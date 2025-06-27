from flask import (
    Blueprint, render_template, redirect, url_for, request, flash, current_app, make_response
)
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from .forms import (
    RegisterForm, LoginForm, ForgotPasswordForm, DepositForm, WithdrawForm, TransferForm,
    ProfileForm, SetGoalForm,
)
from .models import (
    User, Account, Transaction, Loan, SpamReport, FinancialGoal, db, SavingMode
)
from datetime import datetime, timedelta
from functools import wraps
import os
import base64
import pickle
from io import BytesIO
from PIL import Image
import numpy as np
import face_recognition
import pytz
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

@main.route("/dashboard")
@login_required
def dashboard():
    account = get_or_create_account(current_user)
    balance = account.balance if account else 0.0
    account_number = account.account_number if account else None

    # Total saved in goals
    goal_savings = sum(goal.smart_saver_balance for goal in current_user.goals) if hasattr(current_user, 'goals') else 0.0
    usable_balance = balance - goal_savings

    return render_template(
        "dashboard.html",
        username=current_user.username,
        account_number=account_number,
        balance=balance,
        usable_balance=usable_balance,
        goal_savings=goal_savings
    )


@main.route("/forgot_password", methods=["GET", "POST"])
@nocache
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            user.set_password(form.new_password.data)
            db.session.commit()
            flash("Password reset successful! Please login.", "success")
            return redirect(url_for("main.login"))
        else:
            flash("No account found with that email.", "danger")
    return render_template("forgot_password.html", form=form)

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
            txn = Transaction(user_id=current_user.id, type='Deposit', amount=amount, recipient_account=None)
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
            txn = Transaction(user_id=current_user.id, type='Withdraw', amount=amount, recipient_account=None)
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
            txn = Transaction(user_id=current_user.id, type='Transfer', amount=amount, recipient_account=recipient_acc)
            db.session.add(txn)
            db.session.commit()
            flash("Transfer successful!", "success")
            return redirect(url_for('main.dashboard'))
    return render_template('transfer.html', form=form)

# Loan
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

# Profile
@main.route("/profile", methods=["GET", "POST"])
@login_required
@nocache
def profile():
    form = ProfileForm()
    if form.validate_on_submit():
        if form.email.data != current_user.email:
            if User.query.filter_by(email=form.email.data).first():
                flash("Email already exists.", "danger")
                return redirect(url_for("main.profile"))
            current_user.email = form.email.data

        current_user.name = form.name.data
        current_user.place = form.place.data
        current_user.mobile_number = form.mobile_number.data

        if form.profile_image.data:
            filename = secure_filename(form.profile_image.data.filename)
            upload_path = os.path.join(current_app.root_path, "static/uploads", filename)
            form.profile_image.data.save(upload_path)
            current_user.profile_image = filename

        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("main.profile"))

    elif request.method == "GET":
        form.name.data = current_user.name
        form.place.data = current_user.place
        form.mobile_number.data = current_user.mobile_number
        form.email.data = current_user.email

    return render_template("profile.html", form=form, user=current_user)

# Loans
@main.route("/my_loans")
@login_required
@nocache
def my_loans():
    loans = Loan.query.filter_by(user_id=current_user.id).order_by(Loan.id.desc()).all()
    return render_template("my_loans.html", loans=loans)

# Transactions
@main.route("/transactions", methods=['GET'])
@login_required
@nocache
def transactions():
    name_filter = request.args.get('name', '').strip()
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()
    tx_type = request.args.get('transaction_type', '').strip().lower()

    query = Transaction.query.filter_by(user_id=current_user.id)

    if name_filter:
        query = query.filter(Transaction.beneficiary_name.ilike(f"%{name_filter}%"))

    if tx_type:
        if tx_type == "deposit":
            query = query.filter(Transaction.type.ilike("Deposit"))
        elif tx_type == "withdraw":
            query = query.filter(Transaction.type.ilike("Withdraw"))
        elif tx_type == "received":
            query = query.filter(Transaction.type.ilike("Received"))

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(Transaction.timestamp >= start_date)
        except ValueError:
            flash("Invalid start date format. Use YYYY-MM-DD.", "danger")

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Transaction.timestamp < end_date)
        except ValueError:
            flash("Invalid end date format. Use YYYY-MM-DD.", "danger")

    transactions = query.order_by(Transaction.timestamp.desc()).all()

    indian_time = pytz.timezone('Asia/Kolkata')
    for tx in transactions:
        if tx.timestamp:
            tx.local_timestamp = tx.timestamp.replace(tzinfo=pytz.utc).astimezone(indian_time)

    saved_contacts = SavedContact.query.filter_by(user_id=current_user.id).all()
    reported_ids = [r.transaction_id for r in current_user.spam_reports_sent]

    return render_template("transactions.html", transactions=transactions, saved_contacts=saved_contacts, reported_ids=reported_ids)

# Face login
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

# -------------------------------
# Financial Goals
# -------------------------------

@main.route("/financial_goals")
@login_required
def financial_goals_landing():
    goals = FinancialGoal.query.filter_by(user_id=current_user.id).all()
    return render_template("goal_basic.html", goals=goals)

@main.route("/goal_calculator")
@login_required
def goal_calculator():
    return render_template("goal_calculator.html")


from datetime import datetime, timedelta
from calendar import month_abbr

