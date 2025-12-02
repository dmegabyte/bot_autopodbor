"""Test script to verify tag functionality in _build_sync_payload()"""

import sys
sys.path.insert(0, r'C:\Users\User\Desktop\VICTORY\bot_autopodbor')

from bot import _build_sync_payload


def test_tag_with_data():
    """Test that tag is included when present in user_data"""
    user_data = {
        "phone": "79991234567",
        "brand": "Toyota",
        "model": "Camry",
        "city": "Москва",
        "tag": "vk_campaign"
    }

    payload = _build_sync_payload(user_data)
    print("Test 1: Tag with data")
    print(f"Input: {user_data}")
    print(f"Output: {payload}")
    print(f"Tag present: {'tag' in payload}")
    print(f"Tag value: {payload.get('tag', 'NOT FOUND')}")
    assert "tag" in payload, "Tag should be present in payload"
    assert payload["tag"] == "vk_campaign", "Tag value should match input"
    print("[PASS] Test 1 PASSED\n")


def test_tag_without_data():
    """Test that tag is not included when absent in user_data"""
    user_data = {
        "phone": "79991234567",
        "brand": "BMW",
        "model": "X5",
        "city": "Москва"
    }

    payload = _build_sync_payload(user_data)
    print("Test 2: No tag in data")
    print(f"Input: {user_data}")
    print(f"Output: {payload}")
    print(f"Tag present: {'tag' in payload}")
    print(f"Tag is None: {payload.get('tag') is None}")
    assert "tag" not in payload, "Tag should be filtered out when None"
    print("[PASS] Test 2 PASSED\n")


def test_tag_empty_string():
    """Test that empty string tag is filtered out"""
    user_data = {
        "phone": "79991234567",
        "brand": "Mercedes",
        "model": "E-Class",
        "city": "Москва",
        "tag": ""
    }

    payload = _build_sync_payload(user_data)
    print("Test 3: Empty string tag")
    print(f"Input: {user_data}")
    print(f"Output: {payload}")
    print(f"Tag present: {'tag' in payload}")
    assert "tag" not in payload, "Empty tag should be filtered out"
    print("[PASS] Test 3 PASSED\n")


def test_various_tag_formats():
    """Test various tag formats"""
    test_cases = [
        ("instagram_ads", "instagram_ads"),
        ("google_search", "google_search"),
        ("vk", "vk"),
        ("direct_link", "direct_link"),
        ("utm_source_facebook", "utm_source_facebook")
    ]

    print("Test 4: Various tag formats")
    for tag_input, expected in test_cases:
        user_data = {
            "phone": "79991234567",
            "tag": tag_input
        }
        payload = _build_sync_payload(user_data)
        print(f"  Input tag: '{tag_input}' -> Output: '{payload.get('tag', 'NOT FOUND')}'")
        assert payload.get("tag") == expected, f"Tag should match: {expected}"

    print("[PASS] Test 4 PASSED\n")


if __name__ == "__main__":
    print("="*60)
    print("TESTING TAG FEATURE IN _build_sync_payload()")
    print("="*60 + "\n")

    try:
        test_tag_with_data()
        test_tag_without_data()
        test_tag_empty_string()
        test_various_tag_formats()

        print("="*60)
        print("ALL TESTS PASSED!")
        print("="*60)
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
