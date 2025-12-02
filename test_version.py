"""Проверка версии GAS скрипта."""
import json
import requests

SHEET_SYNC_URL = "https://script.google.com/macros/s/AKfycbyw_WbXJpFn8x9I0MAOmCjPKVPDAxAUAgZ0CtVy9rVZk8deTHN-rMhM38_MfdTkJ4wI/exec"

# Минимальный payload
test_payload = {
    "phone": "79999999999",
    "city": "Тест",
    "client_name": "Тест Тестович"
}

headers = {'Content-Type': 'application/json; charset=utf-8'}
json_data = json.dumps(test_payload, ensure_ascii=False).encode('utf-8')

print("Testing GAS script version...")
print(f"Payload: {test_payload}")

response = requests.post(SHEET_SYNC_URL, data=json_data, headers=headers, timeout=10)

print(f"\nStatus: {response.status_code}")
print(f"Response:\n{json.dumps(response.json(), indent=2, ensure_ascii=False)}")

# Проверяем наличие новых debug полей
result = response.json()
if 'debug_extracted' in result:
    print("\nOK: Script UPDATED - debug_extracted found")
else:
    print("\nERROR: Script OLD - debug_extracted NOT found")
    print("Need to update deployment in Google Apps Script!")
