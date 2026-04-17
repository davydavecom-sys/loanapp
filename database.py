import os
import psycopg2
from psycopg2 import extras

class LoanAppDB:
    def __init__(self):
        self.url = os.environ.get('DATABASE_URL')

    def get_connection(self):
        try:
            # The .url must be your port 6543 string from Supabase
            return psycopg2.connect(self.url)
        except Exception as e:
            # CHECK RENDER LOGS FOR THIS PRINT
            print(f"CRITICAL DATABASE ERROR: {e}")
            return None

    def get_user_by_username(self, username):
        """Updated to use password_hash column name"""
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
            if conn:
                conn.close()

    def get_dashboard_stats(self):
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
            if conn:
                conn.close()
