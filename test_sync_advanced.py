"""Продвинутый тест синхронизации с записью в файл для проверки кодировки."""
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

SHEET_SYNC_URL = os.getenv(
    "SHEET_SYNC_URL",
    "https://script.google.com/macros/s/AKfycbxkA7StolIG29wpoe26bM2Q1ZOasmbvZbQqxHJhoTWaUNbYG5HlTekVlviTaCab4ce2/exec",
)

# Тестовые данные с городом "Москва"
test_payload = {
    "phone": "79991234568",  # Другой номер для нового теста
    "brand": "Haval",
    "model": "Jolion",
    "city": "Санкт-Петербург",
    "year": 2022,
    "budget": 2500000,
}

print("Testing POST request with city in Cyrillic...")

# Отправляем POST запрос
headers = {'Content-Type': 'application/json; charset=utf-8'}
json_data = json.dumps(test_payload, ensure_ascii=False).encode('utf-8')

response = requests.post(
    SHEET_SYNC_URL,
    data=json_data,
    headers=headers,
    timeout=10
)

# Записываем результат в файл
with open('test_result.json', 'w', encoding='utf-8') as f:
    json.dump({
        'status_code': response.status_code,
        'request_payload': test_payload,
        'response': response.json() if response.status_code == 200 else response.text
    }, f, ensure_ascii=False, indent=2)

print(f"Status: {response.status_code}")
print("Result saved to test_result.json")

# Проверяем результат
try:
    result = response.json()
    received_city = result.get('debug_received_data', {}).get('city', '')
    expected_city = test_payload['city']

    print(f"Expected city: {expected_city}")
    print(f"Received city: {received_city}")
    print(f"Match: {received_city == expected_city}")

    # Выводим байты для диагностики
    print(f"\nExpected city bytes: {expected_city.encode('utf-8')}")
    print(f"Received city bytes: {received_city.encode('utf-8')}")

except Exception as e:
    print(f"Error: {e}")
