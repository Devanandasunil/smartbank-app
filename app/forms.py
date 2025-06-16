from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, PasswordField, SubmitField, FloatField,
    TextAreaField, DateField, EmailField, SelectField, DecimalField
)
from wtforms.validators import (
    DataRequired, Length, EqualTo, NumberRange,
    Email, Optional
)

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=25)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    name = StringField('Full Name', validators=[DataRequired()])
    place = StringField('Place', validators=[DataRequired()])
    mobile_number = StringField('Mobile Number', validators=[DataRequired(), Length(min=10, max=15)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), EqualTo('new_password', message='Passwords must match.')
    ])
    submit = SubmitField('Reset Password')

class ProfileForm(FlaskForm):
    name = StringField('Name', validators=[Optional(), Length(max=150)])
    place = StringField('Place', validators=[Optional(), Length(max=150)])
    mobile_number = StringField('Mobile Number', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=150)])
    photo = FileField('Profile Picture', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')
    ])
    submit = SubmitField('Update Profile')

class DepositForm(FlaskForm):
    amount = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField('Deposit')

class WithdrawForm(FlaskForm):
    amount = DecimalField('Amount', validators=[DataRequired()])
    submit = SubmitField('Withdraw')

class TransferForm(FlaskForm):
    recipient_account = StringField("Recipient Account Number", validators=[DataRequired()])
    amount = DecimalField("Amount", validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField("Transfer")

class LoanForm(FlaskForm):
    amount = FloatField('Loan Amount', validators=[
        DataRequired(), NumberRange(min=0.01, message="Amount must be positive.")
    ])
    reason = TextAreaField('Loan Reason', validators=[DataRequired()])
    submit = SubmitField('Apply for Loan')

class GoalBasicForm(FlaskForm):
    target_amount = FloatField(
        "Target Amount (₹)",
        validators=[DataRequired(), NumberRange(min=0.01)]
    )
    deadline = DateField(
        "Deadline (YYYY-MM-DD)",
        format="%Y-%m-%d",
        validators=[DataRequired()]
    )
    saving_mode = SelectField(
        "Saving Mode",
        choices=[
            ("NONE", "None"),
            ("DAILY", "Daily"),
            ("WEEKLY", "Weekly"),
            ("MONTHLY", "Monthly"),
            ("YEARLY", "Yearly"),
        ],
        default="NONE",
        validators=[DataRequired()]
    )
    daily_amount = FloatField(
        "Daily Amount", validators=[Optional(), NumberRange(min=0.0)]
    )
    weekly_amount = FloatField(
        "Weekly Amount", validators=[Optional(), NumberRange(min=0.0)]
    )
    monthly_amount = FloatField(
        "Monthly Amount", validators=[Optional(), NumberRange(min=0.0)]
    )
    yearly_amount = FloatField(
        "Yearly Amount", validators=[Optional(), NumberRange(min=0.0)]
    )
    submit = SubmitField("Save Goal")
    
class SavingModeForm(FlaskForm):
    saving_mode = SelectField(
        "Saving Mode",
        choices=[
            ("NONE", "None"),
            ("DAILY", "Daily"),
            ("WEEKLY", "Weekly"),
            ("MONTHLY", "Monthly"),
            ("YEARLY", "Yearly"),
        ],
        validators=[DataRequired()]
    )
    daily_amount = FloatField("Daily Amount", validators=[Optional(), NumberRange(min=0.0)])
    weekly_amount = FloatField("Weekly Amount", validators=[Optional(), NumberRange(min=0.0)])
    monthly_amount = FloatField("Monthly Amount", validators=[Optional(), NumberRange(min=0.0)])
    yearly_amount = FloatField("Yearly Amount", validators=[Optional(), NumberRange(min=0.0)])
    submit = SubmitField("Save Saving Mode")

