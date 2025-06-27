from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session, make_response
from flask_login import login_user, logout_user, current_user, login_required
from .models import User, db, Loan, SpamReport, Transaction
from .staff_form import StaffLoginForm, StaffRegisterForm, ForgotUsernameForm, ForgotPasswordForm
from .decorators import staff_required
from .utils import nocache
import random
import string
import face_recognition
import base64
import numpy as np
import pickle
from PIL import Image
from io import BytesIO
import logging
import cv2
import csv
from io import StringIO

staff_bp = Blueprint('staff', __name__, url_prefix='/staff')
logger = logging.getLogger(__name__)

def generate_username(name):
    base = ''.join(name.lower().split())
    suffix = ''.join(random.choices(string.digits, k=4))
    username = f"{base}{suffix}"
    while User.query.filter_by(username=username).first():
        suffix = ''.join(random.choices(string.digits, k=4))
        username = f"{base}{suffix}"
    return username

def get_face_encoding_from_base64(base64_data):
    try:
        if "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]
        img_bytes = base64.b64decode(base64_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        rgb_img = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb_img)
        if not encodings:
            print("❌ No valid face encoding found!")
            return None
        return encodings[0]
    except Exception as e:
        print(f"⚠️ Face processing error: {e}")
        return None

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
            flash('Invalid staff registration key.', 'danger')
            return render_template('staff_register.html', form=form)

        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered.', 'danger')
            return render_template('staff_register.html', form=form)

        username = generate_username(form.name.data)
        new_user = User(
            username=username,
            email=form.email.data,
            name=form.name.data,
            mobile_number=form.mobile.data,
            is_staff=True
        )
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()

        face_data_url = request.form.get('face_image')
        if face_data_url:
            try:
                encoding = get_face_encoding_from_base64(face_data_url)
                if encoding is not None and encoding.shape == (128,):
                    new_user.face_encoding = pickle.dumps(encoding)
                    db.session.commit()
                else:
                    raise ValueError("No valid face encoding detected.")
            except Exception as e:
                logger.error(f"Face encoding error during registration for {username}: {e}")
                db.session.delete(new_user)
                db.session.commit()
                flash(f"Face processing error: {e}", "danger")
                return render_template('staff_register.html', form=form)
        else:
            db.session.delete(new_user)
            db.session.commit()
            flash("Face image not provided. Please try again.", "danger")
            return render_template('staff_register.html', form=form)

        flash('Staff registered successfully.', 'success')
        flash(f'Your username is: {username}', 'info')
        return redirect(url_for('staff.login', prefill_username=username))

    return render_template('staff_register.html', form=form)

@staff_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = StaffLoginForm()
    if form.validate_on_submit():
        staff = User.query.filter_by(username=form.username.data, is_staff=True).first()
        if staff and staff.check_password(form.password.data):
            login_user(staff)
            flash(f"Login successful. Welcome, {staff.username}!", "success")
            return redirect(url_for('staff.dashboard'))
        else:
            flash("Invalid username or password.", "danger")

    prefill_username = request.args.get('prefill_username')
    if prefill_username:
        form.username.data = prefill_username

    return render_template("staff_login.html", form=form)

@staff_bp.route('/face_login', methods=['POST'])
def face_login():
    face_data_url = request.form.get("face_image")
    if not face_data_url:
        flash("Face image not received", "danger")
        return redirect(url_for("staff.login"))

    try:
        header, encoded = face_data_url.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        img = Image.open(BytesIO(img_bytes)).convert('RGB')
        img_np = np.array(img)
        encodings = face_recognition.face_encodings(img_np)

        if len(encodings) == 0:
            flash("No face detected. Try again.", "danger")
            return redirect(url_for("staff.login"))

        input_encoding = encodings[0]

        staff_list = User.query.filter_by(is_staff=True).all()
        for staff in staff_list:
            if staff.face_encoding:
                try:
                    stored_encoding = pickle.loads(staff.face_encoding)
                    if isinstance(stored_encoding, np.ndarray):
                        results = face_recognition.compare_faces(
                            [stored_encoding], input_encoding, tolerance=0.5
                        )
                        if results and results[0]:
                            login_user(staff)
                            flash(f"Face login successful. Welcome, {staff.username}!", "success")
                            return redirect(url_for("staff.dashboard"))
                except Exception as e:
                    continue

        flash("Face not recognized. Try again or use credentials.", "danger")
        return redirect(url_for("staff.login"))

    except Exception as e:
        flash(f"Face login error: {e}", "danger")
        return redirect(url_for("staff.login"))
    
@staff_bp.route('/dashboard')
@nocache
@staff_required
def dashboard():
    return render_template("staff_dashboard.html")

@staff_bp.route('/approve_loans', methods=['GET', 'POST'])
@nocache
@staff_required
def approve_loans():
    pending_loans = Loan.query.filter_by(status='Pending').all()
    return render_template('approve_loans.html', loans=pending_loans)

@staff_bp.route('/loan/<int:loan_id>/update', methods=['POST'])
@nocache
@staff_required
def update_loan_status(loan_id):
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
    loans = Loan.query.filter_by(status='Approved').all()
    return render_template('approved_loans.html', loans=loans)

@staff_bp.route('/rejected_loans')
@nocache
@staff_required
def rejected_loans():
    loans = Loan.query.filter_by(status='Rejected').all()
    return render_template('rejected_loans.html', loans=loans)

