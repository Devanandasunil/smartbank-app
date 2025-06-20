from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, current_app, make_response
)
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from .forms import (
    RegisterForm, LoginForm, DepositForm, WithdrawForm, TransferForm,
    GoalBasicForm, SavingModeForm, ProfileForm
)
from .models import (
    User, Account, Transaction, Loan, SpamReport, FinancialGoal, db, SavingMode
)
from datetime import datetime, timezone
from functools import wraps
import os
import base64
import pickle
from io import BytesIO
from PIL import Image
import numpy as np
import face_recognition
from app.models import Transaction, SavedContact
# ✅ Required imports at top of file
from datetime import datetime, timedelta
from flask import render_template, request, flash
from flask_login import login_required, current_user
from app.models import Transaction, SavedContact



main = Blueprint("main", __name__)

# Cache control decorator
def nocache(view):
    @wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return no_cache

# Helper: Ensure account exists
def get_or_create_account(user):
    if not user.account:
        account = Account(user_id=user.id)
        db.session.add(account)
        db.session.commit()
        return account
    return user.account

@main.route("/")
@nocache
def home():
    if current_user.is_authenticated:
        if hasattr(current_user, 'is_staff') and current_user.is_staff:
            return redirect(url_for('staff.dashboard'))
        else:
            return redirect(url_for('main.dashboard'))
    return render_template('home.html')

@main.route('/landing')
def landing():
    return render_template('home.html')

@main.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = User.query.filter((User.username == form.username.data) | (User.email == form.email.data)).first()
        if existing_user:
            flash("Username or email already exists.", "danger")
            return redirect(url_for('main.register'))

        new_user = User(
            username=form.username.data,
            email=form.email.data,
            name=form.name.data,
            place=form.place.data,
            mobile_number=form.mobile_number.data
        )
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful!", "success")
        return redirect(url_for('main.login'))

    return render_template("register.html", form=form)

@main.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for('main.dashboard'))
        else:
            flash("Invalid credentials.", "danger")
    return render_template("login.html", form=form)

@main.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("main.landing"))

from .utils import get_or_create_account 

@main.route("/dashboard")
@login_required
def dashboard():
    # ✅ Use helper to make sure account exists
    account = get_or_create_account(current_user)

    return render_template(
        "dashboard.html",
        username=current_user.username,
        account_number=account.account_number,
        balance=account.balance
    )



# Route: Financial Goals - Set & View
@main.route("/goals", methods=["GET", "POST"])
@login_required
@nocache
def goals():
    form = GoalBasicForm()
    if form.validate_on_submit():
        # Save the goal information
        goal = FinancialGoal(
            user_id=current_user.id,
            target_amount=form.target_amount.data,
            deadline=form.deadline.data,
            saving_mode=SavingMode[form.saving_mode.data]  # Use Enum
        )
        db.session.add(goal)
        db.session.commit()
        flash("Goal set successfully.", "success")
        return redirect(url_for("main.goals"))  # Redirect to goals page

    goals = FinancialGoal.query.filter_by(user_id=current_user.id).all()
    return render_template("goal_basic.html", form=form, goals=goals)

# Route: Configure Save Mode Amounts
@main.route("/goals/saving_mode/<int:goal_id>", methods=["GET", "POST"])
@login_required
@nocache
def saving_mode(goal_id):
    goal = FinancialGoal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        flash("Unauthorized access to this goal.", "danger")
        return redirect(url_for("main.goals"))

    form = SavingModeForm(obj=goal)
    if form.validate_on_submit():
        goal.saving_mode = SavingMode[form.saving_mode.data]  # Update using enum
        goal.daily_amount = form.daily_amount.data
        goal.weekly_amount = form.weekly_amount.data
        goal.monthly_amount = form.monthly_amount.data
        goal.yearly_amount = form.yearly_amount.data
        db.session.commit()
        flash("Saving mode updated successfully.", "success")
        return redirect(url_for("main.goals"))

    return render_template("goal_saving_mode.html", form=form, goal=goal)

# Route: Delete Financial Goal
@main.route('/goals/delete/<int:goal_id>', methods=['POST'])
@login_required
def delete_goal(goal_id):
    goal = FinancialGoal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for("main.goals"))
    
    db.session.delete(goal)
    db.session.commit()
    flash("Goal deleted successfully.", "info")
    return redirect(url_for("main.goals"))

# Deposit Route
@main.route('/deposit', methods=['GET', 'POST'])
@login_required
def deposit():
    form = DepositForm()
    if form.validate_on_submit():
        amount = float(form.amount.data)
        if amount <= 0:
            flash("Enter a valid amount", "danger")
        else:
            account = current_user.account
            account.balance += amount

            txn = Transaction(
                user_id=current_user.id,
                type='Deposit',
                amount=amount,
                recipient_account=None
            )
            db.session.add(txn)
            db.session.commit()

            flash("Deposit successful!", "success")
            return redirect(url_for('main.dashboard'))

    return render_template('deposit.html', form=form)

# Withdraw Route
@main.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    form = WithdrawForm()
    if form.validate_on_submit():
        amount = float(form.amount.data)
        account = current_user.account
        if amount <= 0 or amount > account.balance:
            flash("Invalid withdrawal amount", "danger")
        else:
            account.balance -= amount

            txn = Transaction(
                user_id=current_user.id,
                type='Withdraw',
                amount=amount,
                recipient_account=None
            )
            db.session.add(txn)
            db.session.commit()

            flash("Withdrawal successful!", "success")
            return redirect(url_for('main.dashboard'))

    return render_template('withdraw.html', form=form)

