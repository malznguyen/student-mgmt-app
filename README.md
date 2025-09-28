# Student Mgmt App

Student management dashboard built with Flask (API) and a static Tailwind/Alpine UI.

## Run locally

1. **Set up a virtual environment**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   ```
2. **Install backend dependencies**
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure MongoDB access**
   - Create `backend/.env` (the file is ignored by git).
   - Provide a connection string via `MONGODB_URI` (and optionally override the database with `MONGODB_DB`).
     ```env
     MONGODB_URI=mongodb://localhost:27017/student_mgmt
     ```
4. **Seed the database** (MongoDB must be running):
   ```bash
   python scripts/seed.py
   ```
5. **Start the API server**
   ```bash
   python backend/app.py
   ```
6. Visit [http://localhost:5000/pages/students.html](http://localhost:5000/pages/students.html) to manage the roster.

## Students API

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| GET    | `/api/students` | List students. Supports `q` for name/email search. |
| POST   | `/api/students` | Create a student. Requires `_id`, `full_name`, `email`, `major_dept_id`, `year`. |
| PUT    | `/api/students/<id>` | Update any student field (email must remain unique). |
| DELETE | `/api/students/<id>` | Remove a student record. |

Responses are JSON. Validation issues return HTTP 400 with an `error` message and optional `details`; duplicate emails respond with HTTP 409.

### Sample cURL

```bash
# Create a new student
curl -X POST http://localhost:5000/api/students \
  -H 'Content-Type: application/json' \
  -d '{
    "_id": "S-3001",
    "full_name": "Jamie Rivera",
    "email": "jamie.rivera@example.edu",
    "major_dept_id": "CS",
    "year": 2026
  }'

# Update an existing student
curl -X PUT http://localhost:5000/api/students/S-3001 \
  -H 'Content-Type: application/json' \
  -d '{
    "phone": "+1-555-300-0001"
  }'

# Delete a student
curl -X DELETE http://localhost:5000/api/students/S-3001
```

## Seeding

`python scripts/seed.py` clears the configured collections and loads `scripts/seed.json`, which contains eight realistic sample students covering different majors and class years. Run it any time you want to reset the roster.

> **Reminder:** keep `backend/.env` out of source control.
