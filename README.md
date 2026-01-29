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
  - **Backend**: FastAPI, SQLAlchemy, PostgreSQL (Docker)  
  - **Auth**: JWT (passlib bcrypt)  
  - **Frontend**: Vanilla JS, HTML, CSS, Chart.js (via CDN)  

## Repository & Deployment Details

- **Repository**: Create a new GitHub repository (e.g., `github.com/yourusername/votingapp`).  
- **Branching**: `main` holds the production‑ready code.  
- **CI/CD (optional)**: Add a GitHub Actions workflow that runs `docker build` and pushes the image to GitHub Packages or Docker Hub on every push to `main`.  
- **Docker Hub**: If you wish to publish the image, tag it as `yourusername/votingapp:latest` and push with `docker push`.  

## Build & Run (Docker)

The application is fully containerised. All you need is Docker & Docker Compose.

### Build the image (optional)

```bash
cd /Users/shadab/Downloads/votingapp
docker build -t votingapp:latest .
```

> The `Dockerfile` uses a lightweight Python 3.11‑slim base, installs the dependencies from `requirements.txt`, and sets a non‑root user.

### Start the stack

```bash
docker-compose up -d
```

- **PostgreSQL 17** container (`votingapp-db`) runs with a superuser `postgres` and a database named `voting`.  
- **FastAPI** container (`votingapp-web`) is exposed on **0.0.0.0:8000** (binds to all host interfaces).  

The API will be reachable at `http://localhost:8000`.  
- Attendee UI: `http://localhost:8000/`  
- Admin dashboard: `http://localhost:8000/admin`

### Stop the stack

```bash
docker-compose down
```

All containers are stopped and removed; volumes (including the database data) are preserved unless you add `-v`.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLAlchemy connection string for PostgreSQL | `postgresql+psycopg2://postgres:voting_pass@db:5432/voting` |
| `JWT_SECRET_KEY` | Secret used to sign JWT tokens | `supersecretkey` |
| `JWT_ALGORITHM` | Algorithm for JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime in minutes | `60` |

You can override any of these in a `.env` file placed at the project root; Docker Compose will automatically load it.

## Default Admin Account

- **Username:** `admin`  
- **Password:** `admin123`

The first start of the container creates this user automatically if it does not exist. You can create additional admin users via the `/admin/create-admin` endpoint or through the UI after logging in.

## Development (without Docker)

1. Create a virtual environment  

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies  

   ```bash
   pip install -r requirements.txt
   ```

3. Set the `DATABASE_URL` environment variable (example for a local Postgres instance)  

   ```bash
   export DATABASE_URL=postgresql+psycopg2://postgres:voting_pass@localhost:5432/voting
   ```

4. Run the server  

   ```bash
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
├─ db/
│   └─ init.sql        # Optional seed script executed on first DB start
├─ docker-compose.yml
├─ Dockerfile
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