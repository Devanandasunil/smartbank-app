# app/decorators.py
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user

def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:  # Check authentication FIRST
            flash('You need to log in to access this page.', 'danger')
            return redirect(url_for('main.login'))  # Redirect to login

        if not current_user.is_staff:  # THEN check is_staff
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.home'))  # Or staff.login

        return f(*args, **kwargs)
    return decorated_function
