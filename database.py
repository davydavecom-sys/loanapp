import psycopg2
from psycopg2 import extras
from psycopg2.extras import RealDictCursor

class LoanAppDB:
    def __init__(self):
        self.conn_params = {
            "dbname": "loanapp", 
            "user": "postgres",
            "password": "kuku",
            "host": "localhost",
            "port": "5432"
        }
        try:
            # We keep one persistent connection for simple counts
            self.conn = psycopg2.connect(**self.conn_params)
            print("Database connection successful!")
        except Exception as e:
            print(f"Error connecting to database: {e}")
            self.conn = None

    def get_connection(self):
        """Returns a new connection for with-block usage (auto-closes)"""
        return psycopg2.connect(**self.conn_params)

    # --- USER AUTHENTICATION ---
    def get_user_by_username(self, username):
        try:
            # Use the persistent connection for quick lookups
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                return cursor.fetchone()
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            print(f"Error fetching user: {e}")
            return None

    # --- CUSTOMER MANAGEMENT ---
    def add_customer(self, first, last, nat_id, phone, location):
        # I updated the query to match the 'location' field we added to your form
        query = """
            INSERT INTO PERSONAL_TABLE (first_name, last_name, id_number, phone, location)
            VALUES (%s, %s, %s, %s, %s) RETURNING id;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (first, last, nat_id, phone, location))
                new_id = cur.fetchone()[0]
                conn.commit()
                return new_id

    # --- LOAN MANAGEMENT ---
    def apply_loan(self, customer_id, amount, period, interest):
        query = """
            INSERT INTO LOAN_APPLICATIONS (customer_id, loan_amount, period, interest_rate)
            VALUES (%s, %s, %s, %s) RETURNING loan_id;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (customer_id, amount, period, interest))
                loan_id = cur.fetchone()[0]
                conn.commit()
                return loan_id

    def review_loan(self, loan_id, new_status):
        query = "UPDATE LOAN_APPLICATIONS SET loan_status = %s WHERE loan_id = %s;"
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (new_status, loan_id))
                conn.commit()

    # --- DASHBOARD STATS ---
    def get_total_customers_count(self):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM PERSONAL_TABLE;")
                result = cursor.fetchone()
                return result[0] if result else 0
        except:
            return 0

    def get_active_loans_count(self):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM LOAN_APPLICATIONS WHERE status = 'active';")
                result = cursor.fetchone()
                return result[0] if result else 0
        except:
            return 0

    def get_overdue_loans_count(self):
        try:
            with self.conn.cursor() as cursor:
                query = "SELECT COUNT(*) FROM LOAN_APPLICATIONS WHERE deadline < CURRENT_DATE AND status != 'paid';"
                cursor.execute(query)
                result = cursor.fetchone()
                return result[0] if result else 0
        except:
            return 0

    # --- REPORTS ---
    def get_unpaid_loans(self):
        query = "SELECT * FROM ALERT_REPORT;"
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute(query)
                return cur.fetchall()