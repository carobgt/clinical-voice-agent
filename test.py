# testing 
from conversation_manager import ConvoManager

# sample data
test_transcript = [
    ("Clinician", "How long has this been going on?"),
    ("Patient", "It started like, uh, last Tuesday? No, wait, two Tuesdays ago."),
    ("Patient", "I've been taking... [pause]... um, propanol? No, pro-pran-o-lol for the shakes."),
    ("Patient", "But my heart feels kinda... fluttery? Is that dangerous? Should I stop taking it?")
]

manager = ConvoManager()

for speaker, text in test_transcript:
    result = manager.process_utterance(text, speaker)
    print(f"\n{speaker}: {text}")
    print(f"Cleaned: {result['cleaned_text']}")
    print(f"Safety: {result['safety_assessment']}")