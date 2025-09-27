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
6. Visit [http://localhost:5000](http://localhost:5000) to explore the dashboard, Students page, and new catalog/enrollment tools backed by live data.

> **Note:** Keep `backend/.env` out of version control. The repository `.gitignore` already excludes it.

## API overview

All endpoints return JSON. Errors follow the shape `{ "error": "message", "details": { ... } }`.

| Method | Endpoint                     | Description                                                         |
| ------ | ---------------------------- | ------------------------------------------------------------------- |
| GET    | `/api/health`                | Health probe for monitoring.                                        |
| GET    | `/api/students`              | List students. Supports `q`, `major`, `limit`.                      |
| POST   | `/api/students`              | Create a student (ID, name, email, major, year).                    |
| PUT    | `/api/students/<id>`         | Update a student's attributes.                                      |
| DELETE | `/api/students/<id>`         | Remove a student record.                                            |
| GET    | `/api/courses`               | List courses with optional `q`, `dept`, and `limit` filters.        |
| POST   | `/api/courses`               | Create a course (ID, title, dept, credits).                         |
| PUT    | `/api/courses/<id>`          | Update course metadata.                                             |
| DELETE | `/api/courses/<id>`          | Remove a course (response includes number of remaining sections).   |
| GET    | `/api/sections`              | List class sections. Filters: `course_id`, `semester`, `instructor`. |
| POST   | `/api/sections`              | Create a class section tied to an existing course.                  |
| PUT    | `/api/sections/<id>`         | Update section schedule, instructor, or capacity.                   |
| DELETE | `/api/sections/<id>`         | Remove a section (response includes impacted enrollments).          |
| GET    | `/api/enrollments`           | List enrollments. Filters: `student_id`, `section_id`, `semester`.  |
| POST   | `/api/enrollments`           | Create an enrollment; validates student & section existence.        |
| PUT    | `/api/enrollments/<id>`      | Update enrollment grades/section; recalculates the letter grade.    |
| DELETE | `/api/enrollments/<id>`      | Remove an enrollment record.                                        |
| GET    | `/api/stats`                 | Aggregated dashboard metrics and chart data.                        |

Emails are enforced unique at the database level; duplicate submissions return HTTP `409`.

Optional student attributes include `pronouns` and `phone`. Graduation years are stored as integers.

Courses accept optional `description` text and prerequisite IDs. Sections require an existing course and capture capacity, room, and meeting pattern. Enrollments validate both the student and section foreign keys; if midterm/final/bonus scores are provided the API computes a letter grade automatically.

### Sample cURL

```bash
# Create a course
curl -X POST http://localhost:5000/api/courses \
  -H 'Content-Type: application/json' \
  -d '{
    "_id": "CS350",
    "title": "Operating Systems",
    "dept_id": "CS",
    "credits": 4,
    "description": "Processes, concurrency, and resource management"
  }'

# Create a section for that course
curl -X POST http://localhost:5000/api/sections \
  -H 'Content-Type: application/json' \
  -d '{
    "_id": "SEC-CS350-2025B-01",
    "course_id": "CS350",
    "semester": "2025B",
    "section_no": "01",
    "instructor_id": "I-4001",
    "capacity": 30,
    "room": "ENG-410"
  }'

# Enroll an existing student and include scores
curl -X POST http://localhost:5000/api/enrollments \
  -H 'Content-Type: application/json' \
  -d '{
    "student_id": "S-1001",
    "section_id": "SEC-CS350-2025B-01",
    "semester": "2025B",
    "midterm": 90,
    "final": 94,
    "bonus": 1
  }'

# Dashboard stats
curl http://localhost:5000/api/stats
```

## Seeding scripts

Sample student records live in `scripts/seed.json`. Running `python scripts/seed.py` wipes and repopulates the configured database collections so you can test CRUD flows end-to-end.
