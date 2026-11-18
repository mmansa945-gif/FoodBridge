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

## 2. Demo workflow (use fictional details)

1. Click Create account; register an NGO named Hope Community Kitchen, email `ngo@example.test`, a unique password of at least 8 characters, area Electronic City, need 80, diet Vegetarian. Sign out.
2. Register a donor named Greenfield Canteen using `donor@example.test`, a separate password, area Electronic City.
3. Post a donation: Vegetable rice, 30 meals, Vegetarian, deadline later today (must be future), notes 'Packed for demonstration'.
4. Go to Smart matching > Find match. Hope Community Kitchen appears. Click Reserve (or sign in as the NGO to reserve it yourself).
5. Track donations > Collect. Sign out, sign in as the NGO > Track donations > Deliver.
6. Sign back in as donor: dashboard should show 30 delivered meals. Export CSV and inspect history. Open another browser or incognito session to demonstrate shared records. Refresh/reopen to see other users' updates.

Accounts are not pre-seeded. Each registration saves data on the backend. Create fresh fictional accounts in the cloud database; local accounts will not automatically transfer to Atlas.

## 3. MongoDB Atlas (shared cloud database)

1. Sign in at https://www.mongodb.com/atlas and create a project and a free cluster (if offered in your region). Select a free tier, not a paid cluster.
2. Under Database Access, create a database user with a unique strong password and read/write access to `foodbridge` only. This is not your Atlas login password.
3. Under Network Access, add your current IP for local Atlas testing. Once Render is created, add the outbound IP ranges shown in Render's Connect/Outbound settings. Prefer specific allowed ranges instead of 0.0.0.0/0. If the free host's networking requires a broad temporary rule for a demo, understand the exposure, use a strong restricted database user, and remove the rule afterwards.
4. Click Connect > Drivers > Python and copy the connection URI. Replace the password placeholder with the database password (URL-encode special characters). Never commit this URI or paste it into frontend/config.js.
5. To test Atlas locally, set `MONGODB_URI` in backend/.env to your real URI and restart the backend. `/health` should now report `mongodb`. Collections `users` and `donations` are created automatically on first write. If you want to keep local data separate, leave the local URI blank instead.

Reference: https://www.mongodb.com/docs/atlas/connect-to-database-deployment/

## 4. Push to GitHub

Create a new empty repository, preferably private, e.g. `FoodBridge`. From the project root:

```powershell
git init
git add .
git status
git commit -m "Build FoodBridge full-stack cloud application"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/FoodBridge.git
git push -u origin main
```

Check git status before committing: `.env`, virtual environments, and local `.db` files must NOT be included. GitHub may prompt you to authenticate. Replace the example GitHub URL with your repository URL.

## 5. Deploy backend on Render

At https://render.com/ sign in, connect GitHub, choose New > Web Service and select the repository. Use these settings (manual creation OR the optional render.yaml Blueprint; do not create two services):

| Setting | Value |
|---|---|
| Language / runtime | Python |
| Root Directory | backend |
| Build Command | pip install -r requirements.txt |
| Start Command | uvicorn main:app --host 0.0.0.0 --port $PORT |
| Instance type | Free (if available) |
| Health Check Path | /health |

Add environment variables under Environment (not in the source repository):

| Variable | Value |
|---|---|
| APP_ENV | production |
| MONGODB_URI | your actual Atlas connection URI |
| MONGODB_DATABASE | foodbridge |
| JWT_SECRET | new random secret of at least 32 characters |
| CORS_ORIGINS | http://127.0.0.1:5500,http://localhost:5500 (update after frontend deployment) |

If deployment fails due to database networking, check your Atlas IP allowlist and credentials. Copy your actual `https://YOUR-SERVICE.onrender.com` URL. Open its `/health` and `/docs`. Health must report MongoDB. Render free web services sleep after inactivity and their local disk is ephemeral; that's why production requires Atlas. Expect a cold-start delay and retry after the backend wakes. Do not use SQLite on Render.

Reference: https://render.com/docs/deploy-fastapi and https://render.com/docs/free

## 6. Set frontend API URL

Edit `frontend/config.js`:

```js
window.FOODBRIDGE_API = 'https://YOUR-SERVICE.onrender.com';
```

Use your real HTTPS Render URL without a trailing slash. Push changes:

```powershell
git add frontend/config.js
git commit -m "Configure deployed API URL"
git push
```

The API URL is public, but secrets are never public. The local frontend will now call the cloud database through Render. To switch back to the local backend, restore the localhost URL while testing, then set the deployed URL again before uploading.

## 7. Deploy frontend on Vercel

1. Sign in at https://vercel.com/ and import your GitHub repository.
2. Select `frontend` as Root Directory. Framework preset: Other. No build command or framework needed. Leave output directory default (project root, `.` if requested). Use a personal/free Hobby project if eligible.
3. Deploy. Copy the production URL, e.g. `https://foodbridge-example.vercel.app`.
4. Add the exact origin to Render `CORS_ORIGINS` (comma-separated, no trailing slash, no `/index.html`), keeping local origins if needed. Save and redeploy/restart Render. Test sign-up on Vercel after backend health succeeds.

## 8. Deploy same frontend on AWS Academy

