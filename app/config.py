import os

APP_TITLE = "Kids Math Quiz"
DAILY_LIMIT = 400
REWARD_PER_CORRECT = 50
COOKIE_NAME = "math_sess"

DB_PATH = os.getenv("DB_PATH", "math_app.sqlite3")
ADMIN_CLEAR_PASSWORD = os.getenv("ADMIN_CLEAR_PASSWORD", "masukaja")

CHILDREN = ["althafandra", "alleia"]