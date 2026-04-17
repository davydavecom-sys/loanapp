import os
import psycopg2
from psycopg2 import extras
from dotenv import load_dotenv

load_dotenv()

class LoanAppDB:
    def __init__(self):
        # This pulls the link from your Render Environment Variables
        self.url = os.environ.get('DATABASE_URL')

    def get_connection(self):
        try:
            return psycopg2.connect(self.url)
        except Exception as e:
            print(f"Database Connection Failed: {e}")
            return None

    def get_user_by_username(self, username):
    query = "SELECT id, username, password, role FROM users WHERE username = %s"
    conn = self.get_connection()
    if not conn: return None
    try:
        with conn:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute(query, (username,))
                return cur.fetchone()
    finally:
        conn.close()

    def login_user(self, username, password):
        """Checks credentials. Uses %s for PostgreSQL."""
        query = "SELECT id, username, role FROM users WHERE username = %s AND password = %s"
        conn = self.get_connection()
        if not conn:
            return None
        try:
            with conn:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                    cur.execute(query, (username, password))
                    return cur.fetchone()
        except Exception as e:
            print(f"Login Query Error: {e}")
            return None
        finally:
            conn.close()

    def get_dashboard_stats(self):
        """Fetches counts. Returns zeros if query fails to prevent 500 error."""
        # IMPORTANT: Change 'customers' and 'loans' to match your actual table names
        query = """
            SELECT 
                (SELECT COUNT(*) FROM customers) as customers,
                (SELECT COUNT(*) FROM loans WHERE status = 'active') as active,
                (SELECT COUNT(*) FROM loans WHERE status = 'overdue') as critical,
                (SELECT COALESCE(SUM(amount), 0) FROM loans) as portfolio
        """
        default_stats = {'customers': 0, 'active': 0, 'critical': 0, 'portfolio': 0}
        conn = self.get_connection()
        if not conn:
            return default_stats
            
        try:
            with conn:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                    cur.execute(query)
                    res = cur.fetchone()
                    return res if res else default_stats
        except Exception as e:
            print(f"Stats Query Error: {e}")
            return default_stats
        finally:
            conn.close()
