# Deploying to Vercel

The project deploys as one Python serverless function from root [index.py](../index.py). Static files are served directly from `public/static`.

## 1. Link the repository

1. Push the project to GitHub.
2. In Vercel, choose **Add New Project** and import the repository.
3. Use the **Other** framework preset.
4. Vercel detects `index.py` as the Python function. `run.py` remains for local Flask development.

## 2. Configure environment variables

Set these variables for Production, Preview, and Development as appropriate:

| Variable | Example | Notes |
| --- | --- | --- |
| `FLASK_ENV` | `production` | Enables production behavior. |
| `SECRET_KEY` | a long random value | Required in production; startup fails without it. |
| `MONGO_URI` | MongoDB Atlas URI | Include the database name in the URI. |
| `RATELIMIT_STORAGE_URI` | `redis://:password@host:6379/0` | Production must use a shared Redis URL. `memory://` is local-only. |
| `COOKIE_SECURE` | `true` | Use secure cookies on Vercel HTTPS. |
| `ALLOW_REGISTRATION` | `false` | Public registration is closed after the first user unless explicitly enabled. |
| `SMTP_HOST` / `SMTP_PORT` | SMTP server and port | Used for verification and password-reset mail. |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | SMTP credentials | Store as encrypted Vercel environment variables. |
| `SMTP_FROM` | `security@example.com` | Sender address for security mail. |
| `CRON_SECRET` | a long random value | Vercel sends this as `Authorization: Bearer <secret>` for the overdue cron. |

Do not commit `.env`; use [.env.example](../.env.example) only as a local template.

## 3. Configure MongoDB Atlas

1. Create an Atlas cluster, database user, and database.
2. In Atlas **Network Access**, allow the Vercel deployment according to the current Vercel egress/IP strategy for your plan.
3. For an initial non-production test, `0.0.0.0/0` may be used temporarily, but restrict it before production.
4. Store the complete Atlas URI, including the database name, in `MONGO_URI`.

The application creates one module-level `MongoClient` with `maxPoolSize=10` and `serverSelectionTimeoutMS=5000`. Warm invocations reuse it. Startup does not create indexes or seed data.

## 4. Create indexes manually

With the required environment variables available locally, run:

```powershell
python scripts/create_indexes.py
```

Run this once for each database environment. It creates indexes for user emails, asset lookups, and risk filtering/search.

## 5. Deploy and verify

1. Click **Deploy** in Vercel.
2. Open `/auth/login`, `/assets`, and `/risks`.
3. Register the first user; that user becomes the administrator.
4. Confirm `/static/app.css`, `/static/app.js`, and `/static/fonts/...` load without CSP violations.
5. Confirm the theme toggle persists after refresh.

For local Vercel parity:

```powershell
npm install
npm run build:css
vercel dev
```

Local Flask development remains:

```powershell
python run.py
```
