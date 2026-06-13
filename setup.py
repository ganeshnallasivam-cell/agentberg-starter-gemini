"""
setup.py — one-time onboarding. Sets your agent's CHARACTER (persona, risk, goals).

    python setup.py

Answer each question, or press Enter to let the agent decide (it uses the kit's
sensible default). Re-run anytime to update; your agent operates by this character
until you change it. The agent can also ask these questions conversationally — see
AGENTS.md — but the list is always the same.
"""

import character


def main():
    print("\nAgentberg agent setup — answer, or press Enter to let the agent decide.\n")
    existing = character.load()
    answers = dict(existing)

    for q in character.QUESTIONS:
        current = existing.get(q["id"], q.get("default"))
        prompt = q["q"]
        if q.get("options"):
            prompt += f"  [{'/'.join(q['options'])}]"
        if current not in (None, "", []):
            prompt += f"  (current: {current})"
        raw = input(prompt + "\n> ").strip()

        if not raw:  # deferred
            if q.get("required") and not current:
                while not raw:
                    raw = input("(required) > ").strip()
                answers[q["id"]] = character.coerce(q, raw)
            else:
                answers[q["id"]] = current  # keep existing / kit default
            continue
        answers[q["id"]] = character.coerce(q, raw)

    character.save(answers)
    print("\n✓ Saved character.json")
    print(f"  {character.summary()}")
    print("  Your agent will operate by this until you ask it to change.\n")


if __name__ == "__main__":
    main()
