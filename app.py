from functools import wraps
from flask import session, redirect, url_for, flash

# Security Decorator: Checks if user is logged in and has the right role
def roles_allowed(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            if session['user']['role'] not in roles:
                flash("Unauthorized Access: You do not have permission for this section.")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Example Usage:
# @app.route('/settings')
# @roles_allowed('admin')
# def settings(): ...


@app.route('/dashboard')
@roles_allowed('admin', 'marketer', 'approver', 'reporter')
def dashboard():
    # Fetch stats from the DB method we created earlier
    stats = db.get_dashboard_stats()
    
    # Logic for "Critical Loans" alert
    critical_list = db.get_critical_loans() # We'll add this method next
    
    return render_template('dashboard.html', stats=stats, critical=critical_list)








