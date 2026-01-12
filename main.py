from cleaner import Cleaner
from safety_checker import SafetyChecker

# main orchestrator
class VoiceAgent:

    def __init__(self):
        self.cleaner = Cleaner()
        self.safety = SafetyChecker() 
        self.state = {
            'symptoms': [],
            'medications': [],
            'body_parts': [],
            'turn_count': 0
        }
    
    def process(self, raw_text):

        cleaned_output = self.cleaner.clean(raw_text)
        cleaned_text = cleaned_output['cleaned_text']
        metadata = cleaned_output['metadata']
        
        for key in ['medications', 'symptoms', 'body_parts']:
            self.state[key] = list(set(self.state.get(key, []) + cleaned_output['entities'][key]))
        
        # safety check
        safety_output = self.safety.check(cleaned_text)  
        
        # update state
        self.state['turn_count'] += 1
        
        return {
            'cleaned_text': cleaned_text,
            'metadata': metadata,
            'safety': safety_output,
            'state': self.state,
        }
    
    def reset_state(self): # reset conversation state
        self.state = {
            'symptoms': [],
            'medications': [],
            'body_parts': [],
            'turn_count': 0
        }