1. Log into AWS Academy and start your Learner Lab. Read its allowed services and budget limits. Your course has a $50 lab budget; keep it below the limit. Open the AWS console when the AWS indicator is green. If permissions block any operation, do not bypass; ask your instructor.
2. Open **S3 > Create bucket**. Use a globally unique name (e.g. `foodbridge-yourinitials-randomdigits`), a lab-supported region, default encryption, Bucket owner enforced, and keep **Block all public access ON**. No static website hosting toggle is needed for the private-origin method.
3. Open the bucket > Upload. Upload exactly these four files from `frontend/` at the bucket root: `index.html`, `style.css`, `app.js`, `config.js`. Verify config.js contains the actual HTTPS Render API URL. Do not upload the enclosing folder, backend, .env, database files, or credentials.
4. Open **CloudFront > Create distribution**. Choose the S3 bucket REST origin, not the S3 website endpoint. Use Origin Access Control (OAC) with signed requests (recommended). Choose viewer protocol Redirect HTTP to HTTPS; allowed methods GET/HEAD. Set **Default root object = index.html** (without a leading slash). Avoid optional paid features; select a lab-permitted plan. Create distribution.
5. If the console offers a bucket policy update, apply its generated policy. Otherwise copy the generated OAC policy and paste into S3 > Permissions > Bucket policy. The policy allows `cloudfront.amazonaws.com` to read bucket objects only for your distribution ARN. Keep bucket access private. See official OAC instructions below. If the academy role denies bucket policy changes, ask the instructor to enable the permitted approach.
6. Once distribution deployment is complete, open its actual HTTPS domain (e.g. `https://dEXAMPLE.cloudfront.net`). Do not use your instructor's existing distribution or bucket.
7. In Render, add this exact CloudFront origin to CORS_ORIGINS, alongside the Vercel and local URLs. Example only:

```
http://127.0.0.1:5500,http://localhost:5500,https://foodbridge-example.vercel.app,https://dEXAMPLE.cloudfront.net
```

Save the environment change and redeploy/restart Render. Test `/health` first. The browser calls Render directly, so no API proxy or S3 CORS policy is required for this design.

8. Test the AWS website registration/login, create a record on one frontend and sign into the other frontend with the same account to verify data sync. If you update frontend files, upload replacements to S3 and invalidate `/index.html`, `/app.js`, `/style.css`, `/config.js` in CloudFront if stale; invalidations may have charges beyond included usage.

References:
- https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html
- https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DefaultRootObject.html

## 9. API documentation

Use `/docs` on local or deployed backend. For secured routes, obtain the JWT from register/login, click Authorize and enter the token itself (Swagger adds Bearer).

| Method and path | Access / purpose |
|---|---|
| GET /health | Public database readiness |
| POST /api/register | Public create donor or NGO account |
| POST /api/login | Public login, obtain JWT |
| GET /api/me | Authenticated profile |
| PATCH /api/me | NGO updates meal requirement and dietary preference |
| GET /api/ngos | Authenticated NGO network |
| GET /api/donations | Donor's records; NGO's records plus available marketplace |
| POST /api/donations | Donor creates listing |
| GET /api/donations/{id}/matches | Eligible recipients for available listing |
| POST /api/donations/{id}/reserve | Donor assigns own listing, or NGO reserves for itself |
| PATCH /api/donations/{id}/status | Authorized parties collect/release; assigned NGO delivers |
| GET /api/analytics | Authenticated user's statistics |

## 10. Matching algorithm and database

Reject expired listings and incompatible diets. Vegan food is compatible with a Vegetarian recipient, but Vegetarian is not necessarily Vegan. Reject if the recipient's declared requirement minus reserved/collected meals is less than the listing quantity. Score = 30 dietary fit + 30 if the same supported locality + round(40 * quantity / remaining demand). Rank highest first. This is a heuristic recommendation (not a trained AI model, not geographic routing, not a food safety certification). Remaining demand is advisory; simultaneous reservations of distinct donations can exceed declared demand. Recipient updates requirements periodically. Single-donation transitions use atomic revision checks to avoid duplicate/stale reservations.

`users`: id, name, email, password_hash, role, area, need, diet, created_at. `donations`: id, donor_id, donor name, title, qty, diet, deadline, note, area, status, NGO id/name, revision, history, created_at. Donor and NGO IDs link to user IDs. Passwords use salted PBKDF2, and authenticated calls use expiring HS256 JWTs. The API enforces roles and ownership; tokens are stored in browser sessionStorage (not permanent localStorage). Account IDs derive from email hashes in this demo; do not use real personal information. No email verification, password reset, rate limiting, NGO verification, transport integration or production-scale pagination is included. The system is for a student demonstration only.

## 11. Troubleshooting and cleanup

- 401: sign in again, or obtain a new JWT after server secret changes.
- 403: account lacks the role or permission for that action; AWS permission denied requires instructor support.
- 409: reservation conflict, duplicate email, incompatible recipient or invalid status transition; refresh.
- 422: fix required fields or choose a future deadline within 7 days.
- Failed to fetch: verify backend URL, /health, exact CORS origins and HTTPS. Free Render may be asleep.
- CloudFront 403: check root object, correct S3 origin, OAC and generated bucket policy.
- Atlas health failure: check URI, restricted database user and IP allowlist.
- When finished with AWS, disable/delete only your own distribution, delete the associated OAC if unused, and empty/delete your own bucket if the instructor permits. Check budget. Learner Lab access is temporary; do not rely on it for permanent hosting. Vercel and Render free plans have limits and availability may change.

## 12. Run tests

From backend with dependencies installed:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest -v test_api.py
```

Tests use an isolated temporary SQLite database; no Atlas credentials or demo data are required.
