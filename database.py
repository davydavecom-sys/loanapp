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
            conn = self.get_connection()
            # Default stats to show if things fail
            default_stats = {'user_count': 0, 'active_loans': 0}
            try:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                    # We wrap this in a try/except so one missing table doesn't kill the app
                    cur.execute("SELECT COUNT(*) as user_count FROM users")
                    res = cur.fetchone()
                    return res if res else default_stats
            except Exception as e:
                print(f"Dashboard Query Error: {e}")
                return default_stats
            finally:
                conn.close()
