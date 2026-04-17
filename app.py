from flask import Flask, render_template, request, redirect, session, flash, url_for
from database import Database
import os

app = Flask(__name__)

# Security: Using a default for local dev, but Render will use the Environment Variable
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'meru_dev_secret_2026')

# Initialize Database with the Supabase URL from Render Environment Variables
db_url = os.environ.get('DATABASE_URL')
db = Database(db_url)

@app.route('/')
def index():
    """Redirects the main URL to the login page."""
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password_attempt = request.form.get('password')

        user = db.get_user_by_username(username)

        # PLAIN TEXT CHECK (for debugging/initial setup)
        if user and user['password_hash'] == password_attempt:
            # We store the data in a 'user' dictionary to match your HTML:
            # {{ session['user']['username'] }}
            session['user'] = {
                'id': user['id'],
                'username': user['username'],
                'role': user['role']
            }
            # Also keeping flat keys just in case other parts of your code use them
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password. Please try again.", "danger")
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    # Security check: If the 'user' key isn't in session, they aren't logged in
    if 'user' not in session:
        return redirect(url_for('login'))
    
    try:
        stats = db.get_dashboard_stats()
        return render_template('dashboard.html', stats=stats)
    except Exception as e:
        print(f"Dashboard Error: {e}")
        return "Internal Server Error", 500

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Use environment port for Render compatibility
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
