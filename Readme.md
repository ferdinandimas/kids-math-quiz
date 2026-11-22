# FastAPI Math App

A lightweight FastAPI application for simple backend services and APIs.

## Product planning

- [KidQuest: Build Your World PRD v1.4](docs/KidQuest_Build_Your_World_PRD_v1.4.md)
- [KidQuest visual design and asset pipeline](docs/KidQuest_Visual_Design_Asset_Pipeline.md)
- [KidQuest implementation plan](docs/KidQuest_Implementation_Plan.md)
- [KidQuest execution task tracker](docs/KidQuest_Execution_Tasks.md)

The KidQuest documents describe an incremental world-building enhancement, its child/parent UX
system, themed asset pipeline, economy, and testable delivery plan. Existing quiz and statistics
flows remain the production baseline until each flagged milestone is verified.

## Requirements
- Python 3.12 (the supported version, matching the Docker image). The code needs at least
  Python 3.10 because it evaluates `X | None` type annotations at runtime.
- pip

## Dependencies

fastapi==0.115.6
uvicorn[standard]==0.32.1
jinja2==3.1.0
tzdata==2026.6

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

## Testing

Install the test dependencies once (they include the runtime requirements):

```bash
pip install -r requirements-dev.txt
```

Run the full suite from the repository root:

```bash
python -m pytest
```

The tests never touch a local `math_app.sqlite3`. `tests/conftest.py` points `DB_PATH` at a
temporary file before the app is imported, and every test gets its own fresh SQLite database,
a frozen clock, and seeded randomness. `tests/integration/test_known_legacy_behaviors.py` records
current legacy behavior that later KidQuest tasks will change, including one expected failure
(`xfail`) for the duplicate-answer race fixed by KQ-003.

## Access

- App: http://127.0.0.1:8000
- Health check: http://127.0.0.1:8000/health
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Project Structure

```
.
├── app/                 # FastAPI routes, services, domain logic, and SQLite access
├── docs/                # Product requirements and implementation plans
├── scripts/             # Database migration and operational commands
├── static/              # JavaScript, CSS, question content, and images
├── tests/               # pytest unit and legacy characterization tests
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt # Test-only dependencies
├── railway.toml
└── run.sh
```

## Notes

- Intended for local development.
- For production, remove `--reload` and bind to `0.0.0.0`.
- Configuration is managed with environment variables. Set `DB_PATH` to an
  absolute path when persisting SQLite data outside the repository. Day boundaries
  use `APP_TIMEZONE` (default `Asia/Jakarta`), never the server's local timezone.
  See [Database Operations](docs/Database_Operations.md) for every variable.
- SQLite database is intentionally excluded from version control.

## Railway

`railway.toml` builds the `Dockerfile` and uses `/health` as the deployment health
check. On start, `docker-entrypoint.sh` creates the database from the image's seed
if the volume is empty, runs the SQLite migrations, and then starts Uvicorn.

Before the first deployment, add a Railway Volume mounted at `/data`, then set:

```text
ADMIN_CLEAR_PASSWORD=<strong secret>
SESSION_COOKIE_SECURE=true
```

The image already sets `DB_PATH=/data/kids-quiz/kids-quiz.sqlite3`. In production
the app refuses to start while `ADMIN_CLEAR_PASSWORD` is unset or the legacy default.

SQLite requires a persistent volume. Without it, Railway's ephemeral filesystem
will discard quiz data whenever a deployment or restart creates a new container.
Back up, verify, and deploy using the runbook in
[Database Operations](docs/Database_Operations.md).

## License

Private / Internal use.
