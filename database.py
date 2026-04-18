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
        default_stats = {'user_count': 0, 'active_loans': 0, 'total_loan_value': 0}
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                # Get count of users
                cur.execute("SELECT COUNT(*) as user_count FROM users")
                users = cur.fetchone()

                # Get count of active loans and total amount from the 'loans' table
                # Assuming 'status' column exists based on your schema
                cur.execute("""
                    SELECT 
                        COUNT(*) as active_loans, 
                        SUM(loan_amount) as total_value 
                    FROM loans 
                    WHERE status = 'active'
                """)
                loans = cur.fetchone()

                return {
                    'user_count': users['user_count'] if users else 0,
                    'active_loans': loans['active_loans'] if loans else 0,
                    'total_loan_value': loans['total_value'] if loans['total_value'] else 0
                }
        except Exception as e:
            print(f"Dashboard Query Error: {e}")
            return default_stats
                print(f"Dashboard Query Error: {e}")
                return default_stats
            finally:
                conn.close()
