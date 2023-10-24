import requests
import json
import hashlib

data = {
    "id":4,
    "text": "test",
    "title": "yooo"
        }

def compute_checksum(data):
    return hashlib.sha256(str(data).encode('utf-8')).digest()


checksum = compute_checksum(data)
print(checksum)
data['checksum'] = checksum.hex()
print(data['checksum'])

headers = {'Content-Type': 'application/json'}
params = {'text_column':'aws_text', 'title_column':'aws_title', 'checksum_column':'aws_checksum'}
url = 'https://ousoxg55w5-vpce-0ebe9f0a90313d9ea.execute-api.us-west-1.amazonaws.com/prod/put-first-translation'

response = requests.post(url, json=json.dumps(data), headers=headers, params=params)

print(response.status_code)
print(response.text)
