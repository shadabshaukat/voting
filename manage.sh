#!/usr/bin/env bash

# -------------------------------------------------
# Voting & Trivia Application management script
# -------------------------------------------------
# Usage:
#   ./manage.sh build   # Create virtual environment and install dependencies
#   ./manage.sh start   # Start the FastAPI server (creates DB tables if needed)
#   ./manage.sh stop    # Stop the running server
# -------------------------------------------------

# Directory of this script (project root)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
PID_FILE="${PROJECT_ROOT}/uvicorn.pid"
PROXY_PID_FILE="${PROJECT_ROOT}/proxy443.pid"

# Load .env if present (export variables for this shell)
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${PROJECT_ROOT}/.env"
    set +a
fi

# Defaults for networking
UVICORN_HOST=${UVICORN_HOST:-0.0.0.0}
UVICORN_PORT=${UVICORN_PORT:-8000}
ENABLE_HTTPS=${ENABLE_HTTPS:-false}
SSL_CERTFILE=${SSL_CERTFILE:-}
SSL_KEYFILE=${SSL_KEYFILE:-}
HTTPS_PORT=${HTTPS_PORT:-443}

# Helper: kill anything on a given port and known processes
kill_port() {
    local PORT="$1"
    # Kill by PID file if matches known port
    if [[ "$PORT" == "${UVICORN_PORT}" && -f "${PID_FILE}" ]]; then
        local PID=$(cat "${PID_FILE}")
        if kill -0 "${PID}" 2>/dev/null; then
            echo "Killing process from PID file (PID ${PID})..."
            kill "${PID}" || true
            sleep 1
        fi
        rm -f "${PID_FILE}" || true
    fi
    if [[ "$PORT" == "443" && -f "${PROXY_PID_FILE}" ]]; then
        local PPID=$(cat "${PROXY_PID_FILE}")
        if kill -0 "${PPID}" 2>/dev/null; then
            echo "Killing TLS proxy on :443 (PID ${PPID})..."
            kill "${PPID}" || true
            sleep 1
        fi
        rm -f "${PROXY_PID_FILE}" || true
    fi

    # Kill anything listening on the port (lsof if available)
    if command -v lsof >/dev/null 2>&1; then
        local PIDS=$(lsof -ti:"${PORT}" || true)
        if [[ -n "$PIDS" ]]; then
            echo "Killing processes listening on :${PORT} (PIDs: $PIDS)..."
            kill $PIDS || true
            sleep 1
        fi
    fi

    # Fallback: pkill uvicorn on this app/port
    pkill -f "uvicorn .*app.main:app.*${PORT}" 2>/dev/null || true

    # Wait briefly for port to free
    for i in {1..10}; do
        if command -v lsof >/dev/null 2>&1; then
            if ! lsof -ti:"${PORT}" >/dev/null 2>&1; then
                break
            fi
        fi
        sleep 0.5
    done
}

# Backward-compatible wrapper
kill_port_8000() { kill_port 8000; }

# Activate virtual environment
activate_venv() {
    if [[ -d "${VENV_DIR}" ]]; then
        source "${VENV_DIR}/bin/activate"
    else
        echo "Virtual environment not found. Run './manage.sh build' first."
        exit 1
    fi
}

# Build: create venv and install deps
build() {
    echo "Creating virtual environment..."
    uv venv "${VENV_DIR}"
    activate_venv
    echo "Installing Python dependencies..."
    uv pip install -r "${PROJECT_ROOT}/requirements.txt"
    echo "Build complete."
}

