import psycopg2
from psycopg2 import extras

class Database:
    def __init__(self, db_url):
        if db_url and db_url.startswith("postgres://"):
            self.db_url = db_url.replace("postgres://", "postgresql://", 1)
        else:
            self.db_url = db_url

    def get_connection(self):
        return psycopg2.connect(self.db_url)

    # --- USER AUTHENTICATION & ACCESS ---
    def get_user_by_username(self, username):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
                return cur.fetchone()
        except Exception as e:
            print(f"DB Error (Get User): {e}")
            return None
        finally:
            if conn: conn.close()

    # --- CUSTOMER MANAGEMENT ---
    def add_customer(self, id_number, first_name, last_name, phone, created_by):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO customers (id_number, first_name, last_name, phone, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                """, (id_number, first_name, last_name, phone, created_by))
                new_id = cur.fetchone()[0]
                conn.commit()
                return new_id
        except Exception as e:
            print(f"DB Error (Add Customer): {e}")
            if conn: conn.rollback()
            return None
        finally:
            if conn: conn.close()

    # --- LOAN ISSUANCE SYSTEM ---
    def create_loan(self, customer_id, first_name, last_name, loan_amount, loan_interest, loan_state='pending'):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # 1. Insert into loans table (amount_payable is generated automatically by PostgreSQL)
                cur.execute("""
                    INSERT INTO loans (customer_id, first_name, last_name, loan_amount, loan_interest, loan_state)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, amount_payable;
                """, (customer_id, first_name, last_name, loan_amount, loan_interest, loan_state))
                
                res = cur.fetchone()
                loan_id = res[0]
                amount_payable = res[1]

                # 2. If the loan state is instantly granted, set up the initial balance entry tracking
                if loan_state.lower() == 'granted':
                    cur.execute("""
                        INSERT INTO loan_balances (loan_id, status, amount_payable, paid, balance)
                        VALUES (%s, 'granted', %s, 0.00, %s);
                    """, (loan_id, amount_payable, amount_payable))
                
                conn.commit()
                return loan_id
        except Exception as e:
            print(f"DB Error (Create Loan): {e}")
            if conn: conn.rollback()
            return None
        finally:
            if conn: conn.close()

    # --- RECORD TRANSACTION PAYMENTS ---
    def process_payment(self, transaction_code, payment_amount, customer_id, loan_id):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # 1. Log the transaction into the log audit table
                cur.execute("""
                    INSERT INTO payment_transactions (transaction_code, payment_amount, customer_id, loan_id)
                    VALUES (%s, %s, %s, %s);
                """, (transaction_code.upper().strip(), payment_amount, customer_id, loan_id))

                # 2. Update the system balance ledger tracker dynamically
                cur.execute("""
                    UPDATE loan_balances
                    SET 
                        paid = paid + %s,
                        balance = balance - %s,
                        status = CASE WHEN (balance - %s) <= 0 THEN 'paid' ELSE status END,
                        updated_at = NOW()
                    WHERE loan_id = %s;
                """, (payment_amount, payment_amount, payment_amount, loan_id))

                # 3. Synchronize state status back to master loan ledger sheet
                cur.execute("""
                    UPDATE loans 
                    SET loan_state = CASE WHEN (SELECT balance FROM loan_balances WHERE loan_id = %s) <= 0 
                                     THEN 'paid' ELSE loan_state END
                    WHERE id = %s;
                """, (loan_id, loan_id))

                conn.commit()
                return True
        except Exception as e:
            print(f"DB Error (Process Payment): {e}")
            if conn: conn.rollback()
            return False
        finally:
            if conn: conn.close()

    # --- ANALYTICAL SYSTEM METRICS ---
    def get_dashboard_stats(self):
        conn = None
        stats = {'user_count': 0, 'active_loans': 0, 'total_loan_value': 0}
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                # Access Level Tracker Counter
                cur.execute("SELECT COUNT(*) as count FROM users")
                u_res = cur.fetchone()
                if u_res: stats['user_count'] = u_res['count']

                # Financial Risk Metrics Parser
                cur.execute("""
                    SELECT 
                        COUNT(*) as count, 
                        COALESCE(SUM(amount_payable), 0) as total 
                    FROM loans 
                    WHERE loan_state = 'granted'
                """)
                l_res = cur.fetchone()
                if l_res:
                    stats['active_loans'] = l_res['count']
                    stats['total_loan_value'] = l_res['total']
            return stats
        except Exception as e:
            print(f"DB Error (Stats Fetch): {e}")
            return stats
        finally:
            if conn: conn.close()
