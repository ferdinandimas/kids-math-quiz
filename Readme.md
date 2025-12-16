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
uvicorn main:app --reload
```

## Access

- API: http://127.0.0.1:8000  
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
- Configuration should be managed via environment variables.
- SQLite database is intentionally excluded from version control.

## License

Private / Internal use.
