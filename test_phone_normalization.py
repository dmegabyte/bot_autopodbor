import sys

sys.path.insert(0, r"C:\Users\User\Desktop\VICTORY\bot_autopodbor")

from bot import normalize_phone_number


def run_tests():
    cases = {
        "+7 (999) 123-45-67": "79991234567",
        "89991234567": "79991234567",
        "9991234567": "79991234567",
        "": "",
        "abc123": "",
        "123": "",
        "+1 234 567 8901": "",
    }

    for raw, expected in cases.items():
        result = normalize_phone_number(raw)
        print(f"{raw!r} -> {result!r} (expected {expected!r})")
        assert result == expected, f"Failed for {raw!r}"

    print("All phone normalization tests passed.")


if __name__ == "__main__":
    run_tests()
