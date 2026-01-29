# Voting & Trivia Application

A modern **Python FastAPI** backend with a **Progressive Web App** (PWA) frontend that lets an admin create polls/trivia questionnaires, set a time limit, and view dynamic results. Attendees can join via a unique URL, enter their name & company, answer multiple‑choice questions, and have their responses recorded.

## Features

- **Admin Dashboard** (`/admin`)  
  - JWT‑protected login  
  - Create polls with unlimited questions & choices (JSON format)  
  - Activate / deactivate polls (sets start/end time)  
  - View real‑time results (vote counts per choice)  

- **Attendee UI** (`/`)  
  - Popup for name & company before voting  
  - Timer based on poll end time (default 2 min, configurable)  
  - Automatic submission when time expires  

- **PWA**  
  - Works offline / installable on mobile & desktop  
  - Service worker caches assets  

- **Tech Stack**  
  - **Backend**: FastAPI, SQLAlchemy, PostgreSQL (installed on the host)  
  - **Auth**: JWT (passlib bcrypt)  
  - **Frontend**: Vanilla JS, HTML, CSS, Chart.js (via CDN)  

## Prerequisites

- **Ubuntu 22.04+** (or any recent Debian‑based distro)  
- **Python 3.11** (or newer)  
- **uv** – a fast Python package installer & runner  
- **PostgreSQL 17** – will be installed via the official PostgreSQL APT repository  

## Install `uv`

```bash
# Install uv (single‑line installer)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Ensure ~/.local/bin is on your PATH
export PATH="$HOME/.local/bin:$PATH"
```

## Clean up any existing PostgreSQL installation

```bash
# Stop the service if it is running
sudo systemctl stop postgresql

# Remove all PostgreSQL packages and configuration files
sudo apt-get --purge remove -y postgresql*
sudo rm -rf /etc/postgresql /var/lib/postgresql
```

## Install PostgreSQL 17

```bash
# 1. Install required utilities
sudo apt-get install -y wget gnupg lsb-release ca-certificates

# 2. Add the PostgreSQL APT repository signing key
wget -qO - https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
    sudo gpg --dearmor -o /usr/share/keyrings/pgdg.gpg

# 3. Add the repository (replace $(lsb_release -cs) with your Ubuntu codename, e.g. noble)
echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" | \
    sudo tee /etc/apt/sources.list.d/pgdg.list > /dev/null

# 4. Update package lists and install PostgreSQL 17
sudo apt-get update
sudo apt-get install -y postgresql-17

# 5. Enable and start the service
sudo systemctl enable --now postgresql

## Project Setup (using `uv`)

```bash
# Clone the repository (or copy the source folder)
git clone https://github.com/shadabshaukat/voting.git
cd voting

# Create a virtual environment (recommended)
uv venv .venv
source .venv/bin/activate   # or: . .venv/bin/activate

# Install Python dependencies into the venv
uv pip install -r requirements.txt

# If you prefer not to use a venv, you can install system‑wide:
# uv pip install -r requirements.txt --system

# The FastAPI app will create tables automatically on first run.
```

## Run the Application

```bash
# Using uv to run the server
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be reachable at `http://0.0.0.0:8000`:

- Attendee UI: `http://0.0.0.0:8000/`  
- Admin dashboard: `http://0.0.0.0:8000/admin`

## Management Script

A helper script **manage.sh** is provided to simplify building, starting, and stopping the application in the `uv` virtual environment.

```bash
# Make the script executable
chmod +x manage.sh

# Build the virtual environment and install dependencies
./manage.sh build

# Start the server (runs in background, stores PID in uvicorn.pid)
./manage.sh start

# Stop the server
./manage.sh stop
```

The `start` command also ensures that database tables are created if they do not already exist (SQLAlchemy’s `create_all` is idempotent, so existing objects are left untouched).

```
# Example workflow
./manage.sh build   # one‑time setup
./manage.sh start   # launch the app
# ... use the app ...
./manage.sh stop    # shut it down
```

The script handles virtual‑environment activation automatically, so you never need to run `uv` commands manually.

## Environment Variables

The application reads its configuration from a **.env** file placed in the project root.  
Create the file (or copy the provided template) and adjust the values to match your environment.

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | `voting` |
| `DB_USER` | Database user | `voting_user` |
| `DB_PASSWORD` | Database password (single‑quoted; special characters are stripped by the app) | `voting_pass` |
| `DB_SSLMODE` | SSL mode (require) | `require` |
| `JWT_SECRET_KEY` | Secret used to sign JWT tokens | `supersecretkey` |
| `JWT_ALGORITHM` | Algorithm for JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime in minutes | `60` |

You can override any of these in a `.env` file placed at the project root; `uv run` will automatically load it.

## Default Admin Account

- **Username:** `admin`  
- **Password:** `admin123`

The first start of the application creates this user automatically if it does not exist. You can create additional admin users via the `/admin/create-admin` endpoint or through the UI after logging in.

## Development (without `uv`)

If you prefer a classic virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Using the Admin Dashboard

1. Open `http://localhost:8000/admin` in a browser.  
2. Log in with the admin credentials.  
3. **Create a poll** – fill the form (questions must be a JSON array, e.g.:

   ```json
   [
     {
       "text": "What is your favorite color?",
       "choices": [{"text":"Red"},{"text":"Blue"},{"text":"Green"}]
     },
     {
       "text": "How often do you use our product?",
       "choices": [{"text":"Daily"},{"text":"Weekly"},{"text":"Monthly"}]
     }
   ]
   ```

4. Activate the poll – it becomes visible on the public URL (`/`).  
5. Attendees can now vote; after the poll ends you can view results via **View Results**.

## PWA Installation

- Open the site in Chrome/Edge on mobile or desktop.  
- Click the **Install** button in the address bar (or “Add to Home screen”).  
- The app will work offline for the already‑loaded poll.

## Project Structure

```
votingapp/
├─ app/
│  ├─ __init__.py
│  ├─ main.py          # FastAPI app, routes, static & template mounting
│  ├─ config.py        # Settings (DB URL, JWT secret)
│  ├─ db.py            # SQLAlchemy engine & session
│  ├─ models.py        # ORM models
│  ├─ schemas.py       # Pydantic request/response models
│  ├─ auth.py          # Password hashing, JWT utilities, dependencies
│  ├─ routers/
│  │   ├─ admin.py     # Admin CRUD, auth, results
│  │   └─ poll.py      # Public poll fetching & vote submission
│  ├─ static/
│  │   ├─ style.css
│  │   ├─ main.js
│  │   ├─ manifest.json
│  │   └─ sw.js
│  └─ templates/
│      ├─ index.html   # Attendee UI
│      └─ admin.html   # Admin dashboard
├─ requirements.txt
└─ README.md
```

## Customisation

- **Timer length** – set `end_time` when creating a poll (ISO 8601). If omitted, the UI will use the default 2 minutes.  
- **Styling** – edit `static/style.css`.  
- **Charts** – the admin results are returned as JSON; you can integrate Chart.js in `admin.html` to display dynamic graphs.

## License

MIT – feel free to adapt and extend.

---  

Enjoy gathering insights with your new voting/trivia app!