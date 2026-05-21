from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
import psycopg2
from psycopg2 import extras
import os

# -----------------------------------------------------------------------------
# 1. INITIALIZATION & CONFIGURATION
# -----------------------------------------------------------------------------
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "system_development_key_local_5541")

# Clean the DATABASE_URL environment variable for cloud hosting compatibility
raw_db_url = os.getenv("DATABASE_URL")
if raw_db_url and raw_db_url.startswith("postgres://"):
    DATABASE_URL = raw_db_url.replace("postgres://", "postgresql://", 1)
else:
    DATABASE_URL = raw_db_url

def get_db_connection():
    """Establishes an isolated atomic link connection to Supabase."""
    return psycopg2.connect(DATABASE_URL)


# -----------------------------------------------------------------------------
# 2. RAW DATABASE OPERATIONS & SQL CONTROLS
# -----------------------------------------------------------------------------

def get_user_by_username(username):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
            return cur.fetchone()
    except Exception as e:
        print(f"DB Error (Get User): {e}")
        return None
    finally:
        if conn: conn.close()

def add_customer(id_number, first_name, last_name, phone, created_by):
    conn = None
    try:
        conn = get_db_connection()
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

def create_loan(customer_id, first_name, last_name, loan_amount, loan_interest, loan_state='pending'):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Note: amount_payable is generated automatically by your PostgreSQL table formula
            cur.execute("""
                INSERT INTO loans (customer_id, first_name, last_name, loan_amount, loan_interest, loan_state)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, amount_payable;
            """, (customer_id, first_name, last_name, loan_amount, loan_interest, loan_state))
            
            res = cur.fetchone()
            loan_id = res[0]
            amount_payable = res[1]

            # If instantly granted, set up the initial tracking balance entry sheets
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

def process_payment(transaction_code, payment_amount, customer_id, loan_id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # 1. Log payment event to the audit ledger
            cur.execute("""
                INSERT INTO payment_transactions (transaction_code, payment_amount, customer_id, loan_id)
                VALUES (%s, %s, %s, %s);
            """, (transaction_code.upper().strip(), payment_amount, customer_id, loan_id))

            # 2. Adjust live systemic tracked remaining balances
            cur.execute("""
                UPDATE loan_balances
                SET 
                    paid = paid + %s,
                    balance = balance - %s,
                    status = CASE WHEN (balance - %s) <= 0 THEN 'paid' ELSE status END,
                    updated_at = NOW()
                WHERE loan_id = %s;
            """, (payment_amount, payment_amount, payment_amount, loan_id))

            # 3. Synchronize status back to master loan ledger records
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

def get_dashboard_stats():
    conn = None
    stats = {'user_count': 0, 'customer_count': 0, 'active_loans': 0, 'total_loan_value': 0.0}
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            
            # Fetch Officers Count
            try:
                cur.execute("SELECT COUNT(*)::integer as count FROM users")
                u_res = cur.fetchone()
                if u_res: stats['user_count'] = u_res['count']
            except Exception as ue:
                print(f"Stats User Query Failed: {ue}")

            # Fetch Onboarded Customers Count
            try:
                cur.execute("SELECT COUNT(*)::integer as count FROM customers")
                c_res = cur.fetchone()
                if c_res: stats['customer_count'] = c_res['count']
            except Exception as ce:
                print(f"Stats Customer Query Failed: {ce}")
                conn.rollback()

            # Fetch Financial Analytics Metrics
            try:
                cur.execute("""
                    SELECT 
                        COUNT(*)::integer as count, 
                        COALESCE(SUM(amount_payable), 0)::float as total 
                    FROM loans 
                    WHERE LOWER(loan_state) IN ('granted', 'active')
                """)
                l_res = cur.fetchone()
                if l_res:
                    stats['active_loans'] = l_res['count']
                    stats['total_loan_value'] = l_res['total']
            except Exception as le:
                print(f"Stats Loan Query Failed: {le}")
                
        return stats
    except Exception as e:
        print(f"Database Connection completely failed in stats: {e}")
        return stats
    finally:
        if conn: conn.close()


# -----------------------------------------------------------------------------
# 3. FLASK WEB APPLICATION ROUTING LAYER
# -----------------------------------------------------------------------------

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = get_user_by_username(username)
        
        if user and user['password'] == password:
            session['user'] = {
                'id': str(user['id']),
                'username': user['username'],
                'role': user['role']
            }
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid operational credentials supplied.", "danger")
            
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    stats_data = get_dashboard_stats()
    
    # Clean mapping casting layer to enforce type safety during template parsing
    safe_stats = {
        'user_count': int(stats_data.get('user_count', 0)),
        'customer_count': int(stats_data.get('customer_count', 0)),
        'active_loans': int(stats_data.get('active_loans', 0)),
        'total_loan_value': float(stats_data.get('total_loan_value', 0.0))
    }
    
    try:
        return render_template('dashboard.html', stats=safe_stats, current_user=session.get('user', {}))
    except Exception as template_err:
        print(f"Template Rendering Failed: {template_err}")
        return f"Dashboard loaded, but HTML rendering failed. Data: {safe_stats}", 500


@app.route('/customer/add', methods=['POST'])
def web_add_customer():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    id_number = request.form.get('id_number')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    phone = request.form.get('phone')
    created_by = session['user']['id']
    
    new_id = add_customer(id_number, first_name, last_name, phone, created_by)
    if new_id:
        flash("Customer profile added successfully!", "success")
    else:
        flash("Failed to add profile. Verify National ID unique constraints.", "danger")
        
    return redirect(url_for('dashboard'))


# --- SEPARATED LOAN APPLICATION WORKFLOW VIEWS ---

@app.route('/loan/apply', methods=['GET'])
def loan_apply_page():
    """Renders the dedicated standalone loan request view file page."""
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('apply_loan.html', current_user=session.get('user', {}))


@app.route('/loan/issue', methods=['POST'])
def web_issue_loan():
    """Processes the save button action data entries from apply_loan.html form."""
    if 'user' not in session:
        return redirect(url_for('login'))
        
    customer_id = request.form.get('customer_id')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    loan_amount = float(request.form.get('loan_amount', 0))
    loan_interest = float(request.form.get('loan_interest', 0))
    loan_state = request.form.get('loan_state', 'pending')
    
    loan_id = create_loan(customer_id, first_name, last_name, loan_amount, loan_interest, loan_state)
    if loan_id:
        flash(f"Loan record successfully saved with state: {loan_state}!", "success")
    else:
        flash("Failed to register loan entry. Verify Customer UUID exists.", "danger")
        
    return redirect(url_for('dashboard'))


@app.route('/payment/receive', methods=['POST'])
def web_receive_payment():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    transaction_code = request.form.get('transaction_code')
    payment_amount = float(request.form.get('payment_amount', 0))
    customer_id = request.form.get('customer_id')
    loan_id = request.form.get('loan_id')
    
    success = process_payment(transaction_code, payment_amount, customer_id, loan_id)
    if success:
        flash(f"Payment processed successfully! Code: {transaction_code.upper()}", "success")
    else:
        flash("Failed to log transaction. Check for duplicate M-Pesa codes.", "danger")
        
    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
