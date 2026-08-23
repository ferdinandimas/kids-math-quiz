# FastAPI Math App

A lightweight FastAPI application for simple backend services and APIs.

## Requirements
- Python 3.9+
- pip

## Dependencies

fastapi==0.115.6  
uvicorn[standard]==0.32.1  

## Setup

### 1. Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / WSL
# .venv\Scripts\activate   # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the application

```bash
./run.sh
```

## Access

- App: http://127.0.0.1:8000
- Health check: http://127.0.0.1:8000/health
- Swagger UI: http://127.0.0.1:8000/docs  
- ReDoc: http://127.0.0.1:8000/redoc  

## Project Structure

```
.
├── main.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Notes

- Intended for local development.
- For production, remove `--reload` and bind to `0.0.0.0`.
- Configuration is managed with environment variables. Set `DB_PATH` to an
  absolute path when persisting SQLite data outside the repository.
- SQLite database is intentionally excluded from version control.

## Railway

`railway.toml` configures Railpack, runs the SQLite migration script before a
deployment, starts `run.sh`, and uses `/health` as the deployment health check.

Before the first deployment, add a Railway Volume mounted at `/data`, then set:

```text
DB_PATH=/data/math_app.sqlite3
ADMIN_CLEAR_PASSWORD=<strong secret>
```

SQLite requires a persistent volume. Without it, Railway's ephemeral filesystem
will discard quiz data whenever a deployment or restart creates a new container.

## License

Private / Internal use.
