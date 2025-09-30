# Student Management App

Dashboard for managing university students, courses, sections, and enrollments.

## Tech stack
- Frontend: HTML + Tailwind + Alpine + Chart.js (CDN)
- Backend: Flask
- DB: MongoDB
- Auth: fixed admin/123456

## System requirements
- Python 3.10+
- MongoDB 6.x (local or Atlas)
- Node.js not required (static frontend)

## Project structure
```
.
├── backend/   # Flask application and API
├── frontend/  # Static pages and assets
└── scripts/   # Maintenance and seed utilities
```

## Quick start (local)
```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```
Create `backend/.env` with:
```bash
cat > backend/.env <<'ENV'
MONGODB_URI=mongodb://localhost:27017/university
APP_SECRET=dev-secret-please-change
ADMIN_USER=admin
ADMIN_PASS=123456
ENV
```
Seed and run:
```bash
python scripts/seed.py
python backend/app.py
```
Open http://localhost:5000/pages/login.html (sign in with admin / 123456), then browse the dashboard pages.

## MongoDB Atlas (optional)
Set `MONGODB_URI` in `backend/.env` to your Atlas connection string (include username, password, and default database). Ensure the IP whitelist allows your client or Codespaces.

## GitHub Codespaces (optional)
1. Create a Codespace from the repository.
2. Run the quick start commands in the terminal (venv + install + .env + seed).
3. Start the server with `python backend/app.py` and forward port 5000 to access `/pages/login.html`.

## Scripts
- `python scripts/seed.py` — reset sample data for students, courses, sections, and enrollments.

## Troubleshooting
- **MongoDB connection errors**: confirm the database service is running and `MONGODB_URI` points to an accessible instance.
- **Seed data missing**: verify you activated the virtual environment, MongoDB was running, and the target database matches the URI before rerunning `python scripts/seed.py`.
- **Cannot create/update/delete records**: log in at `/pages/login.html` with admin credentials to unlock write actions.
- **Port already in use**: stop other services using 5000 or set `FLASK_RUN_PORT` before launching the app.

## Dev notes
- Static frontend served directly; no build tools or bundlers are involved.
- Seed script can be rerun safely; indexes and sample data are idempotent.
- Prefer small, focused pull requests with linked issue context.

## License
Internal project — contact the maintainers before external reuse.
