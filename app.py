import os
from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import check_password_hash
from database import LoanAppDB

# --- CRITICAL FOR RENDER ---
# This variable must be named 'app' and be at the top level
app = Flask(__name__)

# Ensure you have 'FLASK_SECRET_KEY' set in Render Environment Variables
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'meru_dev_secure_key_2026')

# Initialize the database helper
db = LoanAppDB()

@app.route('/')
def index():
    """Redirects the root URL to the login page."""
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Fetch the user record from the 'users' table in Supabase
        user = db.get_user_by_username(username)
        
        # We use 'password_hash' because that is your database column name
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            # Direct string redirect to avoid URL building errors on Render
            return redirect('/dashboard')
            
        flash("Invalid username or password.", "danger")
        
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """Main dashboard view. Protected by session check."""
    if 'user_id' not in session:
        return redirect('/login')
    
    # Fetches counts for customers, loans, etc.
    stats = db.get_dashboard_stats()
    return render_template('dashboard.html', stats=stats)

@app.route('/logout')
def logout():
    """Clears the session and sends the user back to login."""
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    # Local development settings
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
