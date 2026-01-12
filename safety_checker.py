
# flags queries about medication changes or dangerous symptoms.

class SafetyChecker:
    
    # any question about changing medication = high risk
    MEDICATION_QUESTIONS = ['stop', 'double', 'increase', 'skip', 'quit']
    
    # illustrative list of serious symptoms, in the future would use NHS symptoms database: https://www.nhs.uk/symptoms/
    DANGEROUS_SYMPTOMS = ['chest pain', 'can\'t breathe', 'severe']
    
    # question words
    ASKING = ['should i', 'can i', 'is it safe', 'is it dangerous', 'what do i']

    def check(self, text):
        text_lower = text.lower()
        
        # flag if asking about medication changes or dangerous symptoms
        has_question = any(q in text_lower for q in self.ASKING)
        mentions_med_change = any(m in text_lower for m in self.MEDICATION_QUESTIONS)
        mentions_danger = any(s in text_lower for s in self.DANGEROUS_SYMPTOMS)
        
        is_high_risk = (has_question and mentions_med_change) or (has_question and mentions_danger)
        
        if is_high_risk:
            return {
                'risk_level': 'high',
                'is_safe': False,
                'message': "I cannot provide medical advice. Please contact your GP immediately."
            }
        
        return {
            'risk_level': 'low',
            'is_safe': True,
            'message': None
        }