@staff_bp.route('/view_reports', methods=['GET'])
@nocache
@staff_required
def view_reports():
    status_filter = request.args.get('status')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search = request.args.get('search')

    query = SpamReport.query

    if status_filter:
        query = query.filter_by(status=status_filter)
    if start_date:
        query = query.filter(SpamReport.timestamp >= start_date)
    if end_date:
        query = query.filter(SpamReport.timestamp <= end_date)
    if search:
        query = query.join(User, SpamReport.user_id == User.id).filter(
            db.or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                SpamReport.reason.ilike(f"%{search}%")
            )
        )

    reports = query.order_by(SpamReport.timestamp.desc()).all()
    return render_template("view_reports.html", reports=reports)

@staff_bp.route('/resolve_report/<int:report_id>', methods=['POST'])
@staff_required
def resolve_report(report_id):
    report = SpamReport.query.get_or_404(report_id)
    report.status = 'Resolved'
    db.session.commit()
    flash("Report marked as resolved.", "success")
    return redirect(url_for('staff.view_reports'))

@staff_bp.route('/delete_report/<int:report_id>', methods=['POST'])
@staff_required
def delete_report(report_id):
    report = SpamReport.query.get_or_404(report_id)
    db.session.delete(report)
    db.session.commit()
    flash("Report deleted.", "info")
    return redirect(url_for('staff.view_reports'))

@staff_bp.route('/customers')
@nocache
@staff_required
def view_customers():
    users = User.query.filter_by(is_staff=False).all()
    return render_template("staff_customers.html", users=users)

@staff_bp.route('/customer/<int:user_id>/transactions')
@nocache
@staff_required
def view_user_transactions(user_id):
    from datetime import datetime, timedelta
    import pytz

    user = User.query.get_or_404(user_id)
    tx_type = request.args.get("type")
    date_range = request.args.get("date_range")
    search = request.args.get("search", "").lower()
    page = request.args.get("page", 1, type=int)

    transactions_query = Transaction.query.filter_by(user_id=user.id)

    # Filter by type
    if tx_type == "credit":
        transactions_query = transactions_query.filter(Transaction.amount > 0)
    elif tx_type == "debit":
        transactions_query = transactions_query.filter(Transaction.amount < 0)

    # Filter by date range
    if date_range == "3days":
        start_date = datetime.utcnow() - timedelta(days=3)
        transactions_query = transactions_query.filter(Transaction.timestamp >= start_date)
    elif date_range == "7days":
        start_date = datetime.utcnow() - timedelta(days=7)
        transactions_query = transactions_query.filter(Transaction.timestamp >= start_date)
    elif date_range == "30days":
        start_date = datetime.utcnow() - timedelta(days=30)
        transactions_query = transactions_query.filter(Transaction.timestamp >= start_date)
    elif date_range == "3months":
        start_date = datetime.utcnow() - timedelta(days=90)
        transactions_query = transactions_query.filter(Transaction.timestamp >= start_date)
    elif date_range == "thisyear":
        start_of_year = datetime(datetime.utcnow().year, 1, 1)
        transactions_query = transactions_query.filter(Transaction.timestamp >= start_of_year)

    # Filter by search
    if search:
        search_pattern = f"%{search}%"
        transactions_query = transactions_query.filter(
            db.or_(
                Transaction.type.ilike(search_pattern),
                Transaction.description.ilike(search_pattern),
                db.cast(Transaction.timestamp, db.String).ilike(search_pattern)
            )
        )

    # Sort and paginate
    transactions_query = transactions_query.order_by(Transaction.timestamp.desc())
    per_page = 10
    pagination = transactions_query.paginate(page=page, per_page=per_page, error_out=False)
    transactions = pagination.items
    total_transactions = pagination.total

    # Convert UTC to IST
    indian_time = pytz.timezone('Asia/Kolkata')
    for tx in transactions:
        if tx.timestamp:
            tx.local_timestamp = tx.timestamp.replace(tzinfo=pytz.utc).astimezone(indian_time)
    
    return render_template(
        "staff_user_transactions.html",
        user=user,
        transactions=transactions,
        total_transactions=total_transactions,
        page=page,
        pages=pagination.pages,
        current_type=tx_type,
        current_range=date_range,
        search_query=search
    )

from flask import make_response
from io import StringIO
import csv
import pytz

@staff_bp.route('/staff/customer/<int:user_id>/export_transactions')
@nocache
@staff_required
def export_customer_transactions(user_id):
    user = User.query.get_or_404(user_id)
    transactions = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.timestamp.desc()).all()

    # Convert timestamps to IST
    ist = pytz.timezone('Asia/Kolkata')
    for tx in transactions:
        if tx.timestamp:
            tx.local_timestamp = tx.timestamp.replace(tzinfo=pytz.utc).astimezone(ist)

    # Generate CSV content
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Transaction ID', 'Date (IST)', 'Type', 'Amount', 'Status', 'Description'])

    for tx in transactions:
        cw.writerow([
            f'TNX{tx.timestamp.strftime("%Y%m%d")}{tx.id:04}',
            tx.local_timestamp.strftime("%b %d, %Y at %I:%M %p"),
            'Credit' if tx.amount > 0 else 'Debit',
            f"{tx.amount:.2f}",
            tx.status,
            tx.description or "Bank Transaction"
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=transactions_{user.username}.csv"
    output.headers["Content-type"] = "text/csv"
    return output


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
            flash("Password reset link would be sent to your email (simulation).", "info")
        else:
            flash("Invalid username/email or not a staff account.", "danger")
    return render_template('forgot_password_staff.html', form=form)

@staff_bp.route('/transaction/<int:transaction_id>')
@nocache
@staff_required
def view_transaction_detail(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    user = User.query.get(transaction.user_id)

    import pytz
    indian_time = pytz.timezone('Asia/Kolkata')
    if transaction.timestamp:
        transaction.local_timestamp = transaction.timestamp.replace(tzinfo=pytz.utc).astimezone(indian_time)

    return render_template("staff_transaction_detail.html", transaction=transaction, user=user)



