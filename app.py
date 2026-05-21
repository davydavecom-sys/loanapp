from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
import psycopg2
from psycopg2 import extras
import os
import base64
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth

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
# 2. MPESA DARAJA INTEGRATION HELPERS
# -----------------------------------------------------------------------------

def get_mpesa_access_token():
    """Fetches a secure OAuth authentication token from Safaricom Daraja."""
    consumer_key = os.getenv("MPESA_CONSUMER_KEY")
    consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")
    api_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    
    try:
        res = requests.get(api_url, auth=HTTPBasicAuth(consumer_key, consumer_secret), timeout=10)
        if res.status_code == 200:
            return res.json().get("access_token")
    except Exception as e:
        print(f"Failed to fetch M-Pesa token: {e}")
    return None

def initiate_stk_push(phone_number, amount, loan_id, customer_id):
    """Triggers an STK Push toolkit PIN popup menu to the client's phone handset."""
    access_token = get_mpesa_access_token()
    if not access_token:
        return False
        
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    
    business_shortcode = os.getenv("MPESA_SHORTCODE")
    passkey = os.getenv("MPESA_PASSKEY")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Create Daraja Password hash layer string
    password_str = f"{business_shortcode}{passkey}{timestamp}"
    password = base64.b64encode(password_str.encode()).decode("utf-8")
    
    # Format phone format systematically from 07... to 2547...
    if phone_number.startswith("0"):
        phone_number = "254" + phone_number[1:]
    elif phone_number.startswith("+254"):
        phone_number = phone_number[1:]
        
    payload = {
        "BusinessShortCode": business_shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone_number,
        "PartyB": business_shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": os.getenv("MPESA_CALLBACK_URL"),
        "AccountReference": f"LN-{loan_id[:6].upper()}",
        "TransactionDesc": f"Payment For Loan ID {loan_id[:6]}"
    }
    
    try:
        res = requests.post(api_url, json=payload, headers=headers, timeout=15)
        print(f"Daraja Gateway Raw Outbound Broadcast Response: {res.text}")
        if res.status_code == 200 and res.json().get("ResponseCode") == "0":
            return True
    except Exception as e:
        print(f"Daraja API Outbound Post Exception Failure: {e}")
    return False


# -----------------------------------------------------------------------------
# 3. RAW DATABASE OPERATIONS & SQL CONTROLS
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
            cur.execute("""
                INSERT INTO loans (customer_id, first_name, last_name, loan_amount, loan_interest, loan_state)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, amount_payable;
            """, (customer_id, first_name, last_name, loan_amount, loan_interest, loan_state))
            
            res = cur.fetchone()
            loan_id = res[0]
            amount_payable = res[1]

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

def get_pending_loans():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, customer_id, first_name, last_name, loan_amount, loan_interest, 
                       (loan_amount + loan_interest)::float as amount_payable, created_at
                FROM loans 
                WHERE LOWER(loan_state) = 'pending'
                ORDER BY created_at DESC;
            """)
            return cur.fetchall()
    except Exception as e:
        print(f"DB Error (Get Pending Loans): {e}")
        return []
    finally:
        if conn: conn.close()

def update_loan_state(loan_id, new_state):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE loans 
                SET loan_state = %s 
                WHERE id = %s 
                RETURNING id, loan_amount, loan_interest;
            """, (new_state, loan_id))
            
            row = cur.fetchone()
            if row and new_state == 'granted':
                loan_amount = float(row[1])
                loan_interest = float(row[2])
                amount_payable = loan_amount + loan_interest
                
                cur.execute("""
                    INSERT INTO loan_balances (loan_id, status, amount_payable, paid, balance)
                    VALUES (%s, 'granted', %s, 0.00, %s)
                    ON CONFLICT (loan_id) DO NOTHING;
                """, (loan_id, amount_payable, amount_payable))
                
            conn.commit()
            return True
    except Exception as e:
        print(f"DB Error (Update Loan State): {e}")
        if conn: conn.rollback()
        return False
    finally:
        if conn: conn.close()

