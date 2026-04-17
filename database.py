import os
import psycopg2
from psycopg2 import extras
from dotenv import load_dotenv

load_dotenv()

class LoanAppDB:
    def __init__(self):
        # This will pull from your Render Environment Variables
        self.url = os.environ.get('DATABASE_URL')

    def get_connection(self):
        """Establishes connection to Supabase."""
        try:
            return psycopg2.connect(self.url)
        except Exception as e:
            print(f"CRITICAL: Database connection failed: {e}")
            return None

    def login_user(self, username, password):
        """Checks credentials and returns user dict."""
        query = "SELECT id, username, role FROM users WHERE username = %s AND password = %s"
        conn = self.get_connection()
        if not conn:
            return None
            
        try:
            with conn:
                # RealDictCursor allows you to use user['role'] in app.py
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                    cur.execute(query, (username, password))
                    return cur.fetchone()
        except Exception as e:
            print(f"Login Error: {e}")
            return None
        finally:
            conn.close()

    def get_dashboard_stats(self):
        """Fetches counts for the dashboard cards."""
        query = """
            SELECT 
                (SELECT COUNT(*) FROM customers) as customers,
                (SELECT COUNT(*) FROM loans WHERE status = 'active') as active,
                (SELECT COUNT(*) FROM loans WHERE status = 'overdue') as critical,
                (SELECT COALESCE(SUM(amount), 0) FROM loans) as portfolio
        """
        conn = self.get_connection()
        if not conn:
            return {'customers': 0, 'active': 0, 'critical': 0, 'portfolio': 0}

        try:
            with conn:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                    cur.execute(query)
                    result = cur.fetchone()
                    return result if result else {'customers': 0, 'active': 0, 'critical': 0, 'portfolio': 0}
        except Exception as e:
            print(f"Stats Error: {e}")
            return {'customers': 0, 'active': 0, 'critical': 0, 'portfolio': 0}
        finally:
            conn.close()
