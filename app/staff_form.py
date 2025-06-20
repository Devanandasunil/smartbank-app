from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError
import re

def validate_staff_email(form, field):
    if not re.match(r".+@bank\.com$", field.data):
        raise ValidationError("Only @bank.com emails are allowed for staff registration.")

class StaffLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class StaffRegisterForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email(), validate_staff_email])
    mobile = StringField('Mobile', validators=[DataRequired()])
    staff_key = StringField('Staff Registration Key', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class ForgotUsernameForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), validate_staff_email])
    submit = SubmitField('Retrieve Username')

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), validate_staff_email])
    username = StringField('Username', validators=[DataRequired()])
    submit = SubmitField('Reset Password')
