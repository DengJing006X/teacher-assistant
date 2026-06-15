import requests
url = 'https://teacher-assistant-production.up.railway.app'
r = requests.post(f'{url}/api/chat', json={
    'message': 'What are the north star indicators?',
    'language': 'en',
    'history': []
}, timeout=30)
answer = r.json()['reply']
print(answer[:500])
