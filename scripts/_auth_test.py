import requests
from importlib import import_module
app = import_module('app')
BASE='http://127.0.0.1:5000'
s = requests.Session()
PASSWORD = app.app.config.get('STAFF_PASSWORD')
print('Using password:', PASSWORD)
resp = s.post(BASE + '/staff/login', data={'password': PASSWORD}, allow_redirects=False)
print('POST /staff/login', resp.status_code, resp.headers.get('Location'))
if resp.status_code in (301,302):
    r2 = s.get(BASE + resp.headers['Location'])
    print('Followed location status', r2.status_code)
print('/dashboard', s.get(BASE + '/dashboard').status_code)
print('/ac', s.get(BASE + '/ac').status_code)