@main.route("/view_goals")
@login_required
def view_goals():
    goals = FinancialGoal.query.filter_by(user_id=current_user.id).all()
    warnings = []  # ✅ Initialize warnings list

    for goal in goals:
        # Chart logic
        start = datetime.utcnow().date()
        end = goal.deadline
        labels = []
        current = start
        while current <= end:
            labels.append(month_abbr[current.month])
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        monthly_value = goal.smart_saver_balance / max(1, len(labels))
        chart_data = [round(monthly_value, 2)] * len(labels)
        goal.chart_labels = labels
        goal.chart_data = chart_data

        # ✅ Warning logic
        days_left = (goal.deadline - datetime.utcnow().date()).days
        if days_left <= 5 and goal.smart_saver_balance < goal.target_amount:
            remaining = goal.target_amount - goal.smart_saver_balance
            warnings.append(
                f"⚠️ Goal '{goal.name}' is nearing deadline! ₹{remaining:.0f} left to save."
            )

    # ✅ Return after processing all goals
    return render_template("view_goal.html", goals=goals, warnings=warnings)


@main.route("/goal/<int:goal_id>")
@login_required
def view_single_goal(goal_id):
    goal = FinancialGoal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for("main.view_goals"))
    goal.chart_labels = ["Jan", "Feb", "Mar", "Apr"]
    goal.chart_data = [1000, 2500, 3000, int(goal.smart_saver_balance)]
    return render_template("single_goal.html", goal=goal)

@main.route("/goal/edit/<int:goal_id>", methods=["GET", "POST"])
@login_required
def edit_goal(goal_id):
    goal = FinancialGoal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for("main.view_goals"))
    if request.method == "POST":
        goal.name = request.form.get("goalName")
        goal.target_amount = float(request.form.get("goalAmount") or 0)
        goal.deadline = datetime.strptime(request.form.get("deadline"), "%Y-%m-%d").date()
        db.session.commit()
        flash("Goal updated successfully.", "success")
        return redirect(url_for("main.view_goals"))
    return render_template("edit_goal.html", goal=goal)

@main.route("/goal/delete/<int:goal_id>", methods=["POST"])
@login_required
def delete_goal(goal_id):
    goal = FinancialGoal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        flash("Unauthorized", "danger")
        return redirect(url_for("main.view_goals"))
    db.session.delete(goal)
    db.session.commit()
    flash("Goal deleted successfully.", "info")
    return redirect(url_for("main.view_goals"))

@main.route("/smart_saver/withdraw/<int:goal_id>", methods=["POST"])
@login_required
def withdraw_from_smart_saver(goal_id):
    goal = FinancialGoal.query.get_or_404(goal_id)
    if goal.user_id != current_user.id:
        flash("Unauthorized", "danger")
        return redirect(url_for("main.view_goals"))
    if goal.smart_saver_balance <= 0:
        flash("Nothing to withdraw.", "warning")
        return redirect(url_for("main.view_goals"))
    amount = round(goal.smart_saver_balance, 2)
    current_user.account.balance += amount
    goal.smart_saver_balance = 0.0
    txn = Transaction(
        user_id=current_user.id,
        type="Smart Saver Withdrawal",
        amount=amount,
        status="Success",
        description="Withdrawn from Smart Saver"
    )
    db.session.add(txn)
    db.session.commit()
    flash(f"₹{amount} withdrawn from Smart Saver.", "success")
    return redirect(url_for("main.view_goals"))

@main.route("/set_goal", methods=["GET", "POST"])
@login_required
def set_goal():
    form = SetGoalForm()
    if form.validate_on_submit():
        name = form.goalName.data
        target = form.goalAmount.data
        current = form.currentSavings.data or 0.0
        deadline = form.deadline.data
        frequency = form.savingsMode.data or "NONE"
        goal = FinancialGoal(
            user_id=current_user.id,
            name=name,
            target_amount=target,
            deadline=deadline,
            saving_mode=SavingMode[frequency],
            smart_saver_balance=current,
            last_saved_at=datetime.utcnow(),
        )
        db.session.add(goal)
        db.session.commit()
        flash("Goal set successfully.", "success")
        return redirect(url_for("main.view_goals"))
    return render_template("set_goal.html", form=form)

@main.route("/goal/deposit/<int:goal_id>", methods=["GET", "POST"])
@login_required
def deposit_to_goal(goal_id):
    goal = FinancialGoal.query.get_or_404(goal_id)

    # Ensure user owns this goal
    if goal.user_id != current_user.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for("main.view_goals"))

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount") or 0)
        except ValueError:
            flash("Invalid input. Please enter a numeric value.", "warning")
            return redirect(url_for("main.deposit_to_goal", goal_id=goal.id))

        if amount <= 0:
            flash("Enter a valid amount.", "warning")
            return redirect(url_for("main.deposit_to_goal", goal_id=goal.id))

        if current_user.account.balance < amount:
            flash("Insufficient account balance.", "danger")
            return redirect(url_for("main.deposit_to_goal", goal_id=goal.id))

        # Process deposit
        goal.smart_saver_balance += amount
        current_user.account.balance -= amount

        txn = Transaction(
            user_id=current_user.id,
            type="Smart Saver Deposit",
            amount=amount,
            status="Success",
            description=f"Deposited to goal '{goal.name}'"
        )
        db.session.add(txn)
        db.session.commit()

        flash(f"₹{amount} deposited to your goal.", "success")
        return redirect(url_for("main.view_goals"))

    return render_template("deposit_goal.html", goal=goal)

