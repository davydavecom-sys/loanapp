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
        # Initial default values
        stats = {'user_count': 0, 'active_loans': 0, 'total_loan_value': 0}
        
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                # 1. Count Users
                try:
                    cur.execute("SELECT COUNT(*) as count FROM users")
                    res = cur.fetchone()
                    stats['user_count'] = res['count'] if res else 0
                except:
                    conn.rollback() # Table might not exist yet

                # 2. Count Active Loans and Sum Amount
                try:
                    cur.execute("""
                        SELECT 
                            COUNT(*) as count, 
                            COALESCE(SUM(loan_amount), 0) as total 
                        FROM loans 
                        WHERE status = 'active'
                    """)
                    res = cur.fetchone()
                    if res:
                        stats['active_loans'] = res['count']
                        stats['total_loan_value'] = res['total']
                except:
                    conn.rollback() # Table might not exist yet

                return stats
        except Exception as e:
            print(f"General Dashboard Error: {e}")
            return stats
        finally:
            if conn:
                conn.close()


    def add_customer(self, first_name, last_name, phone_number, national_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # We combine names if your table has a single 'full_name' column
                full_name = f"{first_name} {last_name}"
                
                cur.execute("""
                    INSERT INTO customers (full_name, phone_number, national_id)
                    VALUES (%s, %s, %s)
                    RETURNING customer_id;
                """, (full_name, phone_number, national_id))
                
                customer_id = cur.fetchone()[0]
                conn.commit()
                return customer_id
        except Exception as e:
            print(f"Error adding customer: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()







