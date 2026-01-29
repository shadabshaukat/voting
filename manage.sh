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

# Helper: kill anything on port 8000 and known uvicorn processes
kill_port_8000() {
    # Kill by PID file if present
    if [[ -f "${PID_FILE}" ]]; then
        local PID=$(cat "${PID_FILE}")
        if kill -0 "${PID}" 2>/dev/null; then
            echo "Killing process from PID file (PID ${PID})..."
            kill "${PID}" || true
            sleep 1
        fi
        rm -f "${PID_FILE}" || true
    fi

    # Kill anything listening on port 8000 (lsof if available)
    if command -v lsof >/dev/null 2>&1; then
        local PIDS=$(lsof -ti:8000 || true)
        if [[ -n "$PIDS" ]]; then
            echo "Killing processes listening on :8000 (PIDs: $PIDS)..."
            kill $PIDS || true
            sleep 1
        fi
    fi



    # Fallback: pkill uvicorn on this app/port
    pkill -f "uvicorn .*app.main:app.*8000" 2>/dev/null || true

    # Wait briefly for port to free
    for i in {1..10}; do
        if command -v lsof >/dev/null 2>&1; then
            if ! lsof -ti:8000 >/dev/null 2>&1; then
                break
            fi
        fi
        sleep 0.5
    done
}

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

    # Ensure nothing is already bound to port 8000
    kill_port_8000

    # Create DB tables if they do not exist (SQLAlchemy's create_all is idempotent)
    echo "Ensuring database tables exist..."
    uv run python - <<EOF
from app.db import engine, Base
Base.metadata.create_all(bind=engine)
EOF

    # Apply idempotent migrations (safe to run multiple times)
    echo "Applying lightweight DB migrations..."
    uv run python -m app.migrate || true

    # Start uvicorn in background and store its PID
    echo "Starting FastAPI server..."
    uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &
    SERVER_PID=$!
    echo "${SERVER_PID}" > "${PID_FILE}"

    # Verify port is bound by the new process; if still busy by something else, try once more
    sleep 0.5
    if command -v lsof >/dev/null 2>&1; then
        if lsof -ti:8000 >/dev/null 2>&1; then
            echo "Server started with PID ${SERVER_PID}."
        else
            echo "Port 8000 not bound after first attempt. Retrying once..."
            kill_port_8000
            uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &
            SERVER_PID=$!
            echo "${SERVER_PID}" > "${PID_FILE}"
            sleep 0.5
            if lsof -ti:8000 >/dev/null 2>&1; then
                echo "Server started with PID ${SERVER_PID}."
            else
                echo "ERROR: Server failed to bind to :8000 after retry."
                exit 1
            fi
        fi
    else
        echo "Server started with PID ${SERVER_PID}."
    fi
    echo "Use './manage.sh stop' to stop the server."
}

# Stop: kill the background uvicorn process
stop() {
    echo "Stopping any running server on :8000..."
    kill_port_8000
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