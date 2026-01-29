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

    # If a previous server is still running, terminate it first
    if [[ -f "${PID_FILE}" ]]; then
        PREV_PID=$(cat "${PID_FILE}")
        if kill -0 "${PREV_PID}" 2>/dev/null; then
            echo "Killing previous server process (PID ${PREV_PID})..."
            kill "${PREV_PID}"
            # Give the OS a moment to release the port
            sleep 1
        fi
        rm -f "${PID_FILE}"
    fi

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
    echo "Server started with PID ${SERVER_PID}."
    echo "Use './manage.sh stop' to stop the server."
}

# Stop: kill the background uvicorn process
stop() {
    if [[ -f "${PID_FILE}" ]]; then
        SERVER_PID=$(cat "${PID_FILE}")
        if kill -0 "${SERVER_PID}" 2>/dev/null; then
            echo "Stopping server (PID ${SERVER_PID})..."
            kill "${SERVER_PID}"
            rm -f "${PID_FILE}"
            echo "Server stopped."
        else
            echo "No process found with PID ${SERVER_PID}. Removing stale PID file."
            rm -f "${PID_FILE}"
        fi
    else
        echo "PID file not found. Is the server running?"
    fi
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