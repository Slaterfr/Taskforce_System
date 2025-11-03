import requests

BASE = 'http://127.0.0.1:5000'

s = requests.Session()
# Try login with configured password
resp = s.get(BASE + '/staff/login')
print('GET /staff/login', resp.status_code)
# read password from config by importing app
from importlib import import_module
app = import_module('app')
PASSWORD = app.app.config.get('STAFF_PASSWORD')
print('Using STAFF_PASSWORD from config:', bool(PASSWORD))
login = s.post(BASE + '/staff/login', data={'password': PASSWORD}, allow_redirects=False)
print('POST /staff/login ->', login.status_code, login.headers.get('Location'))
# follow redirect
if login.status_code in (301,302):
    r2 = s.get(BASE + login.headers['Location'])
    print('Follow ->', r2.status_code)
# Now access dashboard
dash = s.get(BASE + '/dashboard')
print('/dashboard', dash.status_code)
print(dash.text[:500])
