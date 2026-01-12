import re
import spacy

class Cleaner:
    
    def __init__(self):
        # ner model loading
        self.nlp = spacy.load("en_core_web_sm")
        
        # needed to add entity ruler to catch OOD terms
        ruler = self.nlp.add_pipe("entity_ruler", before="ner")
        patterns = [
            # hard coding here bc not much time, in the future would use NHS A-Z medicines database
            {"label": "MEDICATION", "pattern": [{"LOWER": "ibuprofen"}]},
            {"label": "MEDICATION", "pattern": [{"LOWER": "glucophage"}]},
            {"label": "MEDICATION", "pattern": [{"LOWER": "propranolol"}]},
            # {"label": "MEDICATION", "pattern": [{"LOWER": "propanol"}]},
            # {"label": "MEDICATION", "pattern": "pro-pran-o-lol"},
            {"label": "MEDICATION", "pattern": [{"LOWER": "paracetamol"}]},
            
            # body parts, illustrative again
            {"label": "BODY_PART", "pattern": [{"LOWER": "knee"}]},
            {"label": "BODY_PART", "pattern": [{"LOWER": "heart"}]},
        ]
        ruler.add_patterns(patterns)
    
    # illustrative list of disfluencies, should cover most
    disfl = ['um', 'uh', 'er', 'ah', 'like', 'you know', 
    'i mean', 'sort of', 'kind of', 'kinda', 'basically', 'actually']
    
    correction_markers = ['no', 'wait', 'sorry', 'actually', 'i mean', 'or', 'rather']

    noise_patterns = r'\[(?:noise|inaudible|unclear|cough|pause)\]'
    
    #TODO: add metada to track what was removed/corrected, important for validation plan
    # also could add confidence levels for human reviewers s.t. text isnt overprocessed

    
    # VERSION 2, using ner instead of regex (too brittle)
    def clean_corrections(self, text):
        """
        Handle self-corrections using NER to detect entity replacements.
        Process the full text to handle corrections that span multiple clauses.
        """
        corrections = []
        
        # removing ellipses, dashes, assuming here that they indicate pauses rather than punctuation
        text = re.sub(r'\.{2,}', ' ', text)
        text = text.replace('-', '')
        
        # split into segments around correction markers while keeping context
        doc = self.nlp(text)
        
        # find all entities first
        entities = list(doc.ents)
        
        # track which entities have been replaced
        replacements = {}
        
        # look for correction patterns in the text
        correction_pattern = r'\b(no|wait|sorry|actually|i mean|or|rather)\b[,\s]*'
        
        for match in re.finditer(correction_pattern, text, re.IGNORECASE):
            marker_pos = match.end()
            marker_text = match.group(1).lower()
            
            # find entities before and after the marker
            entities_before = [e for e in entities if e.end_char <= match.start()]
            entities_after = [e for e in entities if e.start_char >= marker_pos]
            
            if entities_before and entities_after:
                # get the last entity before the marker
                last_before = entities_before[-1]
                
                # Find matching entity type after marker
                for after_ent in entities_after:
                    # Match by label type
                    if after_ent.label_ == last_before.label_:
                        # Skip if the "after" entity is actually the correction marker
                        if after_ent.text.lower() in self.correction_markers:
                            continue
                        
                        # Record the replacement
                        before_text = last_before.text
                        after_text = after_ent.text
                        
                        replacements[last_before.start_char] = {
                            'before': before_text,
                            'after': after_text,
                            'end_char': last_before.end_char,
                            'marker_start': match.start(),
                            'marker_end': after_ent.end_char
                        }
                        
                        corrections.append((before_text, after_text))
                        break
        
        # apply replacements from right to left to maintain positions
        cleaned_text = text
        for pos in sorted(replacements.keys(), reverse=True):
            repl = replacements[pos]
            # replace from the old entity through the correction marker and old corrected entity
            cleaned_text = (
                cleaned_text[:pos] + 
                repl['after'] + 
                cleaned_text[repl['marker_end']:]
            )
        
        return cleaned_text, corrections
    
    def clean_disfluencies(self, text):
        removed = []

        for dis in self.disfl:
            pattern = r',?\s*\b' + re.escape(dis) + r'\b[,.]?\s*'
            if re.search(pattern, text, re.IGNORECASE):
                removed.append(dis)
                text = re.sub(pattern, ' ', text, flags=re.IGNORECASE)

        return text, removed
    
    def clean_whitespace(self, text): # self explanatory
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\s+([,.?!])', r'\1', text)
        text = re.sub(r'[,]+', ',', text)
        text = re.sub(r'\.{2,}', '.', text)
        
        return text.strip()

    def clean(self, text):
        # tracking what was cleaned, not as important since disfluencies/self correction patterns
        # are hard coded here, but if using NLP/LLMs instead this becomes crucial
        metadata = {
            'original': text,
            'corrections': [],
            'disfluencies_removed': [],
            'noise_removed': False
        }

        # handle noise markers
        if re.search(self.noise_patterns, text):
            text = re.sub(self.noise_patterns, '', text)
            metadata['noise_removed'] = True

        # remove disfluencies first (before corrections to avoid interfering)
        text, metadata['disfluencies_removed'] = self.clean_disfluencies(text)

        # handle self-corrections
        text, metadata['corrections'] = self.clean_corrections(text)
        
        # just in case
        text = self.clean_whitespace(text)

        # tracking entities for state-based monitoring
        entities = {
            'medications': [],
            'symptoms': [],
            'body parts': [],
        }
        
        #TODO: fix this list, check nhs symptoms/medicines database, bit redundant with NER but clinical model didn't work
        text_lower = text.lower()

        for med in ['ibuprofen', 'glucophage', 'paracetamol', 'propranolol', 'propanol', 'pro-pran-o-lol']:
            if med in text_lower:
                entities['medications'].append(med)

        for symptom in ['pain', 'hurts', 'fluttery', 'ache']:
            if symptom in text_lower:
                entities['symptoms'].append(symptom)

        for body in ['head', 'shoulders', 'knees', 'toes', 'knee', 'heart']:
            if body in text_lower:
                entities['body parts'].append(body)

        return {
            'cleaned_text': text,
            'metadata': metadata,
            'entities': entities
        }