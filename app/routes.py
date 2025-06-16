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
            return redirect(url_for('customer.dashboard'))
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

# Route: Deposit Money
@main.route("/deposit", methods=["GET", "POST"])
@login_required
@nocache
def deposit():
    form = DepositForm()
    if form.validate_on_submit():
        account = get_or_create_account(current_user)
        account.balance += form.amount.data
        transaction = Transaction(
            type="Deposit", amount=form.amount.data, user_id=current_user.id
        )
        db.session.add(transaction)
        db.session.commit()
        flash("Amount deposited.", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("deposit.html", form=form)

# Route: Withdraw Money
@main.route("/withdraw", methods=["GET", "POST"])
@login_required
@nocache
def withdraw():
    form = WithdrawForm()
    if form.validate_on_submit():
        account = get_or_create_account(current_user)
        amount = form.amount.data

        # 1. Fetch the User's Active Goal
        goal = (
            FinancialGoal.query.filter_by(user_id=current_user.id)
            .filter(FinancialGoal.saving_mode != SavingMode.NONE)
            .order_by(FinancialGoal.created_at.desc())
            .first()
        )

        if goal:
            # 2. Calculate Savings Progress
            # 2. Calculate Savings Progress
            today = datetime.now(timezone.utc).date()

            if goal.saving_mode == SavingMode.DAILY:
                days_since_creation = (today - goal.created_at.date()).days
                expected_savings = goal.daily_amount * days_since_creation
                weeks_since_creation = (today - goal.created_at.date()).days // 7
                expected_savings = goal.weekly_amount * weeks_since_creation
            elif goal.saving_mode == SavingMode.MONTHLY:
                months_since_creation = (today.year - goal.created_at.year) * 12 + (
                    today.month - goal.created_at.month
                )
                expected_savings = goal.monthly_amount * months_since_creation
            elif goal.saving_mode == SavingMode.YEARLY:
                years_since_creation = today.year - goal.created_at.year
                expected_savings = goal.yearly_amount * years_since_creation
            else:
                expected_savings = 0.0

            # 3. Check Savings Target
            if account.balance < amount:
                flash("Insufficient balance.", "danger")
                return redirect(url_for("main.withdraw"))

            if account.balance - amount < expected_savings:
                flash(
                    "Withdrawal not allowed. You have not met your savings goal.",
                    "danger",
                )
                return redirect(url_for("main.withdraw"))

        # 4. Prevent Withdrawal (If Necessary)
        if amount > account.balance:
            flash("Insufficient balance.", "danger")
            return redirect(url_for("main.withdraw"))

        # 5. Update Savings Progress (If Withdrawal Allowed)
        account.balance -= amount
        transaction = Transaction(
            type="Withdraw", amount=amount, user_id=current_user.id
        )
        db.session.add(transaction)
        db.session.commit()
        flash("Amount withdrawn.", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("withdraw.html", form=form)

# Route: Transfer Money
@main.route("/transfer", methods=["GET", "POST"])
@login_required
@nocache
def transfer():
    form = TransferForm()
    if form.validate_on_submit():
        sender_account = get_or_create_account(current_user)
        recipient_account = Account.query.filter_by(
            account_number=form.recipient_account.data
        ).first()
        if not recipient_account:
            flash("Invalid recipient.", "danger")
            return redirect(url_for("main.transfer"))
        if form.amount.data > sender_account.balance:
            flash("Insufficient balance.", "danger")
            return redirect(url_for("main.transfer"))
        sender_account.balance -= form.amount.data
        recipient_account.balance += form.amount.data

        sender_tx = Transaction(
            type="Transfer Sent",
            amount=form.amount.data,
            user_id=current_user.id,
            recipient_account=recipient_account.account_number,
        )
        recipient_tx = Transaction(
            type="Transfer Received",
            amount=form.amount.data,
            user_id=recipient_account.user_id,
            recipient_account=sender_account.account_number,
        )
        db.session.add(sender_tx)
        db.session.add(recipient_tx)
        db.session.commit()
        flash("Transfer completed.", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("transfer.html", form=form)

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

# Route: Profile Management
@main.route("/profile", methods=["GET", "POST"])
@login_required
@nocache
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.place = form.place.data
        current_user.mobile_number = form.mobile_number.data
        if form.email.data != current_user.email:
            if User.query.filter_by(email=form.email.data).first():
                flash("Email already exists.", "danger")
                return redirect(url_for("main.profile"))
            current_user.email = form.email.data
        if form.photo.data:
            filename = secure_filename(form.photo.data.filename)
            upload_path = os.path.join(
                current_app.root_path, "static/uploads", filename
            )
            form.photo.data.save(upload_path)
            current_user.profile_image = filename
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("main.profile"))
    return render_template("profile.html", form=form, user=current_user)

# New route: Delete user account
@main.route("/profile/delete", methods=["POST"])
@login_required
def delete_profile():
    user = current_user
    logout_user()
    # Delete related data first to avoid foreign key constraints if any
    Loan.query.filter_by(user_id=user.id).delete()
    FinancialGoal.query.filter_by(user_id=user.id).delete()
    Transaction.query.filter_by(user_id=user.id).delete()
    Account.query.filter_by(user_id=user.id).delete()
    SpamReport.query.filter_by(user_id=user.id).delete()
    SpamReport.query.filter_by(reported_user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    flash("Your account has been deleted successfully.", "success")
    return redirect(url_for("main.landing"))

# Route: List My Loans
@main.route("/my_loans")
@login_required
@nocache
def my_loans():
    loans = Loan.query.filter_by(user_id=current_user.id).order_by(Loan.id.desc()).all()
    return render_template("my_loans.html", loans=loans)

# Route: Transaction History
@main.route("/transactions")
@login_required
@nocache
def transactions():
    transactions = (
        Transaction.query.filter_by(user_id=current_user.id)
        .order_by(Transaction.id.desc())
        .all()
    )
    return render_template("transactions.html", transactions=transactions)

# Route: Report Suspicious Transaction
@main.route("/report_spam/<int:transaction_id>", methods=["POST"])
@login_required
def report_spam(transaction_id):
    reason = request.form.get("reason", "")
    transaction = Transaction.query.get_or_404(transaction_id)
    report = SpamReport(
        transaction_id=transaction.id, user_id=current_user.id, reason=reason
    )
    transaction.is_fraud = True
    db.session.add(report)
    db.session.commit()
    flash("Transaction reported as suspicious.", "info")
    return redirect(url_for("main.transactions"))

# Route: Report Transaction
@main.route("/report_transaction/<int:transaction_id>", methods=["POST"])
@login_required
def report_transaction(transaction_id):
    tx = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first()
    if not tx:
        flash("Transaction not found.", "danger")
        return redirect(url_for("main.transactions"))
    if tx.reported:
        flash("Transaction already reported.", "info")
    else:
        tx.reported = True
        db.session.commit()
        flash("Transaction reported successfully.", "success")
    return redirect(url_for("main.transactions"))

# Route: Undo Report Transaction
@main.route("/undo_report_transaction/<int:transaction_id>", methods=["POST"])
@login_required
def undo_report_transaction(transaction_id):
    tx = Transaction.query.filter_by(id=transaction_id, user_id=current_user.id).first()
    if not tx:
        flash("Transaction not found.", "danger")
        return redirect(url_for("main.transactions"))
    if not tx.reported:
        flash("Transaction is not reported.", "info")
    else:
        tx.reported = False
        db.session.commit()
        flash("Report undone successfully.", "success")
    return redirect(url_for("main.transactions"))

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

