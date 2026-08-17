from pydantic_settings import BaseSettings
import os
import datetime

class Settings(BaseSettings):
    SHEET_URL: str = ""
    ADMIN_PHONE: str = ""
    WHATSAPP_SESSION_NAME: str = "my_session"
    MAX_RETRIES: int = 3
    RETRY_DELAY_SECONDS: int = 5
    WARNING_BUFFER_MINUTES: int = 5
    ADMIN_USERNAME: str = "admin"
    ADMIN_ID: str = "admin"
    ADMIN_PASSWORD: str = "adminpassword"
    SECRET_KEY: str = "supersecretkey123"
    
    class Config:
        case_sensitive = False
        env_file = ".env"

    def check_admin_credentials(self, username: str, password: str) -> bool:
        """Validates credentials against environment variables and settings."""
        accepted_ids = {
            self.ADMIN_ID.strip(),
            self.ADMIN_USERNAME.strip(),
            os.environ.get("ADMIN_ID", "").strip(),
            os.environ.get("ADMIN_USERNAME", "").strip(),
            os.environ.get("ADMINID", "").strip(),
            os.environ.get("ADMIN", "").strip(),
        }
        accepted_ids.discard("")
        if not accepted_ids:
            accepted_ids.add("admin")

        accepted_passwords = {
            self.ADMIN_PASSWORD.strip(),
            os.environ.get("ADMIN_PASSWORD", "").strip(),
            os.environ.get("ADMINPASSWORD", "").strip(),
            os.environ.get("PASSWORD", "").strip(),
        }
        accepted_passwords.discard("")
        if not accepted_passwords:
            accepted_passwords.add("adminpassword")

        user_match = username.strip() in accepted_ids
        pass_match = password.strip() in accepted_passwords
        return user_match and pass_match

settings = Settings()

def log_debug(msg):
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("debug_output.txt", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {msg}\n")
    except Exception as e:
        print(f"Logging failed: {e}")
