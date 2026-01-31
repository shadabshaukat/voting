# Voting & Trivia Application

A modern **Python FastAPI** backend with a **Progressive Web App** (PWA) frontend that lets an admin create polls/trivia questionnaires, set a time limit, and view dynamic results. Attendees can join via a unique URL, enter their name & company, answer multiple‑choice questions, and have their responses recorded.

This app is designed as a single PWA that can run surveys/polls/trivia for multiple users at web‑scale (e.g., seminars and conferences), highlighting PostgreSQL’s capabilities for modern apps.

## Features

- **Admin Dashboard** (`/admin`)  
  - JSON login returning JWT (used by UI)  
  - Create polls with unlimited questions & choices (supports types: trivia/survey/poll; only trivia has correct answers)  
  - Activate / deactivate polls (sets start/end time)  
  - Delete polls (cascades remove questions, choices, participants, votes)  
  - View improved results visualizations (doughnut charts with percentage tooltips)  

- **Attendee UI** (`/`)  
  - Popup for name & company before voting  
  - Timer based on poll end time (default 2 min, configurable)  
  - Automatic submission when time expires  

- **PWA**  
  - Works offline / installable on mobile & desktop  
  - Service worker caches assets  

- **Tech Stack**  
  - **Backend**: FastAPI, SQLAlchemy, PostgreSQL (installed on the host)  
  - **Auth**: JWT  
  - **Frontend**: Vanilla JS, HTML, CSS, Chart.js (via CDN)
  - **PWA**: Service Worker + Manifest with vector icon (maskable)  

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

On startup the app automatically creates tables and applies idempotent migrations to keep older databases compatible (e.g., adds polls.slug, choices.is_correct, participants.company, votes.question_id, and a unique index on (participant_id, question_id)).

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
| `ADMIN_USERNAME` | Admin username for simple .env authentication | `admin` |
| `ADMIN_PASSWORD` | Admin password for simple .env authentication | `admin123` |
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

- You can now delete a poll; this cascades to remove all related questions, choices, participants, and votes.
- Results are displayed with smoother doughnut charts and percentage tooltips; toggle “Show correct answers” to color-code.

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
- Manifest now includes a maskable **SVG icon**; service worker pre‑caches core assets (style, JS, manifest, icon).

## Project Structure

Key improvements vs. original:
- Added votes.question_id and enforced unique votes per participant per question at the DB level.
- Startup and migrate scripts backfill and add the constraint idempotently.
- Admin UI supports deleting polls; backend cascades deletions.
- Results visualization changed to doughnut charts with a pleasing palette and percentage tooltips.
- Added poll types (trivia/survey/poll) with UI controls and backend persistence; trivia controls correct answers only.
- Manifest includes a maskable SVG icon; service worker caches it.
- Minor cleanups and notes for web‑scale seminar use cases.

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

- Enforce submission cutoff by end_time: you can add a server‑side check in POST /poll/{id}/submit to reject votes received after end_time.
- Add rate limiting or IP/session guards for very large events.
- Introduce pagination/filters for admin listings in very large datasets.
- Add export endpoints (CSV/JSON) for poll results and participant lists.
- Add WebSocket channel for real‑time results without polling.
- Multi‑tenant awareness (org/workspace keys) if you want isolated sets of polls per customer, while still being one PWA.

## Next Steps (Suggested)

- Live leaderboard view for trivia, and trend view for surveys/polls.
- Role-based admin areas (e.g., event host vs. analyst) without changing your current auth flow yet.
- Public sharing links with read-only results pages.
- Bulk import/export of polls via JSON/CSV; templated question sets.
- Internationalization (i18n) of UI strings.
- Telemetry and analytics (request rate, submission timings) to showcase Postgres performance at scale.
- Archival mode: mark polls inactive and archive results instead of deleting.

- **Timer length** – set `end_time` when creating a poll (ISO 8601). If omitted, the UI will use the default 2 minutes.  
- **Styling** – edit `static/style.css`.  
- **Charts** – the admin results are returned as JSON; you can integrate Chart.js in `admin.html` to display dynamic graphs.

## Known Limitations and Next Steps

- Admin endpoints are not enforcing authentication on the API routes (UI does obtain a token). If needed later, add route dependencies; per your guidance we are leaving that aside for now.
- Consider archiving vs. deleting polls; current delete fully removes associated data.
- CORS is open for development; restrict in production.

## License

MIT – feel free to adapt and extend.

---  

## HTTPS and Port 443 Support

You can run the app over HTTPS using Let's Encrypt certificates and control HTTP/HTTPS via `.env`.

1. Set the following in `.env`:

```
ENABLE_HTTPS=true
SSL_CERTFILE=/etc/letsencrypt/live/yourdomain/fullchain.pem
SSL_KEYFILE=/etc/letsencrypt/live/yourdomain/privkey.pem
HTTPS_PORT=443
```

2. Start with the management script:

```
./manage.sh start
```

Behavior:
- Run uvicorn with TLS on a non-privileged port (default 8443) controlled by HTTPS_PORT.
- Use a reverse proxy (recommended: Nginx) to expose standard HTTPS on 443 and route to the app.

Nginx setup (Ubuntu/Debian example):

```
sudo apt-get update && sudo apt-get install -y nginx

# Create a site config (adjust server_name, cert/key, ports)
cat | sudo tee /etc/nginx/sites-available/votingapp.conf >/dev/null <<'NGINX'
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name example.com;  # change to your domain or _

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;  # or your paths
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # Proxy to FastAPI TLS endpoint on 8443 (self-terminating), or use HTTP 8000 if preferred
    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_pass https://127.0.0.1:8443;
    }
}

server {
    listen 80;
    listen [::]:80;
    server_name example.com;  # change to your domain or _
    return 301 https://$host$request_uri;
}
NGINX

# Enable and reload
sudo ln -s /etc/nginx/sites-available/votingapp.conf /etc/nginx/sites-enabled/votingapp.conf
sudo nginx -t && sudo systemctl reload nginx
```

Notes:
- The app can terminate TLS itself on 8443. If you prefer Nginx to terminate TLS and proxy HTTP to the app, set ENABLE_HTTPS=false and proxy_pass http://127.0.0.1:8000 instead.
- OCI environments commonly block direct 443 binds for non-root processes; using Nginx on 443 is the supported approach.
- You can still change HTTPS_PORT to any non-privileged port.

## Attendee Details Update

The attendee entry form now requires:
- Full Name
- Company (required)
- Email (required)

Backend changes:
- New fields persisted in the `participants` table: `full_name`, `company`, `email`.
- Legacy databases are migrated at startup (and via `app/migrate.py`) to add these columns and backfill `full_name` from any existing `name` column.
- Admin results, leaderboard and winners views now display the attendee full name.

UI wording:
- The UI refers to each created item as an “Event”. The term “Poll” remains only as a selectable event type (trivia/survey/poll).

Enjoy gathering insights with your new voting/trivia app!