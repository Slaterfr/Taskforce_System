from app import app
from flask import request
import traceback

with app.test_request_context('/ac', method='GET'):
    # attach a fake user object so staff_required passes
    request.user = type('U', (), {'is_staff': True})()
    try:
        rv = app.view_functions['ac_dashboard']()
        print('SUCCESS', type(rv))
        if isinstance(rv, str):
            print('LENGTH', len(rv))
        else:
            print(rv)
    except Exception:
        traceback.print_exc()
