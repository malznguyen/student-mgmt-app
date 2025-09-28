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

## Courses API

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| GET    | `/api/courses` | List courses. Supports `q` (title search), `dept`, and `limit` (defaults to 100). |
| POST   | `/api/courses` | Create a course. Requires `_id`, `title`, `dept_id`, and integer `credits`; optional `prereq_ids` array. |
| PUT    | `/api/courses/<id>` | Update an existing course's fields. |
| DELETE | `/api/courses/<id>` | Remove a course from the catalog. |

Errors return JSON payloads such as `{ "error": "Course not found." }` with the appropriate HTTP status. Duplicate IDs respond with HTTP 409.

### Sample cURL

```bash
# Create a new course
curl -X POST http://localhost:5000/api/courses \
  -H 'Content-Type: application/json' \
  -d '{
    "_id": "CS350",
    "title": "Operating Systems",
    "dept_id": "CS",
    "credits": 4,
    "prereq_ids": ["CS210"]
  }'

# Update course credits
curl -X PUT http://localhost:5000/api/courses/CS350 \
  -H 'Content-Type: application/json' \
  -d '{
    "credits": 3
  }'

# Delete a course
curl -X DELETE http://localhost:5000/api/courses/CS350
```

## Sections API

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| GET    | `/api/sections` | List class sections. Supports `course_id`, `semester`, `instructor_id`, `q` (matches section/course IDs), and `limit` (defaults to 200). |
| POST   | `/api/sections` | Create a section. Requires `_id`, `course_id`, `semester`, and `section_no`; optional `instructor_id`, `capacity`, `room`, and `schedule`. Validates that `course_id` exists. |
| PUT    | `/api/sections/<id>` | Update any section fields (cannot change `_id`). Validates referenced course when `course_id` is supplied. |
| DELETE | `/api/sections/<id>` | Delete a section. Returns number of affected enrollments for awareness. |

Validation failures respond with HTTP 400 and `details` describing the offending fields. Unknown courses respond with HTTP 404, and creating a duplicate `_id` returns HTTP 409.

### Sample cURL

```bash
# Create a new section
curl -X POST http://localhost:5000/api/sections \
  -H 'Content-Type: application/json' \
  -d '{
    "_id": "CS210_2025B_01",
    "course_id": "CS210",
    "semester": "2025B",
    "section_no": "01",
    "instructor_id": "I-2403",
    "capacity": 28,
    "room": "TECH-214",
    "schedule": [
      { "dow": "Tue", "start": "09:30", "end": "10:45" },
      { "dow": "Thu", "start": "09:30", "end": "10:45" }
    ]
  }'

# Update the meeting pattern for an existing section
curl -X PUT http://localhost:5000/api/sections/CS210_2025B_01 \
  -H 'Content-Type: application/json' \
  -d '{
    "schedule": [
      { "dow": "Mon", "start": "08:30", "end": "09:45" },
      { "dow": "Wed", "start": "08:30", "end": "09:45" }
    ]
  }'

# Delete a section
curl -X DELETE http://localhost:5000/api/sections/CS210_2025B_01
```

## Enrollments API

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| GET    | `/api/enrollments` | List enrollments. Supports `student_id`, `section_id`, `semester`, and `limit` (defaults to 200). |
| POST   | `/api/enrollments` | Create an enrollment. Requires `student_id`, `section_id`, and `semester`. Optional `midterm`, `final`, and `bonus` scores compute the letter grade using the 0–10 scale (`0.4*midterm + 0.6*final + bonus`, capped at 10). Validates that the student and section exist for the semester. |
| PUT    | `/api/enrollments/<id>` | Update `midterm`, `final`, `bonus`, `semester`, or `section_id`. Recomputes the letter grade when scores change. |
| DELETE | `/api/enrollments/<id>` | Remove an enrollment record. |

Missing students/sections respond with HTTP 404, duplicate `student_id` + `section_id` pairs respond with HTTP 409, and MongoDB outages respond with HTTP 503 and an `error` message.

### Sample cURL

```bash
# Create an enrollment with initial scores
curl -X POST http://localhost:5000/api/enrollments \
  -H 'Content-Type: application/json' \
  -d '{
    "student_id": "S-2001",
    "section_id": "CS101_2025A_01",
    "semester": "2025A",
    "midterm": 8.8,
    "final": 9.2,
    "bonus": 0.5
  }'

# Update the final score (recalculates the letter grade)
curl -X PUT http://localhost:5000/api/enrollments/<enrollment_id> \
  -H 'Content-Type: application/json' \
  -d '{
    "final": 9.4,
    "bonus": 0.8
  }'

# Delete an enrollment
curl -X DELETE http://localhost:5000/api/enrollments/<enrollment_id>
```

## Seeding

`python scripts/seed.py` clears the configured collections and loads `scripts/seed.json`, which now contains sample students, seven catalog courses, eight ready-to-use class sections, and ten example enrollments with precomputed grades. Run it any time you want to reset the roster, catalog, and schedule data.

> **Reminder:** keep `backend/.env` out of source control.
