import os, sys
# ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app
from flask import session
import traceback

with app.test_request_context('/ac'):
    # set session as staff
    session['is_staff'] = True
    try:
        rv = app.view_functions['ac_dashboard']()
        print('OK:', type(rv))
    except Exception:
        traceback.print_exc()
