from flask import Flask, render_template, request, redirect, url_for, flash, session
from database import LoanAppDB
from functools import wraps
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_key_123')

# Initialize our Database Engine
db = LoanAppDB()

# --- SECURITY DECORATORS ---
def roles_allowed(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                flash("Please log in first.")
                return redirect(url_for('login'))
            if session['user']['role'] not in roles:
                flash("Access Denied: You do not have the required permissions.")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- AUTHENTICATION ---
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = db.login_user(username, password)
        
        if user:
            # 1. Save the whole user object if you need it later
            session['user'] = user 
            
            # 2. Extract and save the role specifically for the decorator
            # This ensures @roles_allowed can find session['role']
            session['role'] = user['role'] 
            
            # 3. Optional: Save the user ID for database queries
            session['user_id'] = user['id']
            
            return redirect(url_for('dashboard'))
            
        flash("Invalid credentials.")
    return render_template('login.html')



@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- DASHBOARD ---
@app.route('/dashboard')
@roles_allowed('admin', 'marketer', 'approver', 'reporter')
def dashboard():
    stats = db.get_dashboard_stats()
    return render_template('dashboard.html', stats=stats)

# --- CUSTOMER REGISTRATION (Logic: C_0000001) ---
@app.route('/register-customer', methods=['GET', 'POST'])
@roles_allowed('admin', 'marketer')
def register_customer():
    if request.method == 'POST':
        cust_id = db.register_customer(
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            id_num=request.form.get('id_number'),
            phone=request.form.get('phone'),
            creator_id=session['user']['id']
        )
        if cust_id:
            flash(f"Customer Registered successfully! ID: {cust_id}")
            return redirect(url_for('dashboard'))
    return render_template('register_customer.html')

# --- LOAN APPLICATION (Logic: L_0000001) ---
@app.route('/apply-loan', methods=['GET', 'POST'])
@roles_allowed('admin', 'marketer')
def apply_loan():
    customers = db.get_all_customers()
    rate = db.get_active_rate()
    
    if request.method == 'POST':
        cust_id = request.form.get('customer_id')
        amount = float(request.form.get('amount'))
        return_date = request.form.get('return_date')
        
        # Check for Wallet Credit (Offsetting)
        wallet_credit = db.get_wallet_balance(cust_id)
        final_principal = amount - wallet_credit
        
        loan_id = db.apply_for_loan(
            customer_id=cust_id,
            amount=final_principal,
            return_date=return_date,
            rate_id=rate['id']
        )
        
        if wallet_credit > 0:
            db.record_wallet_usage(cust_id, loan_id, wallet_credit)
            
        flash(f"Application {loan_id} submitted and pending verification.")
        return redirect(url_for('dashboard'))
        
    return render_template('apply_loan.html', customers=customers, rate=rate)

# --- VERIFICATION & APPROVAL ---
@app.route('/verify-loans')
@roles_allowed('admin', 'approver')
def verify_loans():
    pending = db.get_pending_applications()
    return render_template('verify_loans.html', loans=pending)

@app.route('/process-approval/<int:id>/<action>')
@roles_allowed('admin', 'approver')
def process_approval(id, action):
    status = 'accepted' if action == 'accept' else 'denied'
    db.update_application_status(id, status, session['user']['id'])
    flash(f"Loan Application {status.upper()}.")
    return redirect(url_for('verify_loans'))

# --- BALANCES & PAYMENTS (P_XXXXXXXXXX) ---
@app.route('/balances')
@roles_allowed('admin', 'marketer', 'approver', 'reporter')
def balances():
    unpaid = db.get_unpaid_loans()
    return render_template('balances.html', loans=unpaid, today=datetime.now().date())

@app.route('/pay-loan/<int:id>', methods=['GET', 'POST'])
@roles_allowed('admin', 'marketer', 'approver')
def pay_loan(id):
    loan_data = db.get_loan_details(id)
    if request.method == 'POST':
        amt = float(request.form.get('amount'))
        if amt > loan_data['balance']:
            flash("Error: Payment exceeds outstanding balance.")
        else:
            # Trigger Flutterwave Redirect Logic here
            # On success, db.record_payment(...) generates the P_ ID
            flash("Redirecting to Payment Gateway...")
    return render_template('pay_loan.html', loan=loan_data)

# --- CONTROL PANEL (ADMIN ONLY) ---
@app.route('/settings')
@roles_allowed('admin')
def settings():
    rate = db.get_active_rate()
    return render_template('settings.html', current_rate=rate)

@app.route('/update-rate', methods=['POST'])
@roles_allowed('admin')
def update_rate():
    new_rate = request.form.get('new_rate')
    if db.update_loan_rate(new_rate):
        flash(f"Interest Rate successfully updated to {new_rate}%")
    return redirect(url_for('settings'))

if __name__ == '__main__':
    app.run(debug=True)
