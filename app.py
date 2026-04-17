import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import LoanAppDB

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
        
        user = db.login_user(username, password)
        
        if user:
            # Saving user info to session
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            # Direct string redirect to prevent BuildErrors
            return redirect('/dashboard')
            
        flash("Invalid credentials. Please try again.", "danger")
        
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
