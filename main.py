from conversation_manager import Cleaner
from safety_checker import SafetyChecker

# main orchestrator
class VoiceAgentBrain:

    def __init__(self):
        self.cleaner = Cleaner()
        self.safety = SafetyChecker() 
        self.state = {
            'symptoms': [],
            'medications': [],
            'body parts': [],
            'turn_count': 0
        }
    
    def process(self, raw_text):

        cleaned_output = self.cleaner.clean(raw_text)
        cleaned_text = cleaned_output['cleaned_text']
        
        for key in ['medications', 'symptoms', 'body parts']:
            self.state[key] = list(set(self.state.get(key, []) + cleaned_output['entities'][key]))
        
        # safety check
        safety_output = self.safety.check(cleaned_text)  # Fix method call
        
        # update state
        self.state['turn_count'] += 1
        
        return {
            'cleaned_text': cleaned_text,
            'safety': safety_output,
            'state': self.state,
            'should_respond': safety_output['risk_level'] == 'low'
        }
    
    def reset_state(self):
        """Reset conversation state"""
        self.state = {
            'symptoms': [],
            'medications': [],
            'body parts': [],
            'turn_count': 0
        }
