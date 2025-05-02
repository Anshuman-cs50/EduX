import sqlite3
import logging
from werkzeug.security import generate_password_hash, check_password_hash
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class UserManager:
    def __init__(self, db_path: str = 'database/edu_chat.db'):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_user(self, username: str, email: str, password: str) -> bool:
        """Create new user with hashed password"""
        try:
            password_hash = generate_password_hash(password)
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                    (username, email, password_hash)
                )
                conn.commit()
            logger.info(f"User created: {username}")
            return True
        except sqlite3.IntegrityError as e:
            logger.warning(f"User creation failed (integrity error): {str(e)}")
            return False
        except Exception as e:
            logger.error(f"User creation failed: {str(e)}")
            return False
            
    def authenticate_user(self, username_or_email: str, password: str) -> Optional[dict]:
        """Verify credentials and return user data"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ? OR email = ?",
                (username_or_email, username_or_email)
            )
            user = cursor.fetchone()
            
            if user and check_password_hash(user['password_hash'], password):
                return dict(user)
            return None

    def get_user_stats(self, user_id: int) -> List[Dict]:
        """Get user progress statistics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT topic, correct_count, incorrect_count, avg_response_time
                FROM user_progress 
                WHERE user_id = ?
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]