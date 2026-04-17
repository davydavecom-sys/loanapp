import os
import psycopg2
from psycopg2 import extras
from cryptography.fernet import Fernet
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string

class LoanAppDB:
    def __init__(self):
        self.url = os.environ.get('DATABASE_URL')
        self.key = os.environ.get('ENCRYPTION_KEY').encode()
        self.cipher = Fernet(self.key)

    def get_connection(self):
        return psycopg2.connect(self.url)

    # --- ENCRYPTION TOOLS ---
    def encrypt_data(self, text):
        return self.cipher.encrypt(text.encode()).decode()

    def decrypt_data(self, encrypted_text):
        return self.cipher.decrypt(encrypted_text.encode()).decode()

    # --- CUSTOM ID GENERATORS ---
    def generate_payment_id(self):
        chars = string.ascii_uppercase + string.digits
        return f"P_{''.join(random.choice(chars) for _ in range(10))}"

    # --- AUTHENTICATION & RBAC ---
    def login_user(self, username, password):
        query = "SELECT id, username, password_hash, role FROM users WHERE username = %s"
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute(query, (username,))
                user = cur.fetchone()
                if user and check_password_hash(user['password_hash'], password):
                    return user
        return None

    # --- CUSTOMER REGISTRATION (Logic: C_0000001) ---
    def register_customer(self, first_name, last_name, id_num, phone, creator_id):
        # Secure the sensitive data
        enc_id = self.encrypt_data(id_num)
        enc_phone = self.encrypt_data(phone)
        
        query = """
            INSERT INTO personal_table (first_name, last_name, id_number, phone, created_by)
            VALUES (%s, %s, %s, %s, %s) RETURNING custom_id
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (first_name, last_name, enc_id, enc_phone, creator_id))
                    custom_id = cur.fetchone()[0]
                    conn.commit()
            return custom_id
        except Exception as e:
            print(f"Registration Error: {e}")
            return None

    # --- LOAN APPLICATION LOGIC (Logic: L_0000001 + Calculations) ---
    def apply_for_loan(self, customer_id, amount, return_date, rate_id):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Fetch current rate
                cur.execute("SELECT percentage FROM loan_rates WHERE id = %s", (rate_id,))
                rate_row = cur.fetchone()
                rate = float(rate_row[0]) if rate_row else 0.0

                # 2. Calculate Interest
                interest_amount = amount * (rate / 100)
                total_to_pay = amount + interest_amount

                # 3. Insert Application
                query = """
                    INSERT INTO loan_applications (
                        customer_id, amount_requested, interest_rate, 
                        interest_amount, total_to_pay, expected_return_date, 
                        application_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                    RETURNING loan_app_id
                """
                cur.execute(query, (customer_id, amount, rate, interest_amount, total_to_pay, return_date))
                app_id = cur.fetchone()[0]
                conn.commit()
                return app_id

    # --- DASHBOARD SUMMARY LOGIC ---
    def get_dashboard_stats(self):
        query = """
            SELECT 
                (SELECT COUNT(*) FROM personal_table) as customers,
                (SELECT COUNT(*) FROM loan_applications WHERE loan_status = 'active') as active,
                (SELECT COUNT(*) FROM loan_applications WHERE loan_status = 'active' AND expected_return_date < CURRENT_DATE) as critical,
                (SELECT COALESCE(SUM(total_to_pay), 0) FROM loan_applications WHERE loan_status IN ('active', 'due')) as portfolio
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute(query)
                return cur.fetchone()

    def record_payment(self, loan_id, amount, flutterwave_ref):
    # Requirement: Generate P_ + 10 character string
    payment_id = self.generate_payment_id() 
    
    query = """
        INSERT INTO payments (payment_id, loan_id, amount_paid, flutterwave_ref)
        VALUES (%s, %s, %s, %s);
    """
    try:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (payment_id, loan_id, amount, flutterwave_ref))
                
                # Check if loan is now fully cleared
                cur.execute("""
                    SELECT total_to_pay, (SELECT SUM(amount_paid) FROM payments WHERE loan_id = %s)
                    FROM loan_applications WHERE id = %s
                """, (loan_id, loan_id))
                res = cur.fetchone()
                if res[1] >= res[0]:
                    cur.execute("UPDATE loan_applications SET loan_status = 'cleared' WHERE id = %s", (loan_id,))
                
                conn.commit()
        return payment_id
    except Exception as e:
        print(f"Payment Error: {e}")
        return None


    def approve_loan(self, app_internal_id, approver_id):
    query = """
        UPDATE loan_applications 
        SET application_status = 'accepted', 
            loan_status = 'active',
            approved_by = %s,
            approved_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """
    try:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (approver_id, app_internal_id))
                conn.commit()
        return True
    except Exception as e:
        print(f"Approval Error: {e}")
        return False


    def update_loan_rate(self, new_percentage):
    # We update the 'is_active' status or just overwrite the main rate
    query = "UPDATE loan_rates SET percentage = %s WHERE id = (SELECT id FROM loan_rates LIMIT 1)"
    try:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (new_percentage,))
                conn.commit()
        return True
    except Exception as e:
        print(f"DB Error: {e}")
        return False
