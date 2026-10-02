# Voice and conversation

These are the speaking rules from SPEC.md §5.1. Every sentence the assistant says is a template in `src/saathi/dialog/phrases/hi.yaml`.

- Keep each sentence to 12 words or fewer.
- Ask one question per turn.
- Speak slowly, at about 0.85 of normal rate.
- Address the elder with the honorific the caregiver chose.
- Confirm a critical answer, such as whether a dose was taken, before closing.
- After 6 seconds of silence, repeat the question once. A second silence ends the call politely.
- Do not use English medical jargon.
- Do not give medical advice, suggest a dose, interpret a symptom, or change a schedule.
- On an emergency phrase, tell the elder that the family is being alerted and that they can call 112, then notify the emergency contacts.
