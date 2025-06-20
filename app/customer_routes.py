from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, login_required, logout_user, current_user
from .forms import LoginForm, RegisterForm, TransferForm, DepositForm, WithdrawForm
from .models import User, Account, Transaction, SavedContact
from app import db
from app.utils import nocache
import base64
import numpy as np
import face_recognition
import pickle
from io import BytesIO
from PIL import Image
import random
from datetime import datetime
from .models import SpamReport, Transaction, User, db  


customer_bp = Blueprint('customer', __name__, url_prefix='/customer')

@customer_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data, is_staff=False).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for('main.dashboard'))
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

        flash("Registered successfully! Please login to continue.", "success")
        return redirect(url_for('customer.login'))

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
        
        if account is None:
            flash('No account found.', 'danger')
            return redirect(url_for('main.dashboard'))

        if amount <= 0:
            flash('Please enter a valid positive amount.', 'danger')
            return render_template('deposit.html', form=form)

        account.balance += amount

        transaction = Transaction(
            type="Deposit",
            amount=amount,
            user_id=current_user.id,
            timestamp=datetime.utcnow()
        )
        
        db.session.add(transaction)
        db.session.commit()

        flash('Deposit successful! Your balance has been updated.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('deposit.html', form=form)

@customer_bp.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    form = WithdrawForm()
    if form.validate_on_submit():
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
            return redirect(url_for('main.dashboard'))

    return render_template('transfer.html', form=form)

@customer_bp.route('/transfer-recents', methods=['GET', 'POST'])
@login_required
def transfer_with_recents():
    form = TransferForm()
    saved_contacts = SavedContact.query.filter_by(user_id=current_user.id).all()

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
            
            if request.form.get('save_contact'):
                existing = SavedContact.query.filter_by(
                    user_id=current_user.id,
                    account_number=form.recipient_account.data
                ).first()
                if not existing:
                    contact = SavedContact(
                        user_id=current_user.id,
                        name=form.beneficiary_name.data,
                        account_number=form.recipient_account.data
                    )
                    db.session.add(contact)
            
            db.session.commit()
            flash("Transfer successful!", "success")
            return redirect(url_for('customer.transaction_history'))

    return render_template('customer/transfer.html', form=form, saved_contacts=saved_contacts)

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
    return redirect(url_for('main.landing'))

@customer_bp.route("/interest-calculator", methods=['GET', 'POST'])
@login_required
@nocache
def interest_calculator():
    result = None
    if request.method == 'POST':
        try:
            principal = float(request.form['principal'])
            rate = float(request.form['rate']) / 12 / 100
            time = int(request.form['time'])

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



@customer_bp.route('/contacts/delete/<int:id>')
@login_required
@nocache
def delete_contact(id):
    contact = SavedContact.query.get_or_404(id)
    if contact.user_id != current_user.id:
        flash("Not authorized!")
        return redirect(url_for('customer.contacts'))
    db.session.delete(contact)
    db.session.commit()
    flash("Contact deleted.")
    return redirect(url_for('customer.contacts'))

@customer_bp.route('/contacts/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_contact(id):
    contact = SavedContact.query.get_or_404(id)
    if request.method == 'POST':
        contact.name = request.form['name']
        db.session.commit()
        flash("Contact updated.")
        return redirect(url_for('customer.contacts'))
    return render_template('customer/edit_contact.html', contact=contact)

@customer_bp.route('/report_transaction/<int:transaction_id>', methods=['POST'])
@login_required
def report_transaction(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)

    # Allow reporting even your own transaction (in case of fraud/hack)
    existing_report = SpamReport.query.filter_by(
        user_id=current_user.id,
        transaction_id=transaction_id
    ).first()

    if existing_report:
        db.session.delete(existing_report)
        db.session.commit()
        flash("Report removed for the transaction.", "info")
    else:
        # 🛡️ Save the reported user (could be same as reporter if it's a personal fraud case)
        new_report = SpamReport(
            user_id=current_user.id,
            transaction_id=transaction_id,
            reported_user_id=transaction.user_id,  # Can be same as current_user.id
            reason=request.form.get('message', '')
        )
        db.session.add(new_report)

        # Optional: Mark the transaction as fraud
        transaction.is_fraud = True

        db.session.commit()
        flash("Transaction reported successfully.", "success")

    return redirect(url_for('customer_bp.transactions'))

