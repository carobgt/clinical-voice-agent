
# flags queries about medication changes or dangerous symptoms.

class SafetyChecker:
    #TODO: fix the illustrative list of high risk terms, check nhs website for symptoms list
    # decide whether or not to just not give any advice
    
    # any question about changing medication = high risk
    MEDICATION_QUESTIONS = ['stop', 'double', 'increase', 'skip', 'quit']
    
    # illustrative list of serious symptoms
    DANGEROUS_SYMPTOMS = ['chest pain', 'can\'t breathe', 'severe']
    
    # question words
    ASKING = ['should i', 'can i', 'is it safe', 'is it dangerous']

    def check(self, text):
        text_lower = text.lower()
        
        # flag if asking about medication changes
        has_question = any(q in text_lower for q in self.ASKING)
        mentions_med_change = any(m in text_lower for m in self.MEDICATION_QUESTIONS)
        mentions_danger = any(s in text_lower for s in self.DANGEROUS_SYMPTOMS)
        
        #TODO: rethink this, should we flag if patient doesnt ask a question but symptoms are dangerous? (probably no)
        is_high_risk = (has_question and mentions_med_change) or mentions_danger
        
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