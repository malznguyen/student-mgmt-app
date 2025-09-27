# Student Mgmt App

Modernized administrative dashboard powered by Flask (backend) and a static Tailwind/Alpine front-end.

## Getting started

1. Create and activate a virtual environment (optional but recommended).
2. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure MongoDB connection settings in `backend/.env` (or export them as environment variables). The app defaults to a local instance:
   ```bash
   echo "MONGODB_URI=mongodb://localhost:27017" > backend/.env
   echo "MONGODB_DB_NAME=university" >> backend/.env
   ```
4. Seed MongoDB with baseline data (requires a running Mongo instance and valid credentials):
   ```bash
   python scripts/seed.py
   ```
5. Start the development server:
   ```bash
   python backend/app.py
   ```
6. Visit [http://localhost:5000](http://localhost:5000) to explore the dashboard and feature pages.

> **Tip:** The Students page now loads from `/api/students`, while other pages continue to use in-browser mock data until their APIs are implemented.
