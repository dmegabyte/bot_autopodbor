"""Test script to verify incremental sync with tag (without phone)"""

import sys
sys.path.insert(0, r'C:\Users\User\Desktop\VICTORY\bot_autopodbor')

from bot import _build_sync_payload


def test_tag_without_phone():
    """Test that payload includes tag and tg_user_id but no phone"""
    user_data = {
        "tag": "vk_campaign",
        "tg_user_id": "123456789",
        "tg_username": "testuser"
    }

    payload = _build_sync_payload(user_data)
    print("Test 1: Tag without phone (initial deeplink sync)")
    print(f"Input: {user_data}")
    print(f"Output: {payload}")
    print(f"Has tag: {'tag' in payload}")
    print(f"Has tg_user_id: {'tg_user_id' in payload}")
    print(f"Has phone: {'phone' in payload}")

    assert "tag" in payload, "Tag should be present"
    assert payload["tag"] == "vk_campaign", "Tag value should match"
    assert "tg_user_id" in payload, "tg_user_id should be present"
    assert "phone" not in payload, "Phone should NOT be present (filtered out as None)"
    print("[PASS] Test 1 PASSED\n")


def test_tag_with_phone_added_later():
    """Test that payload includes tag, tg_user_id AND phone when user enters phone"""
    user_data = {
        "tag": "instagram_ads",
        "tg_user_id": "987654321",
        "tg_username": "testuser2",
        "phone": "79991234567"
    }

    payload = _build_sync_payload(user_data)
    print("Test 2: Tag with phone added (second sync)")
    print(f"Input: {user_data}")
    print(f"Output: {payload}")
    print(f"Has tag: {'tag' in payload}")
    print(f"Has tg_user_id: {'tg_user_id' in payload}")
    print(f"Has phone: {'phone' in payload}")

    assert "tag" in payload, "Tag should be present"
    assert payload["tag"] == "instagram_ads", "Tag value should match"
    assert "tg_user_id" in payload, "tg_user_id should be present"
    assert "phone" in payload, "Phone SHOULD be present"
    assert payload["phone"] == "79991234567", "Phone value should match"
    print("[PASS] Test 2 PASSED\n")


def test_no_tag_with_phone():
    """Test that payload works without tag (normal flow)"""
    user_data = {
        "tg_user_id": "555555555",
        "tg_username": "testuser3",
        "phone": "79999999999",
        "brand": "Toyota"
    }

    payload = _build_sync_payload(user_data)
    print("Test 3: No tag, normal flow")
    print(f"Input: {user_data}")
    print(f"Output: {payload}")
    print(f"Has tag: {'tag' in payload}")
    print(f"Has phone: {'phone' in payload}")
    print(f"Has brand: {'brand' in payload}")

    assert "tag" not in payload, "Tag should NOT be present"
    assert "phone" in payload, "Phone should be present"
    assert "brand" in payload, "Brand should be present"
    print("[PASS] Test 3 PASSED\n")


if __name__ == "__main__":
    print("="*60)
    print("TESTING INCREMENTAL SYNC WITH TAG")
    print("="*60 + "\n")

    try:
        test_tag_without_phone()
        test_tag_with_phone_added_later()
        test_no_tag_with_phone()

        print("="*60)
        print("ALL TESTS PASSED!")
        print("="*60)
        print("\nSUMMARY:")
        print("- Tag writes immediately without phone (with tg_user_id)")
        print("- Tag persists when phone is added later")
        print("- Normal flow without tag works as before")
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
