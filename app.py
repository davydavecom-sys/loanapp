import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from database import LoanAppDB

app = Flask(__name__)
# Ensure FLASK_SECRET_KEY is set in Render Environment
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key_meru')

db = LoanAppDB()

@app.route('/')
def index():
    """Redirects visitors to the login page."""
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = db.get_user_by_username(username)
        
        # Verify the password against the hash stored in Supabase
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            # Using direct string redirect to bypass BuildErrors
            return redirect('/dashboard')
            
        flash("Invalid username or password.", "danger")
        
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """Main dashboard view, protected by login check."""
    if 'user_id' not in session:
        return redirect('/login')
    
    stats = db.get_dashboard_stats()
    return render_template('dashboard.html', stats=stats)

@app.route('/logout')
def logout():
    """Clears session and logs user out."""
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    # Render provides the PORT dynamically
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
