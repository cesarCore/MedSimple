# MedSimple Deployment

## Backend — Render (Docker, free tier)

1. Push this repo to GitHub.
2. In Render: **New → Blueprint** → point at the repo. It will read `render.yaml`.
3. Set the three secrets in the Render dashboard (marked `sync: false` in `render.yaml`):
   - `OPENAI_API_KEY`
   - `PUBMED_API_KEY`
   - `GOOGLE_MAPS_API_KEY`
4. Wait for build (~10 min: torch + paddleocr are heavy). Health check: `/health`.
5. Note the public URL, e.g. `https://medsimple-backend.onrender.com`.

Cold-start note: Render free tier sleeps after 15 min idle. First hit after sleep takes ~30–60 s.

## Frontend — Vercel

1. `cd frontend && vercel` (or import the repo root and set **Root Directory** to `frontend`).
2. Framework preset: Create React App (auto-detected via `vercel.json`).
3. Add env var: `REACT_APP_API_URL` = the Render URL from above.
4. Deploy. Vercel serves the static build — the 10 s serverless limit does not apply (no serverless functions are used).

## Local dev

```bash
# Backend
cd backend && pip install -r requirements.txt && python app.py   # port 5001

# Frontend
cd frontend && npm install && npm start                          # port 3000
```

The frontend `package.json` proxy points at `http://localhost:5001`.
