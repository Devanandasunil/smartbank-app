import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'devananda_smartbank_secret'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///instance/bank.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ✅ Google reCAPTCHA keys
    RECAPTCHA_PUBLIC_KEY = '6LdaoFYrAAAAAPEz8C6qgqAvVS6Z76XvwO6vUkw3'   # Site Key
    RECAPTCHA_PRIVATE_KEY = '6LdaoFYrAAAAAHgBMgTkBDhq4TmgzpXC6QcqBtM6'  # Secret Key
