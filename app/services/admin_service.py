from app.config import ADMIN_CLEAR_PASSWORD
from app.db.repo import Repo

class AdminService:
    def __init__(self, repo: Repo):
        self.repo = repo

    def clear_db(self, password: str) -> tuple[bool, str]:
        if (password or "").strip() != ADMIN_CLEAR_PASSWORD:
            return False, "Password salah."
        self.repo.clear_database()
        return True, "Database sudah dikosongkan."