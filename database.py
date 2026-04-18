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
                # 1. Get staff user count
                cur.execute("SELECT COUNT(*) as count FROM users")
                u_res = cur.fetchone()
                if u_res: stats['user_count'] = u_res['count']

                # 2. Get loan stats from loan_applications
                # Using COALESCE to ensure we don't return 'None' to Flask
                cur.execute("""
                    SELECT 
                        COUNT(*) as count, 
                        COALESCE(SUM(loan_amount), 0) as total 
                    FROM loan_applications 
                    WHERE status = 'approved' OR status = 'active'
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

    def add_customer(self, first_name, last_name, phone, id_number, created_by):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # Matches your columns: first_name, last_name, phone, id_number, created_by
                cur.execute("""
                    INSERT INTO personal_table (first_name, last_name, phone, id_number, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                """, (first_name, last_name, phone, id_number, created_by))
                
                new_id = cur.fetchone()[0]
                conn.commit()
                return new_id
        except Exception as e:
            print(f"Add Customer Error: {e}")
            if conn: conn.rollback()
            return None
        finally:
            if conn:
                conn.close()
