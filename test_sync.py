"""Тестовый скрипт для проверки синхронизации данных с Google Apps Script."""
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
    "phone": "79991234567",
    "brand": "Lada",
    "model": "Granta",
    "city": "Москва",
    "year": 2020,
    "budget": 1500000,
}

print("=" * 80)
print("ТЕСТ СИНХРОНИЗАЦИИ С GOOGLE APPS SCRIPT (POST)")
print("=" * 80)
print(f"\nURL: {SHEET_SYNC_URL}")
print(f"\nТестовые данные: {test_payload}")

# Отправляем POST запрос с JSON в теле
try:
    headers = {'Content-Type': 'application/json; charset=utf-8'}
    json_data = json.dumps(test_payload, ensure_ascii=False).encode('utf-8')

    print(f"\nJSON данные: {json_data.decode('utf-8')}")

    response = requests.post(
        SHEET_SYNC_URL,
        data=json_data,
        headers=headers,
        timeout=10
    )

    print(f"\nСтатус ответа: {response.status_code}")
    print(f"Тело ответа:\n{response.text}")

    # Пробуем распарсить JSON ответ
    try:
        json_response = response.json()
        print(f"\nJSON ответ (форматированный):")
        print(json.dumps(json_response, indent=2, ensure_ascii=False))

        # Проверяем, что пришло в debug_received_data
        if "debug_received_data" in json_response:
            print(f"\nПолученные данные на стороне GAS:")
            print(json.dumps(json_response["debug_received_data"], indent=2, ensure_ascii=False))

            # Проверяем город
            received_city = json_response["debug_received_data"].get("city", "")
            expected_city = "Москва"
            if received_city == expected_city:
                print(f"\n✅ УСПЕХ: Город передан корректно: '{received_city}'")
            else:
                print(f"\n❌ ОШИБКА: Город передан некорректно!")
                print(f"   Ожидалось: '{expected_city}'")
                print(f"   Получено: '{received_city}'")
    except Exception as e:
        print(f"(Ошибка парсинга JSON: {e})")

except Exception as e:
    print(f"\nОШИБКА: {e}")

print("\n" + "=" * 80)
