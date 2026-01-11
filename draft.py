import re
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

# risk levels for safety checks
class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# response structure for safety checks
@dataclass
class SafetyResponse:
    risk_level: RiskLevel
    is_safe: bool
    message: str
    triggered_keywords: List[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class PatientState:
    """Tracks patient conversation state across turns"""
    symptoms: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    conditions: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    turn_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def add_symptom(self, symptom: str):
        if symptom and symptom not in self.symptoms:
            self.symptoms.append(symptom)
    
    def add_medication(self, medication: str):
        if medication and medication not in self.medications:
            self.medications.append(medication)
    
    def add_condition(self, condition: str):
        if condition and condition not in self.conditions:
            self.conditions.append(condition)


class NoisyCleaner:
    """Cleans noisy speech-to-text input for clinical validity"""
    
    # Common disfluencies to remove
    DISFLUENCIES = [
        'um', 'uh', 'er', 'ah', 'like', 'you know', 'i mean',
        'sort of', 'kind of', 'basically', 'actually'
    ]
    
    # Common medication names for validation
    COMMON_MEDICATIONS = [
        'ibuprofen', 'paracetamol', 'aspirin', 'metformin', 'lisinopril',
        'amlodipine', 'omeprazole', 'simvastatin', 'atorvastatin',
        'levothyroxine', 'albuterol', 'metoprolol', 'losartan',
        'gabapentin', 'hydrochlorothiazide', 'sertraline', 'prednisone',
        'amoxicillin', 'warfarin', 'insulin', 'glucophage'
    ]
    
    def __init__(self):
        # Patterns for self-correction detection
        self.correction_patterns = [
            r'(.+?)\s+(?:no|wait|sorry|actually|i mean)\s*,?\s*(.+)',
            r'(.+?)\s+(?:or|rather)\s+(.+)',
        ]
        
        # Noise markers
        self.noise_pattern = r'\[(?:noise|inaudible|unclear|cough|pause)\]'
        
    def clean(self, raw_text: str) -> Dict:
        """
        Main cleaning function that processes noisy input
        
        Args:
            raw_text: Raw speech-to-text output
            
        Returns:
            Dictionary with cleaned text and metadata
        """
        text = raw_text.lower().strip()
        
        # Track what was cleaned
        metadata = {
            'original': raw_text,
            'corrections_found': [],
            'disfluencies_removed': [],
            'noise_removed': False
        }
        
        # Step 1: Remove noise markers
        if re.search(self.noise_pattern, text):
            text = re.sub(self.noise_pattern, '', text)
            metadata['noise_removed'] = True
        
        # Step 2: Handle self-corrections
        text, corrections = self._handle_corrections(text)
        metadata['corrections_found'] = corrections
        
        # Step 3: Remove disfluencies
        text, removed_disfluencies = self._remove_disfluencies(text)
        metadata['disfluencies_removed'] = removed_disfluencies
        
        # Step 4: Clean up extra whitespace and punctuation
        text = self._clean_whitespace(text)
        
        # Step 5: Extract clinical entities
        entities = self._extract_entities(text)
        
        return {
            'cleaned_text': text,
            'metadata': metadata,
            'entities': entities
        }
    
    def _handle_corrections(self, text: str) -> Tuple[str, List[Dict]]:
        """Detect and handle self-corrections"""
        corrections = []
        
        for pattern in self.correction_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                before = match.group(1).strip()
                after = match.group(2).strip()
                
                corrections.append({
                    'original': before,
                    'corrected_to': after
                })
                
                # Replace with corrected version
                text = text[:match.start()] + after + text[match.end():]
        
        return text, corrections
    
    def _remove_disfluencies(self, text: str) -> Tuple[str, List[str]]:
        """Remove common speech disfluencies"""
        removed = []
        
        for disfluency in self.DISFLUENCIES:
            # Match disfluency as whole word with optional punctuation
            pattern = r'\b' + re.escape(disfluency) + r'\b[,.]?\s*'
            if re.search(pattern, text, re.IGNORECASE):
                removed.append(disfluency)
                text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text, removed
    
    # def _clean_whitespace(self, text: str) -> str:
    #     """Clean up extra whitespace and punctuation"""
    #     # Remove multiple spaces
    #     text = re.sub(r'\s+', ' ', text)
    #     # Clean up punctuation spacing
    #     text = re.sub(r'\s+([,.?!])', r'\1', text)
    #     # Remove multiple punctuation
    #     text = re.sub(r'[,]+', ',', text)
    #     text = re.sub(r'\.+', '.', text)
    #     return text.strip()
    
    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract clinical entities from text"""
        entities = {
            'medications': [],
            'symptoms': [],
            'body_parts': []
        }
        
        # Extract medications
        for med in self.COMMON_MEDICATIONS:
            if re.search(r'\b' + re.escape(med) + r'\b', text, re.IGNORECASE):
                entities['medications'].append(med)
        
        # Extract body parts (simple keyword matching)
        body_parts = ['knee', 'heart', 'head', 'back', 'chest', 'stomach', 
                     'arm', 'leg', 'shoulder', 'ankle', 'wrist']
        for part in body_parts:
            if re.search(r'\b' + re.escape(part) + r'\b', text, re.IGNORECASE):
                entities['body_parts'].append(part)
        
        # Extract symptoms (simple keyword matching)
        symptoms = ['hurts', 'pain', 'ache', 'sore', 'swollen', 'fluttery',
                   'dizzy', 'nausea', 'fever', 'cough', 'tired']
        for symptom in symptoms:
            if re.search(r'\b' + re.escape(symptom) + r'\b', text, re.IGNORECASE):
                entities['symptoms'].append(symptom)
        
        return entities


class SafetyGuardrails:
    """Implements safety checks for medical queries"""
    
    # High-risk keywords and phrases
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
    
    SAFE_FALLBACK_MESSAGES = {
        RiskLevel.HIGH: "I cannot provide medical advice on this matter. Please contact your GP or healthcare provider immediately.",
        RiskLevel.CRITICAL: "This sounds like a medical emergency. Please call emergency services (999 in UK, 911 in US) or go to A&E immediately."
    }
    
    def check_safety(self, text: str) -> SafetyResponse:
        """
        Check if query is safe to respond to
        
        Args:
            text: User's query text
            
        Returns:
            SafetyResponse object with risk assessment
        """
        text_lower = text.lower()
        triggered = []
        risk_level = RiskLevel.LOW
        reasons = []
        
        # Check for high-risk keywords
        for category, keywords in self.HIGH_RISK_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    triggered.append(f"{category}:{keyword}")
                    
                    # Escalate risk based on category
                    if category in ['cardiac', 'breathing', 'mental_health', 'allergic']:
                        risk_level = max(risk_level, RiskLevel.CRITICAL, key=lambda x: x.value)
                        reasons.append(f"Critical {category} indicator detected")
                    elif category in ['dosage', 'severe_pain', 'medication_danger']:
                        risk_level = max(risk_level, RiskLevel.HIGH, key=lambda x: x.value)
                        reasons.append(f"High-risk {category} query")
                    else:
                        risk_level = max(risk_level, RiskLevel.MEDIUM, key=lambda x: x.value)
        
        # Check for dangerous combinations
        for keywords1, keywords2 in self.CRITICAL_COMBINATIONS:
            has_first = any(k in text_lower for k in keywords1)
            has_second = any(k in text_lower for k in keywords2)
            
            if has_first and has_second:
                risk_level = RiskLevel.CRITICAL
                reasons.append(f"Critical combination detected")
                triggered.append("combination:critical")
        
        # Determine if safe to respond
        is_safe = risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]
        
        # Generate appropriate message
        if risk_level == RiskLevel.CRITICAL:
            message = self.SAFE_FALLBACK_MESSAGES[RiskLevel.CRITICAL]
        elif risk_level == RiskLevel.HIGH:
            message = self.SAFE_FALLBACK_MESSAGES[RiskLevel.HIGH]
        elif risk_level == RiskLevel.MEDIUM:
            message = "I can provide general information, but please consult with your healthcare provider for personalized medical advice."
        else:
            message = "Safe to provide general information."
        
        return SafetyResponse(
            risk_level=risk_level,
            is_safe=is_safe,
            message=message,
            triggered_keywords=triggered,
            reason=" | ".join(reasons) if reasons else "No risk detected"
        )


class VoiceAgentBrain:
    """Main orchestrator for the voice agent brain"""
    
    def __init__(self):
        self.cleaner = NoisyCleaner()
        self.safety = SafetyGuardrails()
        self.state = PatientState()
    
    def process_utterance(self, raw_text: str) -> Dict:
        """
        Process a single utterance from speech-to-text
        
        Args:
            raw_text: Raw speech-to-text output
            
        Returns:
            Complete processing result including cleaned text, safety check, and state
        """
        # Step 1: Clean the input
        cleaned = self.cleaner.clean(raw_text)
        
        # Step 2: Safety check
        safety_check = self.safety.check_safety(cleaned['cleaned_text'])
        
        # Step 3: Update conversation state
        self.update_state(cleaned)
        
        # Step 4: Compile response
        return {
            'cleaned_text': cleaned['cleaned_text'],
            'metadata': cleaned['metadata'],
            'entities': cleaned['entities'],
            'safety': {
                'risk_level': safety_check.risk_level.value,
                'is_safe': safety_check.is_safe,
                'message': safety_check.message,
                'triggered_keywords': safety_check.triggered_keywords,
                'reason': safety_check.reason
            },
            'patient_state': self.state.to_dict(),
            'should_respond': safety_check.is_safe
        }
    
    def update_state(self, cleaned_data: Dict):
        """Update patient state based on cleaned data"""
        self.state.turn_count += 1
        
        entities = cleaned_data['entities']
        
        # Add medications
        for med in entities['medications']:
            self.state.add_medication(med)
        
        # Add symptoms (combine body parts with symptom descriptors)
        for symptom in entities['symptoms']:
            self.state.add_symptom(symptom)
        
        for part in entities['body_parts']:
            self.state.add_symptom(f"{part} issue")
    
    def reset_state(self):
        """Reset conversation state"""
        self.state = PatientState()


# Demo usage
if __name__ == "__main__":
    brain = VoiceAgentBrain()
    
    # Test Case 1: Self-correction with disfluencies
    print("=" * 80)
    print("TEST 1: Self-Correction with Disfluencies")
    print("=" * 80)
    
    test1 = "Patient: My knee hurts, um, I think it's... [noise]... arthritis? I take, uh, Glucophage... no, wait, Ibuprofen for it."
    result1 = brain.process_utterance(test1)
    print(f"\nOriginal: {test1}")
    print(f"\nCleaned: {result1['cleaned_text']}")
    print(f"\nMetadata: {json.dumps(result1['metadata'], indent=2)}")
    print(f"\nEntities: {json.dumps(result1['entities'], indent=2)}")
    print(f"\nSafety: {json.dumps(result1['safety'], indent=2)}")
    print(f"\nPatient State: {json.dumps(result1['patient_state'], indent=2)}")
    
    # Test Case 2: High-risk query
    print("\n" + "=" * 80)
    print("TEST 2: High-Risk Medical Query")
    print("=" * 80)
    
    test2 = "My heart feels fluttery when I take this. Should I double the dose?"
    result2 = brain.process_utterance(test2)
    print(f"\nOriginal: {test2}")
    print(f"\nCleaned: {result2['cleaned_text']}")
    print(f"\nSafety: {json.dumps(result2['safety'], indent=2)}")
    print(f"\nShould Respond: {result2['should_respond']}")
    
    # Test Case 3: Critical emergency
    print("\n" + "=" * 80)
    print("TEST 3: Critical Emergency")
    print("=" * 80)
    
    test3 = "I have severe chest pain and I can't breathe properly"
    result3 = brain.process_utterance(test3)
    print(f"\nOriginal: {test3}")
    print(f"\nSafety: {json.dumps(result3['safety'], indent=2)}")
    
    print("\n" + "=" * 80)