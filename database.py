import psycopg2
from psycopg2 import extras
import os

class Database:
    def __init__(self, db_url):
        # Ensure the URL is clean. Render/Supabase sometimes need 'postgresql://'
        if db_url and db_url.startswith("postgres://"):
            self.db_url = db_url.replace("postgres://", "postgresql://", 1)
        else:
            self.db_url = db_url

    def get_connection(self):
        # Direct connection without extra logic to prevent recursion
        return psycopg2.connect(self.db_url)

    def get_user_by_username(self, username):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
                return cur.fetchone()
        except Exception as e:
            print(f"Login Error: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_dashboard_stats(self):
        conn = None
        stats = {'user_count': 0, 'active_loans': 0, 'total_loan_value': 0}
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                # Get user count
                cur.execute("SELECT COUNT(*) as count FROM users")
                u_res = cur.fetchone()
                if u_res: stats['user_count'] = u_res['count']

                # Get loan stats - COALESCE prevents 'None' errors
                cur.execute("""
                    SELECT 
                        COUNT(*) as count, 
                        COALESCE(SUM(loan_amount), 0) as total 
                    FROM loans 
                    WHERE status = 'active'
                """)
                l_res = cur.fetchone()
                if l_res:
                    stats['active_loans'] = l_res['count']
                    stats['total_loan_value'] = l_res['total']
                    
            return stats
        except Exception as e:
            print(f"Dashboard Stats Error: {e}")
            return stats
        finally:
            if conn:
                conn.close()

    def add_customer(self, first_name, last_name, phone_number, national_id):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                full_name = f"{first_name} {last_name}"
                cur.execute("""
                    INSERT INTO customers (full_name, phone_number, national_id)
                    VALUES (%s, %s, %s)
                    RETURNING customer_id;
                """, (full_name, phone_number, national_id))
                cust_id = cur.fetchone()[0]
                conn.commit()
                return cust_id
        except Exception as e:
            print(f"Add Customer Error: {e}")
            if conn: conn.rollback()
            return None
        finally:
            if conn:
                conn.close()
