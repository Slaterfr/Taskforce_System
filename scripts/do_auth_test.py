import requests
from importlib import import_module
app = import_module('app')
BASE='http://127.0.0.1:5000'
s = requests.Session()
PASSWORD = app.app.config.get('STAFF_PASSWORD')
print('Using password:', PASSWORD)
resp = s.post(BASE + '/staff/login', json={'password': PASSWORD}, allow_redirects=False)
print('POST /staff/login (json) ->', resp.status_code, resp.text[:200])
# try dashboard
print('/dashboard', s.get(BASE + '/dashboard').status_code)
print('/ac', s.get(BASE + '/ac').status_code)
