import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import LoanAppDB
from werkzeug.security import check_password_hash

app = Flask(__name__)
# Ensure this key is set in your Render Environment Variables
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_key_meru_2026')

db = LoanAppDB()

@app.route('/')
def index():
    """Directs users to login page immediately."""
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 1. Fetch the user by username only
        user = db.get_user_by_username(username)
        
        # 2. Check if user exists AND if the password hash matches
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            return redirect('/dashboard')
            
        flash("Invalid credentials", "danger")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    # Simple login check
    if 'user_id' not in session:
        return redirect('/login')
    
    stats = db.get_dashboard_stats()
    return render_template('dashboard.html', stats=stats)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    # Render sets the PORT automatically
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
