# Clinical Voice AI Prototype

A modular system that bridges the gap between messy voice transcripts and safe clinical summaries. The core components are:

- **Cleaner**: Handles disfluencies, self-corrections, and extracts clinical entities
- **SafetyChecker**: Flags high-risk medical queries 
- **VoiceAgent**: Orchestrates cleaning + safety checks + state tracking across conversation turns

## Assumptions

- Input transcripts are always speaker-labeled (Clinician/Patient) as in the test data
- ASR quality is reasonably good—not handling heavily misinterpreted medical terminology (though I note where this would matter below)
- The system is for cleaning patient data; clinician responses are processed but not safety-checked

## Key Design Decisions & Trade-offs

### On Text Cleaning

I opted for a **rule-based + lightweight NER approach** over LLM-based preprocessing, for three reasons:

1. **Interpretability** - In clinical contexts, I need to know exactly why something was changed, LLMs make this harder.
2. **Avoiding hallucination risk** - LLMs could "fix" things that shouldn't be fixed, or introduce errors when correcting medical terminology.
3. **Efficiency** - Regex for predictable patterns (disfluencies) is fast and transparent. Only use heavier tools (spaCy NER) where linguistic understanding matters (self-correction).

On another note, removing all hesitation markers (`um`, `...`) erases the patient's confidence level, which a reviewing clinician might find useful. If I had more time, I'd add confidence annotations to the metadata so nothing gets lost.

### On Self-Correction Logic

This was the trickiest part/what I spent most of my time on. The task is ambiguous because:
- Correction markers are easy (`no`, `wait`, `actually`)
- But identifying what's being corrected is hard when it could span multiple words/entities

My approach: Use spaCy NER to find entities (medications, symptoms, body parts), then apply corrections to the most recent entity of the same type, otherwise preceding meaningful token. I added an entity ruler with common NHS medications since these are often OOD for general NER models. I tried some clinical NER models but these actually performed worse globally, would've experimented more had I had more time.

As such I stuck with `en_core_web_sm` + custom patterns, tracking both the original term and the correction, because auditing these changes is critical for clinical QA.

### On Safety Guardrails

Taking a more conservative approach, the SafetyChecker flags anything that combines:
- A question (`should I`, `can I`, `is it dangerous`)
- AND medication changes (`stop`, `double`, `increase`)
- OR dangerous symptoms (`chest pain`, `can't breathe`)


This is a **high-precision, lower-recall** approach. I'd rather over-flag than miss a dangerous query. In production, I'd expand this using the NHS symptoms database (https://www.nhs.uk/symptoms/) and potentially add severity scoring.

**Design question I grappled with:** Should the agent flag high-risk *symptoms* even if the patient isn't explicitly asking for advice? I.e. is any response to an urgent medical situation query considered advice? For now, I only flag when there's an explicit question, but this could be tuned based on clinical protocols.


## What I'd Do With More Time

1. **Better medication handling** - Integrate the full NHS medicines database instead of hardcoding. Handle phonetic misspellings from ASR (`propanol` → `propranolol`).

2. **Confidence scoring** - Add metadata about how certain the cleaner is about corrections, especially for complex self-corrections or ambiguous entity boundaries.

3. **Test suite** - Unit tests for edge cases (nested corrections, multiple entities in one phrase, ambiguous pronouns).

4. **LLM-augmented correction** - Experiment with using LLM for *only* the ambiguous self-correction cases, with the rule-based system as a fallback. This keeps most processing interpretable while handling edge cases better.


## Validation Plan

Before deploying to real patients, I'd measure safety by:

**1. Correctness of cleaning** - Manual review of 500+ transcript samples by clinical annotators. Key metrics: Did we preserve the right information? Did self-corrections resolve correctly? Are there any introduced errors?

**2. Safety recall** - Testing with synthetic dangerous queries. Ideally >99% recall on medication-change questions and emergency symptoms, since a missed dangerous query is worse than a mistakenly flagged safe one.

**3. False positive rate** - Track how often the safety checker wrongly flags questions. If it's too high, clinicians might start ignoring the flags (alarm fatigue).

I'd also do **A/B testing with synthetic data** before real patients by generating messy transcripts programmatically and measuring entity extraction accuracy, correction precision, and safety flag precision/recall.

## AI Tool Usage

- **ChatGPT/Claude** - Helped with regex pattern syntax for disfluency removal
- Used for debugging spaCy entity ruler syntax
- **Cursor** - Used for readme template

## Running the Code

```bash
pip install spacy
python -m spacy download en_core_web_sm
python test.py
```
