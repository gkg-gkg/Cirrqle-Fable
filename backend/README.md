# Cirqle backend

FastAPI app that powers accounts (Phase 1), the Instagram feed (Phase 2), and
receipt uploads (Phase 3). SQLite for storage to start.

## Run locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then edit CIRQLE_SECRET_KEY
uvicorn app.main:app --reload # serves on http://localhost:8000
```

Interactive API docs: http://localhost:8000/docs

## Endpoints (Phase 1)

| Method | Path           | Purpose                                  |
|--------|----------------|------------------------------------------|
| POST   | `/auth/signup` | Create an account, returns a login token |
| POST   | `/auth/signin` | Log in, returns a login token            |
| GET    | `/auth/me`     | Current user (send `Authorization: Bearer <token>`) |
