import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app

with app.test_client() as c:
    # post login
    config_pw = app.config.get('STAFF_PASSWORD')
    rv = c.post('/staff/login', json={'password': config_pw})
    print('/staff/login', rv.status_code, rv.get_data(as_text=True)[:200])
    # now access /ac
    rv2 = c.get('/ac')
    print('/ac', rv2.status_code)
    if rv2.status_code != 200:
        print(rv2.get_data(as_text=True)[:1000])
    else:
        print('OK length', len(rv2.get_data(as_text=True)))
