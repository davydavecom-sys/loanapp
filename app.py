from flask import Flask, render_template, request, redirect, session, flash
from database import Database
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'meru_dev_2026')

# Initialize Database
db = Database(os.environ.get('DATABASE_URL'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password_attempt = request.form.get('password')

        user = db.get_user_by_username(username)

        # PLAIN TEXT CHECK:
        # We check if the user exists and if the stored 'password_hash' 
        # matches the typed password exactly.
        if user and user['password_hash'] == password_attempt:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect('/dashboard')
        else:
            flash("Invalid username or password", "danger")
            
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    stats = db.get_dashboard_stats()
    return render_template('dashboard.html', stats=stats)

if __name__ == '__main__':
    app.run(debug=True)
@app.route('/')
def index():
    return redirect('/login')
