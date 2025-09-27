# Student Mgmt App

Modernized administrative dashboard powered by Flask (backend) and a static Tailwind/Alpine front-end.

## Getting started

1. **Create a Python virtual environment (recommended)**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\\Scripts\\activate
   ```
2. **Install backend dependencies**
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure MongoDB access**
   - Copy `backend/.env.example` to `backend/.env` if available or create a new `.env` file.
   - Add the connection string (includes the database name) as `MONGODB_URI`. Example:
     ```env
     MONGODB_URI=mongodb://localhost:27017/student_mgmt
     ```
   - Optionally override the database name with `MONGODB_DB`.
4. **Seed the database with sample data** (requires a running MongoDB instance):
   ```bash
   python scripts/seed.py
   ```
5. **Start the development server**
   ```bash
   python backend/app.py
   ```
6. Visit [http://localhost:5000](http://localhost:5000) to explore the dashboard and Students page backed by live data.

> **Note:** Keep `backend/.env` out of version control. The repository `.gitignore` already excludes it.

## API overview

All endpoints return JSON. Errors follow the shape `{ "error": "message", "details": { ... } }`.

| Method | Endpoint                  | Description                                      |
| ------ | ------------------------- | ------------------------------------------------ |
| GET    | `/api/health`             | Health probe for monitoring.                     |
| GET    | `/api/students`           | List students. Supports `q`, `major`, `limit`.   |
| POST   | `/api/students`           | Create a student (ID, name, email, major, year). |
| PUT    | `/api/students/<id>`      | Update a student's attributes.                   |
| DELETE | `/api/students/<id>`      | Remove a student record.                         |

Emails are enforced unique at the database level; duplicate submissions return HTTP `409`.

Optional attributes include `pronouns` and `phone`. Graduation years are stored as integers.

## Seeding scripts

Sample student records live in `scripts/seed.json`. Running `python scripts/seed.py` wipes and repopulates the configured database collections so you can test CRUD flows end-to-end.
