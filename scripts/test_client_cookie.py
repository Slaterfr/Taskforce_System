import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app

# Paste session cookie value captured earlier or read from env
SESSION_COOKIE = None

# Attempt to read from env variable if set
import os
SESSION_COOKIE = os.environ.get('TF_SESSION_COOKIE')

with app.test_client() as c:
    # Directly set session flag to simulate logged-in staff (avoids cookie handling)
    with c.session_transaction() as sess:
        sess['is_staff'] = True
    rv = c.get('/ac')
    print('/ac', rv.status_code)
    if rv.status_code != 200:
        print(rv.get_data(as_text=True)[:1000])
    else:
        print('OK len', len(rv.get_data(as_text=True)))
