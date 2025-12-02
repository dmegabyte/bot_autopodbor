"""Полный тест процесса с эмуляцией действий пользователя."""
import json
import requests
import os
from dotenv import load_dotenv

load_dotenv()

SHEET_SYNC_URL = os.getenv(
    "SHEET_SYNC_URL",
    "https://script.google.com/macros/s/AKfycbxkA7StolIG29wpoe26bM2Q1ZOasmbvZbQqxHJhoTWaUNbYG5HlTekVlviTaCab4ce2/exec",
)

# Эмулируем последовательность действий пользователя
steps = [
    {
        "step": "1. Phone received",
        "payload": {
            "phone": "79991234999",
        }
    },
    {
        "step": "2. Brand selected",
        "payload": {
            "phone": "79991234999",
            "brand": "Lada",
        }
    },
    {
        "step": "3. Model received",
        "payload": {
            "phone": "79991234999",
            "brand": "Lada",
            "model": "Vesta",
        }
    },
    {
        "step": "4. City selected",
        "payload": {
            "phone": "79991234999",
            "brand": "Lada",
            "model": "Vesta",
            "city": "Москва",
        }
    },
    {
        "step": "5. Year received",
        "payload": {
            "phone": "79991234999",
            "brand": "Lada",
            "model": "Vesta",
            "city": "Москва",
            "year": 2021,
        }
    },
    {
        "step": "6. Budget received",
        "payload": {
            "phone": "79991234999",
            "brand": "Lada",
            "model": "Vesta",
            "city": "Москва",
            "year": 2021,
            "budget": 1800000,
        }
    },
    {
        "step": "7. Manager consent",
        "payload": {
            "phone": "79991234999",
            "brand": "Lada",
            "model": "Vesta",
            "city": "Москва",
            "year": 2021,
            "budget": 1800000,
            "manager": "true",
            "client_name": "Дмитрий Иванов",
        }
    },
]

print("=" * 80)
print("ПОЛНЫЙ ТЕСТ ПРОЦЕССА ЗАПОЛНЕНИЯ АНКЕТЫ")
print("=" * 80)

headers = {'Content-Type': 'application/json; charset=utf-8'}

for i, step_data in enumerate(steps, 1):
    print(f"\n{step_data['step']}")
    print(f"Payload: {step_data['payload']}")

    json_data = json.dumps(step_data['payload'], ensure_ascii=False).encode('utf-8')

    try:
        response = requests.post(
            SHEET_SYNC_URL,
            data=json_data,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            print(f"✓ Status: {result.get('status')}, Action: {result.get('action')}")

            # Проверяем город на шаге 4
            if i == 4:
                received_city = result.get('debug_received_data', {}).get('city', '')
                if received_city == "Москва":
                    print(f"✓✓ УСПЕХ: Город '{received_city}' передан корректно!")
                else:
                    print(f"✗✗ ОШИБКА: Город некорректен! Ожидалось 'Москва', получено '{received_city}'")
        else:
            print(f"X Error: HTTP {response.status_code}")

    except Exception as e:
        print(f"X Exception: {e}")

print("\n" + "=" * 80)
print("ТЕСТ ЗАВЕРШЕН")
print("=" * 80)
