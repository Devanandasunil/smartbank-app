from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, login_required, logout_user, current_user
from .forms import LoginForm, RegisterForm, TransferForm, DepositForm, WithdrawForm
from .models import User, Account
from flask_login import login_user
from app.utils import nocache

customer_bp = Blueprint('customer', __name__, url_prefix='/customer')

@customer_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data, is_staff=False).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for('customer.dashboard'))
        else:
            flash("Invalid email or password.", "danger")
    return render_template('login.html', form=form)

@customer_bp.route('/dashboard')
@login_required
@nocache
def dashboard():
    account = current_user.account
    balance = account.balance if account else 0.0
    account_number = account.account_number if account else None
    return render_template(
        "dashboard.html",
        username=current_user.username,
        account_number=account_number,
        balance=balance
    )

@customer_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('customer.login'))

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user
from app import db
from app.models import User, Account
import base64, numpy as np, face_recognition, pickle
from io import BytesIO
from PIL import Image
import random

@customer_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        full_name = request.form['name']
        place = request.form['place']
        mobile_number = request.form['mobile_number']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        face_data_url = request.form.get("face_image")

        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return render_template("register.html", form=form)

        if not face_data_url:
            flash("Please capture your face", "danger")
            return render_template("register.html", form=form)

        try:
            header, encoded = face_data_url.split(",", 1)
            img_bytes = base64.b64decode(encoded)
            img = Image.open(BytesIO(img_bytes)).convert('RGB')
            img_np = np.array(img)
            face_encodings = face_recognition.face_encodings(img_np)
            if not face_encodings:
                flash("No face detected", "danger")
                return render_template("register.html", form=form)
            face_encoding = face_encodings[0]
        except Exception as e:
            flash("Face processing failed", "danger")
            return render_template("register.html", form=form)

        # create user and account
        user = User(username=username, email=email, name=full_name,
                    place=place, mobile_number=mobile_number)
        user.set_password(password)
        user.face_encoding = pickle.dumps(face_encoding)

        db.session.add(user)
        db.session.commit()

        account_number = "SB" + str(random.randint(10000000, 99999999))
        account = Account(user_id=user.id, account_number=account_number, balance=0.0)
        db.session.add(account)
        db.session.commit()

        flash("Registration successful!", "success")
        return redirect(url_for('main.login'))

    return render_template("register.html", form=form)

@customer_bp.route('/emi_calculator', methods=['GET', 'POST'])
@login_required
def emi_calculator():
    emi = None
    if request.method == 'POST':
        try:
            principal = float(request.form['principal'])
            rate = float(request.form['interest_rate']) / 12 / 100
            tenure = int(request.form['tenure'])
            emi = (principal * rate * (1 + rate) ** tenure) / ((1 + rate) ** tenure - 1)
        except Exception:
            flash('Invalid input. Please enter valid numbers.', 'danger')
    return render_template('emi_calculator.html', emi=emi)

@customer_bp.route('/deposit', methods=['GET', 'POST'])
@login_required
def deposit():
    form = DepositForm()
    if form.validate_on_submit():
        amount = float(form.amount.data)
        account = current_user.account
        if account:
            account.balance += amount
            db.session.commit()
            flash('Deposit successful!', 'success')
            return redirect(url_for('customer.dashboard'))
        else:
            flash('No account found.', 'danger')
    return render_template('deposit.html', form=form)

@customer_bp.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    form = WithdrawForm()
    if form.validate_on_submit():
        # Your withdrawal logic here
        pass
    return render_template('withdraw.html', form=form)

@customer_bp.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    form = TransferForm()
    if form.validate_on_submit():
        recipient_acc_num = form.recipient_account.data
        amount = float(form.amount.data)

        sender_account = current_user.account
        recipient_account = Account.query.filter_by(account_number=recipient_acc_num).first()

        if not recipient_account:
            flash("Recipient account not found.", "danger")
        elif sender_account.balance < amount:
            flash("Insufficient funds.", "danger")
        else:
            sender_account.balance -= amount
            recipient_account.balance += amount
            db.session.commit()
            flash("Transfer successful!", "success")
            return redirect(url_for('customer.dashboard'))

    return render_template('transfer.html', form=form)

@customer_bp.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user = current_user
    account = user.account
    if account:
        db.session.delete(account)
    db.session.delete(user)
    db.session.commit()
    logout_user()
    flash("Your account has been deleted.", "success")
    return redirect(url_for('main.landing'))  # or your homepage

@customer_bp.route("/interest-calculator", methods=['GET', 'POST'])
@login_required
def interest_calculator():
    result = None
    if request.method == 'POST':
        try:
            principal = float(request.form['principal'])
            rate = float(request.form['rate']) / 12 / 100  # Monthly rate
            time = int(request.form['time'])  # In months

            emi = (principal * rate * pow(1 + rate, time)) / (pow(1 + rate, time) - 1)
            total_payment = emi * time
            total_interest = total_payment - principal

            result = {
                'emi': round(emi, 2),
                'total_payment': round(total_payment, 2),
                'total_interest': round(total_interest, 2)
            }
        except Exception as e:
            flash("Invalid input. Please enter valid numbers.", "danger")

    return render_template("interest_calculator.html", result=result)