# Transfer Route
@main.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    form = TransferForm()
    if form.validate_on_submit():
        amount = float(form.amount.data)
        recipient_acc = form.recipient_account.data
        sender = current_user.account
        recipient = Account.query.filter_by(account_number=recipient_acc).first()

        if not recipient:
            flash("Recipient not found", "danger")
        elif recipient.id == sender.id:
            flash("Cannot transfer to yourself", "warning")
        elif amount <= 0 or amount > sender.balance:
            flash("Invalid transfer amount", "danger")
        else:
            sender.balance -= amount
            recipient.balance += amount

            txn = Transaction(
                user_id=current_user.id,
                type='Transfer',
                amount=amount,
                recipient_account=recipient_acc
            )
            db.session.add(txn)
            db.session.commit()

            flash("Transfer successful!", "success")
            return redirect(url_for('main.dashboard'))

    return render_template('transfer.html', form=form)

# Route: Loan Application
@main.route("/loan", methods=["GET", "POST"])
@login_required
@nocache
def loan():
    if request.method == "POST":
        amount = request.form.get("amount")
        reason = request.form.get("reason")

        if not amount or not reason:
            flash("Please fill in all the fields.", "danger")
            return redirect(url_for("main.loan"))

        try:
            amount_float = float(amount)
            if amount_float <= 0:
                flash("Amount must be positive.", "danger")
                return redirect(url_for("main.loan"))
        except ValueError:
            flash("Invalid amount.", "danger")
            return redirect(url_for("main.loan"))

        new_loan = Loan(user_id=current_user.id, amount=amount_float, reason=reason)
        db.session.add(new_loan)
        db.session.commit()

        flash("Loan application submitted successfully!", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("loan.html")

@main.route("/profile", methods=["GET", "POST"])
@login_required
@nocache
def profile():
    form = ProfileForm()

    if form.validate_on_submit():
        # Check if email is changing and is unique
        if form.email.data != current_user.email:
            if User.query.filter_by(email=form.email.data).first():
                flash("Email already exists.", "danger")
                return redirect(url_for("main.profile"))
            current_user.email = form.email.data

        # Update other fields
        current_user.name = form.name.data
        current_user.place = form.place.data
        current_user.mobile_number = form.mobile_number.data

        # Handle image upload
        if form.profile_image.data:
            filename = secure_filename(form.profile_image.data.filename)
            upload_path = os.path.join(current_app.root_path, "static/uploads", filename)
            form.profile_image.data.save(upload_path)
            current_user.profile_image = filename

        
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("main.profile"))

    elif request.method == "GET":
        # Pre-fill form with user data
        form.name.data = current_user.name
        form.place.data = current_user.place
        form.mobile_number.data = current_user.mobile_number
        form.email.data = current_user.email

    return render_template("profile.html", form=form, user=current_user)


# Route: List My Loans
@main.route("/my_loans")
@login_required
@nocache
def my_loans():
    loans = Loan.query.filter_by(user_id=current_user.id).order_by(Loan.id.desc()).all()
    return render_template("my_loans.html", loans=loans)

# Route: Transaction History
@main.route("/transactions", methods=['GET', 'POST'])
@login_required
@nocache
def transactions():
    name_filter = request.args.get('name', '').strip()
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()

    # Start base query
    query = Transaction.query.filter_by(user_id=current_user.id)

    # Filter by beneficiary name
    if name_filter:
        query = query.filter(Transaction.beneficiary_name.ilike(f"%{name_filter}%"))

    # Filter by start date
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(Transaction.timestamp >= start_date)
        except ValueError:
            flash("Invalid start date format. Use DD-MM-YYYY.", "danger")

    # Filter by end date
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Transaction.timestamp < end_date)
        except ValueError:
            flash("Invalid end date format. Use DD-MM-YYYY.", "danger")

    transactions = query.order_by(Transaction.id.desc()).all()

    # For "recent recipients"
    saved_contacts = SavedContact.query.filter_by(user_id=current_user.id).all()

    # 🔥 This is the missing piece!
    reported_ids = [r.transaction_id for r in current_user.spam_reports_sent]


    return render_template(
        "transactions.html",
        transactions=transactions,
        saved_contacts=saved_contacts,
        reported_ids=reported_ids
    )



# Route: Face Login
@main.route('/face_login', methods=['POST'])
def face_login():
    face_data_url = request.form.get("face_image")

    if not face_data_url:
        flash("Face image not received", "danger")
        return redirect(url_for("main.login"))

    try:
        header, encoded = face_data_url.split(",", 1)
        img_bytes = base64.b64decode(encoded)
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        img_np = np.array(img)

        encodings = face_recognition.face_encodings(img_np)
        if not encodings:
            flash("No face detected in image", "danger")
            return redirect(url_for("main.login"))

        login_encoding = encodings[0]

        users = User.query.all()
        for user in users:
            if user.face_encoding:
                saved_encoding = pickle.loads(user.face_encoding)
                match = face_recognition.compare_faces([saved_encoding], login_encoding, tolerance=0.5)[0]
                if match:
                    login_user(user)
                    flash("Face login successful!", "success")
                    return redirect(url_for("main.dashboard"))

        flash("No matching user found", "danger")
        return redirect(url_for("main.login"))

    except Exception as e:
        flash("Face login failed", "danger")
        print("Face login error:", str(e))
        return redirect(url_for("main.login"))

# Register the blueprint in your main application file (e.g., app.py) where 'app' is defined:
# from .routes import main
# app.register_blueprint(main)

@main.route('/test')
def test_error():
    print("Home route triggered")
    return 1 / 0  # deliberate ZeroDivisionError
   