# Start: ensure DB tables exist, then launch server in background
start() {
    activate_venv

    # Stop anything on target ports
    kill_port "${UVICORN_PORT}"
    if [[ "${ENABLE_HTTPS}" =~ ^(1|true|yes)$ ]]; then
        kill_port "${HTTPS_PORT}"
    fi

    # Create DB tables if they do not exist (SQLAlchemy's create_all is idempotent)
    echo "Ensuring database tables exist..."
    uv run python - <<'EOF'
from app.db import engine, Base
Base.metadata.create_all(bind=engine)
EOF

    # Apply idempotent migrations (safe to run multiple times)
    echo "Applying lightweight DB migrations..."
    uv run python -m app.migrate || true

    # Start server based on HTTPS settings
    if [[ "${ENABLE_HTTPS}" =~ ^(1|true|yes)$ && -n "${SSL_CERTFILE}" && -n "${SSL_KEYFILE}" ]]; then
        if [[ "${HTTPS_PORT}" != "443" ]]; then
            echo "Starting FastAPI with HTTPS on :${HTTPS_PORT}..."
            uv run uvicorn app.main:app --host "${UVICORN_HOST}" --port "${HTTPS_PORT}" \
                --ssl-certfile "${SSL_CERTFILE}" --ssl-keyfile "${SSL_KEYFILE}" &
            SERVER_PID=$!
            echo "${SERVER_PID}" > "${PID_FILE}"
            TARGET_PORT="${HTTPS_PORT}"
        else
            echo "Attempting to bind HTTPS on privileged port :443 directly..."
            set +e
            uv run uvicorn app.main:app --host "${UVICORN_HOST}" --port 443 \
                --ssl-certfile "${SSL_CERTFILE}" --ssl-keyfile "${SSL_KEYFILE}" &
            SERVER_PID=$!
            echo "${SERVER_PID}" > "${PID_FILE}"
            sleep 0.8
            if command -v lsof >/dev/null 2>&1 && lsof -ti:443 >/dev/null 2>&1; then
                echo "Server started with PID ${SERVER_PID} on :443 (HTTPS)."
                TARGET_PORT=443
            else
                echo "Direct bind to :443 failed (likely due to privileges). Falling back to TLS proxy (socat) on :443 -> :${UVICORN_PORT}."
                # Kill the failed attempt
                kill "${SERVER_PID}" 2>/dev/null || true
                sleep 0.5
                # Start backend on HTTP :UVICORN_PORT
                uv run uvicorn app.main:app --host "${UVICORN_HOST}" --port "${UVICORN_PORT}" &
                SERVER_PID=$!
                echo "${SERVER_PID}" > "${PID_FILE}"
                sleep 0.5
                # Start socat TLS terminator if available
                if command -v socat >/dev/null 2>&1; then
                    socat openssl-listen:443,reuseaddr,cert="${SSL_CERTFILE}",key="${SSL_KEYFILE}",fork TCP:127.0.0.1:"${UVICORN_PORT}" &
                    PROXY_PID=$!
                    echo "${PROXY_PID}" > "${PROXY_PID_FILE}"
                    echo "TLS proxy started on :443 (PID ${PROXY_PID}), forwarding to :${UVICORN_PORT}."
                    TARGET_PORT=443
                else
                    echo "WARNING: 'socat' not found. Install it with 'sudo apt-get install -y socat' (Debian/Ubuntu) to enable :443 TLS proxy."
                    echo "HTTPS fallback not available; server is running on http://0.0.0.0:${UVICORN_PORT}"
                    TARGET_PORT="${UVICORN_PORT}"
                fi
            fi
            set -e
        fi
    else
        echo "Starting FastAPI (HTTP) on :${UVICORN_PORT}..."
        uv run uvicorn app.main:app --host "${UVICORN_HOST}" --port "${UVICORN_PORT}" &
        SERVER_PID=$!
        echo "${SERVER_PID}" > "${PID_FILE}"
        TARGET_PORT="${UVICORN_PORT}"
    fi

    # Verify port is bound
    sleep 0.5
    if command -v lsof >/dev/null 2>&1; then
        if lsof -ti:"${TARGET_PORT}" >/dev/null 2>&1; then
            echo "Server ready on port ${TARGET_PORT}."
        else
            echo "ERROR: Server failed to bind to :${TARGET_PORT}."
            exit 1
        fi
    else
        echo "Server started (port ${TARGET_PORT})."
    fi

    echo "Use './manage.sh stop' to stop the server."
}

# Stop: kill the background uvicorn process
stop() {
    echo "Stopping any running servers..."
    kill_port "${UVICORN_PORT}"
    if [[ "${ENABLE_HTTPS}" =~ ^(1|true|yes)$ ]]; then
        kill_port "${HTTPS_PORT}"
        # Also ensure proxy is killed
        if [[ -f "${PROXY_PID_FILE}" ]]; then
            local PPID=$(cat "${PROXY_PID_FILE}")
            kill "${PPID}" 2>/dev/null || true
            rm -f "${PROXY_PID_FILE}" || true
        fi
    fi
    echo "Done."
}

# Main entry point
case "$1" in
    build)
        build
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    *)
        echo "Invalid command. Use one of: build | start | stop"
        exit 1
        ;;
esac