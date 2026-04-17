import psycopg2
from psycopg2 import extras

class Database:
    def __init__(self, db_url):
        self.db_url = db_url

    def get_connection(self):
        return psycopg2.connect(self.db_url)

    def get_user_by_username(self, username):
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                # We use LOWER() to make the username case-insensitive
                cur.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
                return cur.fetchone()
        except Exception as e:
            print(f"Database Error: {e}")
            return None
        finally:
            conn.close()

    def get_dashboard_stats(self):
        # Keeps the dashboard from crashing if tables are empty
        conn = self.get_connection()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM users) as user_count,
                        0 as active_loans 
                """)
                return cur.fetchone()
        except:
            return {'user_count': 0, 'active_loans': 0}
        finally:
            conn.close()
