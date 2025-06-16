from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, current_user, login_required
from .models import User, Transaction, Loan, SpamReport, db
from .staff_form import StaffLoginForm, StaffRegisterForm, ForgotUsernameForm, ForgotPasswordForm
from .decorators import staff_required
from .utils import nocache
import random
import string

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')

def generate_username(name):
    base = ''.join(name.lower().split())
    suffix = ''.join(random.choices(string.digits, k=4))
    return f"{base}{suffix}"

@staff_bp.route('/login', methods=['GET', 'POST'])
@nocache
def login():
    if current_user.is_authenticated and current_user.is_staff:
        return redirect(url_for('staff.dashboard'))

    form = StaffLoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data, is_staff=True).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('staff.dashboard'))
        flash('Invalid credentials or not authorized.', 'danger')

    return render_template('staff_login.html', form=form)

@staff_bp.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('main.home'))

@staff_bp.route('/register', methods=['GET', 'POST'])
def staff_register():
    form = StaffRegisterForm()
    if form.validate_on_submit():
        if form.staff_key.data != current_app.config.get('STAFF_REGISTRATION_KEY', '123456'):
            flash('Invalid staff registration key. Please use the correct key.', 'danger')
            return render_template('staff_register.html', form=form)

        username = generate_username(form.name.data)

        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email already registered.', 'danger')
            return render_template('staff_register.html', form=form)

        new_user = User(
            username=username,
            email=form.email.data,
            name=form.name.data,
            mobile_number=form.mobile_number.data,
            is_staff=True
        )
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()

        flash(f'Staff registered successfully. Your username is {username}', 'success')
        return redirect(url_for('staff.login'))

    return render_template('staff_register.html', form=form)

@staff_bp.route('/dashboard')
@nocache
@staff_required
def dashboard():
    if not current_user.is_authenticated or not current_user.is_staff:
        return redirect(url_for('main.home'))
    return render_template("staff_dashboard.html")

@staff_bp.route('/forgot_username', methods=['GET', 'POST'])
@nocache
def forgot_username():
    form = ForgotUsernameForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data, is_staff=True).first()
        if user:
            flash(f"Your username is: {user.username}", 'info')
        else:
            flash("Email not found or not a staff account.", 'danger')
    return render_template('forgot_username.html', form=form)

@staff_bp.route('/forgot_password', methods=['GET', 'POST'])
@nocache
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data, username=form.username.data, is_staff=True).first()
        if user:
            flash("Password reset link would be sent to your email (simulate here).", "info")
        else:
            flash("Invalid username/email or not a staff account.", "danger")
    return render_template('forgot_password_staff.html', form=form)

@staff_bp.route('/approve_loans', methods=['GET', 'POST'])
@nocache
@staff_required
def approve_loans():
    if not current_user.is_authenticated or not current_user.is_staff:
        return redirect(url_for('main.home'))
    pending_loans = Loan.query.filter_by(status='Pending').all()
    return render_template('approve_loans.html', loans=pending_loans)

@staff_bp.route('/loan/<int:loan_id>/update', methods=['POST'])
@nocache
@staff_required
def update_loan_status(loan_id):
    if not current_user.is_authenticated or not current_user.is_staff:
        return redirect(url_for('main.home'))
    loan = Loan.query.get_or_404(loan_id)
    new_status = request.form.get('status')
    if new_status in ['Approved', 'Rejected']:
        loan.status = new_status
        db.session.commit()
        flash(f"Loan #{loan.id} has been {new_status.lower()}.", "success")
    else:
        flash("Invalid status update.", "danger")
    return redirect(url_for('staff.approve_loans'))

@staff_bp.route('/approved_loans')
@nocache
@staff_required
def approved_loans():
    if not current_user.is_authenticated or not current_user.is_staff:
        return redirect(url_for('main.home'))
    loans = Loan.query.filter_by(status='Approved').all()
    return render_template('approved_loans.html', loans=loans)

@staff_bp.route('/rejected_loans')
@nocache
@staff_required
def rejected_loans():
    if not current_user.is_authenticated or not current_user.is_staff:
        return redirect(url_for('main.home'))
    loans = Loan.query.filter_by(status='Rejected').all()
    return render_template('rejected_loans.html', loans=loans)

@staff_bp.route('/view_reports')
@nocache
@staff_required
def view_reports():
    if not current_user.is_authenticated or not current_user.is_staff:
        return redirect(url_for('main.home'))
    reports = SpamReport.query.order_by(SpamReport.timestamp.desc()).all()
    return render_template("view_reports.html", reports=reports)

@staff_bp.route('/customer_list')
@nocache
@staff_required
def customer_list():
    if not current_user.is_authenticated or not current_user.is_staff:
        return redirect(url_for('main.home'))
    customers = User.query.filter_by(is_staff=False).all()
    return render_template("customer_list.html", customers=customers)

@staff_bp.route('/customers')
@nocache
@staff_required
def view_customers():
    if not current_user.is_authenticated or not current_user.is_staff:
        return redirect(url_for('main.home'))
    users = User.query.filter_by(is_staff=False).all()
    return render_template('staff_customers.html', users=users)

@staff_bp.route('/customer/<int:user_id>/transactions')
@nocache
@staff_required
def view_user_transactions(user_id):
    if not current_user.is_authenticated or not current_user.is_staff:
        return redirect(url_for('main.home'))
    user = User.query.get_or_404(user_id)
    transactions = Transaction.query.filter_by(user_id=user.id).all()
    return render_template('staff_user_transactions.html', user=user, transactions=transactions)

@staff_bp.route('/create_key', methods=['POST'])
@login_required
def create_key():
    if not current_user.is_admin:
        flash("Unauthorized access", "danger")
        return redirect(url_for('staff.dashboard'))

    new_key = request.form.get('new_key')
    current_app.config['STAFF_REGISTRATION_KEY'] = new_key
    flash(f"New staff key '{new_key}' created!", 'success')
    return redirect(url_for('staff.dashboard'))
