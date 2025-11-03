import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
from importlib import import_module
app = import_module('app')
BASE='http://127.0.0.1:5000'
s = requests.Session()
PASSWORD = app.app.config.get('STAFF_PASSWORD')
r = s.post(BASE + '/staff/login', json={'password': PASSWORD}, allow_redirects=False)
print('LOGIN status:', r.status_code)
print('RESP headers:', dict(r.headers))
print('COOKIES after login (session.cookies):', s.cookies.get_dict())
# Now request /ac
r2 = s.get(BASE + '/ac')
print('/ac status:', r2.status_code)
print('RESP headers (ac):', dict(r2.headers))
print('COOKIES sent:', r2.request._cookies)
print('Response snippet:', r2.text[:400])
