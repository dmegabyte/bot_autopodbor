"""Простой тест POST запроса без Unicode символов."""
import json
import requests

SHEET_SYNC_URL = "https://script.google.com/macros/s/AKfycbyw_WbXJpFn8x9I0MAOmCjPKVPDAxAUAgZ0CtVy9rVZk8deTHN-rMhM38_MfdTkJ4wI/exec"

test_payload = {
    "phone": "79991234999",  # Новый тестовый номер
    "brand": "Lada",
    "model": "Vesta",
    "city": "Москва",
    "year": 2021,
    "budget": 1800000,
    "client_name": "Дмитрий Тестовый",
    "manager": "true"
}

headers = {'Content-Type': 'application/json; charset=utf-8'}
json_data = json.dumps(test_payload, ensure_ascii=False).encode('utf-8')

print("Sending POST request...")
print("Payload:", test_payload)

response = requests.post(SHEET_SYNC_URL, data=json_data, headers=headers, timeout=10)

print("Status:", response.status_code)

# Записываем ответ в файл
with open('simple_test_result.json', 'w', encoding='utf-8') as f:
    json.dump(response.json(), f, ensure_ascii=False, indent=2)

print("Response saved to simple_test_result.json")

result = response.json()

# Проверяем city
city_received = result.get('debug_received_data', {}).get('city', '')
city_expected = test_payload['city']
city_extracted = result.get('debug_extracted', {}).get('city', '')
city_col_index = result.get('debug_col_indexes', {}).get('city', 'N/A')

print(f"\n=== CITY DEBUG ===")
print(f"Expected city: {city_expected}")
print(f"Received city (in data): {city_received}")
print(f"Extracted city (by GAS): {city_extracted}")
print(f"City column index: {city_col_index}")
print(f"Match: {city_received == city_expected and city_extracted == city_expected}")

# Проверяем client_name
name_received = result.get('debug_received_data', {}).get('client_name', '')
name_expected = test_payload['client_name']
name_extracted = result.get('debug_extracted', {}).get('client_name', '')
name_col_index = result.get('debug_col_indexes', {}).get('client_name', 'N/A')

print(f"\n=== CLIENT_NAME DEBUG ===")
print(f"Expected name: {name_expected}")
print(f"Received name (in data): {name_received}")
print(f"Extracted name (by GAS): {name_extracted}")
print(f"Client_name column index: {name_col_index}")
print(f"Match: {name_received == name_expected and name_extracted == name_expected}")
