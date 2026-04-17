import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from database import LoanAppDB
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key_123')

# Initialize Database
db = LoanAppDB()

# --- SECURITY DECORATOR ---
def roles_allowed(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if user is logged in
            if 'role' not in session:
                return redirect(url_for('login'))
            
            # Check if user role is in the allowed list
            if session.get('role') not in roles:
                # Use abort(403) instead of a redirect to avoid 404 BuildErrors
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

# --- ROUTES ---

@app.route('/')
def index():
    """Redirects the root URL to the login page."""
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = db.login_user(username, password)
        
        if user:
            # CRITICAL FIX: Save the role specifically for the decorator
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            return redirect(url_for('dashboard'))
            
        flash("Invalid username or password.", "danger")
    
    return render_template('login.html')

@app.route('/dashboard')
@roles_allowed('admin', 'marketer', 'approver', 'reporter')
def dashboard():
    try:
        stats = db.get_dashboard_stats()
        # Ensure stats isn't None to prevent template errors
        if not stats:
            stats = {'customers': 0, 'active': 0, 'critical': 0, 'portfolio': 0}
            
        return render_template('dashboard.html', stats=stats)
    except Exception as e:
        print(f"Dashboard Load Error: {e}")
        # Fallback to zeros if the database connection blips
        empty_stats = {'customers': 0, 'active': 0, 'critical': 0, 'portfolio': 0}
        return render_template('dashboard.html', stats=empty_stats)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ERROR HANDLERS ---

@app.errorhandler(403)
def forbidden(e):
    return "<h1>403 Forbidden</h1><p>You do not have permission to view this page.</p>", 403

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404 Not Found</h1><p>The page you are looking for does not exist.</p>", 404

if __name__ == '__main__':
    # Use port 5000 for local development, Render will override this automatically
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