def process_payment(transaction_code, payment_amount, customer_id, loan_id):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO payment_transactions (transaction_code, payment_amount, customer_id, loan_id)
                VALUES (%s, %s, %s, %s);
            """, (transaction_code.upper().strip(), payment_amount, customer_id, loan_id))

            cur.execute("""
                UPDATE loan_balances
                SET 
                    paid = paid + %s,
                    balance = balance - %s,
                    status = CASE WHEN (balance - %s) <= 0 THEN 'paid' ELSE status END,
                    updated_at = NOW()
                WHERE loan_id = %s;
            """, (payment_amount, payment_amount, payment_amount, loan_id))

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
            
            try:
                cur.execute("SELECT COUNT(*)::integer as count FROM users")
                u_res = cur.fetchone()
                if u_res: stats['user_count'] = u_res['count']
            except Exception as ue:
                print(f"Stats User Query Failed: {ue}")

            try:
                cur.execute("SELECT COUNT(*)::integer as count FROM customers")
                c_res = cur.fetchone()
                if c_res: stats['customer_count'] = c_res['count']
            except Exception as ce:
                print(f"Stats Customer Query Failed: {ce}")

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
# 4. FLASK WEB APPLICATION ROUTING LAYER
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


@app.route('/loan/apply', methods=['GET'])
def loan_apply_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('apply_loan.html', current_user=session.get('user', {}))


@app.route('/loan/issue', methods=['POST'])
def web_issue_loan():
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


@app.route('/loans/pending', methods=['GET'])
def pending_loans_page():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    pending_list = get_pending_loans()
    return render_template('pending_loans.html', loans=pending_list, current_user=session.get('user', {}))


@app.route('/loan/review/<uuid:loan_id>/<string:action>', methods=['POST'])
def review_loan_action(loan_id, action):
    if 'user' not in session:
        return redirect(url_for('login'))
        
    new_state = 'granted' if action == 'approve' else 'rejected'
    success = update_loan_state(str(loan_id), new_state)
    if success:
        flash(f"Loan account status successfully changed to: {new_state.upper()}", "success")
    else:
        flash("Failed to update the state of this loan account request.", "danger")
        
    return redirect(url_for('pending_loans_page'))


@app.route('/payment/receive', methods=['POST'])
def web_receive_payment():
    """Triggers an automated M-Pesa STK Push request to the customer phone."""
    if 'user' not in session:
        return redirect(url_for('login'))
        
    payment_amount = float(request.form.get('payment_amount', 0))
    customer_id = request.form.get('customer_id')
    loan_id = request.form.get('loan_id')
    
    phone = None
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT phone FROM customers WHERE id = %s", (customer_id,))
            res = cur.fetchone()
            if res: phone = res[0]
    except Exception as e:
        print(f"Error fetching client phone: {e}")
    finally:
        if conn: conn.close()
        
    if not phone:
        flash("Could not trace customer profile or phone contacts in records.", "danger")
        return redirect(url_for('dashboard'))
        
    success = initiate_stk_push(phone, payment_amount, loan_id, customer_id)
    if success:
        flash(f"STK Push initiated successfully to {phone}! Awaiting customer PIN entry.", "success")
    else:
        flash("Failed to broadcast handshake message to Daraja API Gateway.", "danger")
        
    return redirect(url_for('dashboard'))


@app.route('/mpesa/callback', methods=['POST'])
def mpesa_callback():
    """Webhook listener catching Safaricom payload confirmation configurations."""
    data = request.get_json()
    print(f"Inbound Safaricom Callback Data Payload Received: {data}")
    try:
        stk_callback = data['Body']['stkCallback']
        result_code = stk_callback['ResultCode']
        if result_code == 0:
            callback_metadata = stk_callback['CallbackMetadata']['Item']
            amount = 0
            mpesa_code = ""
            for item in callback_metadata:
                if item['Name'] == 'Amount': amount = float(item['Value'])
                elif item['Name'] == 'MpesaReceiptNumber': mpesa_code = str(item['Value'])
            print(f"SUCCESSFUL AUTOMATED INTERACTION PAY: Code={mpesa_code}, Amt={amount}")
    except Exception as e:
        print(f"Error compiling inbound Safaricom callback loop data structures: {e}")
    return {"ResultCode": 0, "ResultDesc": "Confirmation received successfully"}, 200


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
