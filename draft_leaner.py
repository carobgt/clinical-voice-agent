import re
from typing import Dict, List, Tuple


class Cleaner:
    """Cleans noisy speech-to-text input for clinical validity"""
    
    DISFLUENCIES = [
        'um', 'uh', 'er', 'ah', 'like', 'you know', 'i mean',
        'sort of', 'kind of', 'basically', 'actually'
    ]
    
    def __init__(self):
        self.correction_patterns = [
            r'(.+?)\s+(?:no|wait|sorry|actually|i mean)\s*,?\s*(.+)',
            r'(.+?)\s+(?:or|rather)\s+(.+)',
        ]
        self.noise_pattern = r'\[(?:noise|inaudible|unclear|cough|pause)\]'
        
    
    def corrections(self, text: str) -> str:
        """Keep only corrected version of self-corrections"""
        for pattern in self.correction_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                after = match.group(2).strip()
                text = text[:match.start()] + after + text[match.end():]
        return text
    
    def disfluencies(self, text: str) -> str:
        """Remove speech disfluencies"""
        for disfluency in self.DISFLUENCIES:
            pattern = r'\b' + re.escape(disfluency) + r'\b[,.]?\s*'
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        return text
    
    def _clean_whitespace(self, text: str) -> str:
        """Clean up whitespace and punctuation"""
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\s+([,.?!])', r'\1', text)
        text = re.sub(r'[,]+', ',', text)
        text = re.sub(r'\.+', '.', text)
        return text.strip()

    def clean(self, raw_text: str) -> str:
        """Clean noisy input and return processed text"""
        text = raw_text.lower().strip()
        
        # Remove noise markers
        text = re.sub(self.noise_pattern, '', text)
        
        # Handle self-corrections
        text = self.corrections(text)
        
        # Remove disfluencies
        text = self.disfluencies(text)
        
        # Clean whitespace
        text = self._clean_whitespace(text)
        
        return text


class SafetyGuardrails:
    """Implements safety checks for medical queries"""
    
    HIGH_RISK_KEYWORDS = {
        'dosage': ['double', 'triple', 'increase', 'more', 'extra'],
        'cardiac': ['heart attack', 'chest pain', 'heart pain', 'cardiac arrest',
                   'irregular heartbeat', 'fluttery', 'palpitations'],
        'breathing': ['can\'t breathe', 'difficulty breathing', 'shortness of breath',
                     'choking', 'suffocating'],
        'severe_pain': ['severe pain', 'worst pain', 'unbearable', 'extreme pain'],
        'bleeding': ['bleeding', 'blood', 'hemorrhage'],
        'mental_health': ['suicide', 'kill myself', 'end it', 'self-harm', 'hurt myself'],
        'allergic': ['allergic reaction', 'anaphylaxis', 'swelling throat', 'hives'],
        'neurological': ['stroke', 'seizure', 'paralysis', 'numb', 'tingling'],
        'medication_danger': ['stopped taking', 'ran out', 'skip', 'forgot']
    }
    
    CRITICAL_COMBINATIONS = [
        (['heart', 'chest', 'cardiac'], ['pain', 'ache', 'pressure', 'tight']),
        (['breathe', 'breathing'], ['difficult', 'hard', 'can\'t', 'cannot']),
        (['dose', 'dosage', 'medication'], ['double', 'increase', 'more', 'change']),
    ]
    
    FALLBACK_MESSAGES = {
        'high': "I cannot provide medical advice on this matter. Please contact your GP or healthcare provider immediately.",
        'critical': "This sounds like a medical emergency. Please call emergency services (999 in UK, 911 in US) or go to A&E immediately."
    }
    
    def check_safety(self, text: str) -> Dict:
        """Check if query is safe to respond to"""
        text_lower = text.lower()
        risk_level = 'low'
        triggered = []
        
        # Check high-risk keywords
        for category, keywords in self.HIGH_RISK_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    triggered.append(f"{category}:{keyword}")
                    
                    if category in ['cardiac', 'breathing', 'mental_health', 'allergic']:
                        risk_level = 'critical'
                    elif risk_level != 'critical' and category in ['dosage', 'severe_pain', 'medication_danger']:
                        risk_level = 'high'
                    elif risk_level == 'low':
                        risk_level = 'medium'
        
        # Check dangerous combinations
        for keywords1, keywords2 in self.CRITICAL_COMBINATIONS:
            has_first = any(k in text_lower for k in keywords1)
            has_second = any(k in text_lower for k in keywords2)
            if has_first and has_second:
                risk_level = 'critical'
                triggered.append('combination:critical')
        
        # Generate response
        is_safe = risk_level in ['low', 'medium']
        
        if risk_level == 'critical':
            message = self.FALLBACK_MESSAGES['critical']
        elif risk_level == 'high':
            message = self.FALLBACK_MESSAGES['high']
        elif risk_level == 'medium':
            message = "I can provide general information, but please consult with your healthcare provider for personalized medical advice."
        else:
            message = "Safe to provide general information."
        
        return {
            'risk_level': risk_level,
            'is_safe': is_safe,
            'message': message,
            'triggered': triggered
        }


class VoiceAgentBrain:
    """Main orchestrator for the voice agent brain"""
    
    def __init__(self):
        self.cleaner = Cleaner()
        self.safety = SafetyGuardrails()
        self.state = {
            'symptoms': [],
            'medications': [],
            'conditions': [],
            'turn_count': 0
        }
    
    def process(self, raw_text: str) -> Dict:
        """
        Process a single utterance from speech-to-text
        
        Returns:
            Dict with cleaned_text, safety check, and conversation state
        """
        # Clean the input
        cleaned_text = self.cleaner.clean(raw_text)
        
        # Safety check
        safety = self.safety.check_safety(cleaned_text)
        
        # Update state
        self.state['turn_count'] += 1
        
        return {
            'cleaned_text': cleaned_text,
            'safety': safety,
            'state': self.state,
            'should_respond': safety['is_safe']
        }
    
    def reset_state(self):
        """Reset conversation state"""
        self.state = {
            'symptoms': [],
            'medications': [],
            'conditions': [],
            'turn_count': 0
        }


# Quick test
if __name__ == "__main__":
    brain = VoiceAgentBrain()
    
    # Test 1: Self-correction
    test1 = "My knee hurts, um, I think it's... [noise]... arthritis? I take, uh, Glucophage... no, wait, Ibuprofen for it."
    result1 = brain.process(test1)
    print(f"Original: {test1}")
    print(f"Cleaned:  {result1['cleaned_text']}\n")
    
    # Test 2: High-risk query
    test2 = "My heart feels fluttery when I take this. Should I double the dose?"
    result2 = brain.process(test2)
    print(f"Query:    {test2}")
    print(f"Risk:     {result2['safety']['risk_level']}")
    print(f"Safe:     {result2['safety']['is_safe']}")
    print(f"Message:  {result2['safety']['message']}\n")
    
    # Test 3: Critical emergency
    test3 = "I have severe chest pain and I can't breathe properly"
    result3 = brain.process(test3)
    print(f"Query:    {test3}")
    print(f"Risk:     {result3['safety']['risk_level']}")
    print(f"Message:  {result3['safety']['message']}")