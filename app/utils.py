from functools import wraps
from flask import make_response, Response

def nocache(view) -> callable:
    @wraps(view)
    def no_cache(*args, **kwargs) -> Response:
        # Create response with no cache headers
        response = make_response(view(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return no_cache

from .models import Account, db
import random

def get_or_create_account(user):
    if not user.account:
        account_number = "SB" + str(random.randint(10000000, 99999999))
        account = Account(user_id=user.id, account_number=account_number, balance=0.0)
        db.session.add(account)
        db.session.commit()
    return user.account
