# Student Mgmt App

Modernized administrative dashboard powered by Flask (backend) and a static Tailwind/Alpine front-end.

## Getting started

1. Create and activate a virtual environment (optional but recommended).
2. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Seed MongoDB with baseline data (requires a running Mongo instance and valid credentials):
   ```bash
   python scripts/seed.py
   ```
4. Set the `MONGODB_URI` environment variable for the Flask app (defaults to `mongodb://localhost:27017/student_mgmt`). Example:
   ```bash
   export MONGODB_URI="mongodb://localhost:27017/student_mgmt"
   ```
5. Start the development server:
   ```bash
   python backend/app.py
   ```
6. Visit [http://localhost:5000](http://localhost:5000) to explore the dashboard and feature pages.

> **Tip:** The front-end currently uses in-browser mock data to demonstrate interactions. Once the API endpoints are wired up, the same UI will consume live data.
