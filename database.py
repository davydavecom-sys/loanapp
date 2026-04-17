import os
import psycopg2
from psycopg2 import extras

class LoanAppDB:
    def __init__(self):
        # This pulls the DATABASE_URL from your Render Environment Variables
        self.url = os.environ.get('DATABASE_URL')

    def get_connection(self):
        """Establishes connection to Supabase using the Transaction Pooler."""
        try:
            return psycopg2.connect(self.url)
        except Exception as e:
            print(f"Database Connection Error: {e}")
            return None

    def get_user_by_username(self, username):
    # Changed 'password' to 'password_hash'
    query = "SELECT id, username, password_hash, role FROM users WHERE username = %s"
    conn = self.get_connection()
    if not conn:
        return None
    try:
        with conn:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute(query, (username,))
                return cur.fetchone()
    except Exception as e:
        print(f"Query Error (get_user): {e}")
        return None
    finally:
        conn.close()

    def get_dashboard_stats(self):
        """Fetches counts for dashboard. Returns zeros on error to prevent 500 crash."""
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
            print(f"Query Error (stats): {e}")
            return default_stats
        finally:
            conn.close()
