from database import LoanAppDB
from functools import wraps
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
db = LoanAppDB()

app.secret_key = 'beauty'

# --- ACCESS CONTROL DECORATORS ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            return "Access Denied!", 403
        return f(*args, **kwargs)
    return decorated_function

# --- AUTH ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = db.get_user_by_username(username)
        
        if user and str(user.get('password_hash')).strip() == str(password).strip():
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('home'))
        else:
            flash("Invalid username or password")
            return redirect(url_for('login'))

    return render_template('login.html')    

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- MAIN DASHBOARD ---

@app.route('/')
@login_required
def home():
    stats_data = {
        "total_customers": db.get_total_customers_count(),
        "active_loans": db.get_active_loans_count(),
        "pending": db.get_overdue_loans_count() # Using this for the 'Pending' card
    }
    # In a real app, you'd also fetch 'recent customers' here to show in the table
    return render_template('index.html', stats=stats_data, customers=[])

# --- CUSTOMER & LOAN ACTIONS ---

@app.route('/add_customer', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        # Get data from HTML Form (matches the 'name' attributes in your HTML)
        first = request.form.get('first_name')
        last = request.form.get('last_name')
        nat_id = request.form.get('id_number')
        phone = request.form.get('phone')
        location = request.form.get('location')

        success = db.add_customer(first, last, nat_id, phone, location)
        
        if success:
            flash("Customer added successfully!")
            return redirect(url_for('home'))
        else:
            flash("Error adding customer. Check if ID already exists.")
            
    return render_template('add_customer.html')

@app.route('/apply_loan', methods=['GET', 'POST'])
@login_required
def apply_loan():
    if request.method == 'POST':
        # Get data from the form
        customer_id = request.form.get('customer_id')
        amount = request.form.get('amount')
        period = request.form.get('period')
        interest = request.form.get('interest')

        # Save to DB using your existing apply_loan function
        loan_id = db.apply_loan(customer_id, amount, period, interest)
        
        if loan_id:
            flash(f"Success! Loan Application #{loan_id} has been submitted.")
            return redirect(url_for('home'))
        else:
            flash("Error: Could not process loan application.")

    # For the GET request, we need a list of customers for the dropdown
    # You might need to add a 'get_all_customers' method to database.py
    with db.get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT customer_id, first_name, last_name, id_number FROM PERSONAL_TABLE ORDER BY last_name ASC")
            customers = cur.fetchall()

    return render_template('apply_loan.html', customers=customers)

#approve loan
@app.route('/approve_loan', methods=['GET', 'POST'])
@login_required
def approve_loan():
    if request.method == 'POST':
        loan_id = request.form.get('loan_id')
        status = request.form.get('status')
        db.review_loan(loan_id, status)
        flash(f"Loan #{loan_id} has been {status}.")
        return redirect(url_for('approve_loan'))
    
    # Fetch only pending loans
    with db.get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT l.loan_id, c.first_name, c.last_name, l.loan_amount FROM LOAN_APPLICATIONS l JOIN PERSONAL_TABLE c ON l.customer_id = c.id WHERE l.status = 'pending'")
            pending = cur.fetchall()
    return render_template('approve_loan.html', loans=pending)

# --- REPORTS ---

@app.route('/reports/unpaid')
@login_required
def unpaid_report():
    report = db.get_unpaid_loans()
    return render_template('reports.html', report=report)

# --- APP START ---

if __name__ == '__main__':
    app.run(debug=True)            
