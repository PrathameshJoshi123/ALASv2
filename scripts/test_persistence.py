import requests
import json
import sys

CASE_ID = "f2fdb651-5e74-4363-b1c7-b82d7e831687"
BASE_URL = "http://127.0.0.1:8000/api/v1/cases"

def main():
    # 1. Fetch current status
    res0 = requests.get(f"{BASE_URL}/{CASE_ID}/debate/status", timeout=30)
    print("Initial status:", res0.status_code, "Turns count:", len(res0.json().get("debate_turns", [])))

    # 2. Inject Turn as Petitioner (forms Round 2)
    print("2. Injecting intervention as Petitioner...")
    payload1 = {
        "custom_argument": "We have contemporaneous WhatsApp chats showing fraudulent inducement from the very inception before fund transfer.",
        "represented_side": "petitioner"
    }
    res1 = requests.post(f"{BASE_URL}/{CASE_ID}/debate/turn", json=payload1, timeout=90)
    print("Intervention 1 status:", res1.status_code)
    state1 = res1.json()
    print("Turns count after intervention 1:", len(state1.get("debate_turns", [])))

    # 3. Inject Turn as Respondent/Defense (forms Round 3)
    print("3. Injecting intervention as Respondent/Defense...")
    payload2 = {
        "custom_argument": "The WhatsApp messages lack electronic hash certificate under Section 65B(4) / Section 63 BSA, rendering them completely inadmissible as secondary digital evidence.",
        "represented_side": "respondent"
    }
    res2 = requests.post(f"{BASE_URL}/{CASE_ID}/debate/turn", json=payload2, timeout=90)
    print("Intervention 2 status:", res2.status_code)
    state2 = res2.json()
    print("Turns count after intervention 2:", len(state2.get("debate_turns", [])))

    print("\n--- ALL TURNS PERSISTED IN MEMORY ---")
    for t in state2.get("debate_turns", []):
        print(f"Turn #{t.get('turn_number')} | Round {t.get('round_number')} | Speaker: {t.get('speaker')} | Side: {t.get('speaker_side')} | Title: {t.get('title')}")

if __name__ == "__main__":
    main()
