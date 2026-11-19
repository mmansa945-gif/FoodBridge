# FoodBridge — Full-stack cloud project

Cloud-Based Surplus Food Redistribution and Intelligent Donation Matching System

## Problem statement
Restaurants, college canteens, hostels and events often generate surplus food while recipient organizations have unmet meal requirements. FoodBridge provides a shared workspace to register surplus food, recommend suitable recipient organizations and track donations through collection and delivery. It is a student demonstration, not a verified food-safety or emergency distribution service.

## Architecture

```
Browser ── HTTPS ── AWS CloudFront ── private Amazon S3 bucket
   │
   ├── or Vercel (same static frontend)
   │
   └── HTTPS REST API ── Render / FastAPI ── MongoDB Atlas
                             │
                        SQLite locally (optional)
```

Both deployed frontends use the same API and database. AWS hosts only static assets, not the backend. Obtain your instructor's approval for this hybrid architecture.

## Files

```
FoodBridge_FullStack/
├── frontend/
│   ├── index.html       # login, registration and application shell
│   ├── style.css        # responsive styling
│   ├── app.js           # frontend logic and real API requests
│   ├── config.js        # public backend URL, not credentials
│   └── vercel.json      # static deployment settings
├── backend/
│   ├── main.py          # FastAPI routes, validation, auth and matching
│   ├── store.py         # MongoDB and local SQLite adapters
│   ├── requirements.txt # Python runtime libraries
│   ├── requirements-dev.txt # API test dependency
│   ├── .env.example     # environment template
│   └── test_api.py      # API integration tests
├── .gitignore
├── render.yaml          # optional Render Blueprint configuration
├── README.md            # this guide
└── TEST_RESULTS.md
```

## 1. Run on Windows / VS Code (no cloud account needed yet)

Install Python 3.11 or 3.12 and VS Code. Extract the ZIP, open the **FoodBridge_FullStack** folder in VS Code. Open a PowerShell terminal. Run:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the random secret printed in the last command into `backend/.env` as `JWT_SECRET`. Do not share it. Leave `MONGODB_URI` blank for now. The other defaults work locally. If `py -3.12` is unavailable but `python --version` works, use `python -m venv .venv` instead.

Start the backend (leave this terminal open):

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

Open http://127.0.0.1:8000/docs to see Swagger, and http://127.0.0.1:8000/health to verify storage is `sqlite` and status is `ok`. No database installation needed. Local data is saved as `backend/foodbridge.db`.

Open a **second** VS Code terminal from the project root:

```powershell
cd frontend
python -m http.server 5500 --bind 127.0.0.1
```

Open http://127.0.0.1:5500 in Chrome. Do not double-click index.html: use the local HTTP server to avoid browser origin errors. `frontend/config.js` should contain the local API URL:

```js
window.FOODBRIDGE_API = 'http://127.0.0.1:8000';
```

If using VS Code Live Server, keep port 5500 or add its actual origin to `CORS_ORIGINS` in `.env` and restart the backend. If Python is not on PATH in terminal 2, use `py -3.12 -m http.server 5500 --bind 127.0.0.1`.

