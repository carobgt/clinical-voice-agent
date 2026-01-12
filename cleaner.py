import re
import spacy

class Cleaner:
    
    def __init__(self):
        # NER model loading, using mostly for self-correction logic, tried a clinical one w/ less success
        self.nlp = spacy.load("en_core_web_sm")
        
        # needed to add entity ruler to catch OOD terms
        ruler = self.nlp.add_pipe("entity_ruler", before="ner")
        patterns = [
            # hard coding here bc not much time, in the future would use NHS medicines database: https://www.nhs.uk/medicines/
            {"label": "MEDICATION", "pattern": [{"LOWER": "ibuprofen"}]},
            {"label": "MEDICATION", "pattern": [{"LOWER": "glucophage"}]},
            {"label": "MEDICATION", "pattern": [{"LOWER": "propranolol"}]},
            {"label": "MEDICATION", "pattern": [{"LOWER": "paracetamol"}]},
            
            # body parts, illustrative as well
            {"label": "BODY_PART", "pattern": [{"LOWER": "knee"}]},
            {"label": "BODY_PART", "pattern": [{"LOWER": "chest"}]},
            {"label": "BODY_PART", "pattern": [{"LOWER": "neck"}]},
            {"label": "BODY_PART", "pattern": [{"LOWER": "head"}]},
            {"label": "BODY_PART", "pattern": [{"LOWER": "heart"}]},
            
            # some symptoms
            {"label": "SYMPTOM", "pattern": [{"LOWER": "pain"}]},
            {"label": "SYMPTOM", "pattern": [{"LOWER": "hurts"}]},
            {"label": "SYMPTOM", "pattern": [{"LOWER": "fluttery"}]},
            {"label": "SYMPTOM", "pattern": [{"LOWER": "aches"}]},
            {"label": "SYMPTOM", "pattern": [{"LOWER": "shakes"}]},
        ]
        ruler.add_patterns(patterns)
    
    # list of disfluencies, should cover most
    disfl = ['um', 'uh', 'er', 'ah', 'like', 'you know', 
    'i mean', 'sort of', 'kind of', 'kinda', 'basically', 'actually']
    
    correction_markers = ['no', 'wait', 'sorry', 'actually', 'i mean', 'or', 'rather']

    noise_patterns = r'\[(?:noise|inaudible|unclear|cough|pause)\]'
    
    #TODO: could add confidence levels for human reviewers s.t. text isnt overprocessed
    # i.e. because we remove signs of uncertainty/disfluency which might be useful to track

    # updated, using NER instead of regex (too brittle) for self-correction logic
    # also extracting entities here to avoid having to redo this later
    def clean_corrections(self, text):
        corrections = []
        
        # removing ellipses, dashes
        text = re.sub(r'\.{2,}', ' ', text)
        text = text.replace('-', '')
        
        doc = self.nlp(text)
        
        # find all entities first
        entities = list(doc.ents)
        
        # track which entities have been replaced
        replacements = {}
        
        # look for correction patterns in the text
        correction_pattern = r'\b(no|wait|sorry|actually|i mean|or|rather)\b[,\s]*'
        
        for match in re.finditer(correction_pattern, text, re.IGNORECASE):
            marker_pos = match.end()
            marker_start = match.start()
            
            # find entities after the marker
            entities_after = [e for e in entities if e.start_char >= marker_pos]
            
            if not entities_after:
                continue
                
            after_entity = entities_after[0]
            
            # skip if the "after" entity is actually a correction marker word
            if after_entity.text.lower() in self.correction_markers:
                continue
            
            # determine what to replace
            before_item = None
            
            # try to use the last entity before marker that has the same label as after_entity
            entities_before = [e for e in entities if e.end_char <= marker_start and e.label_ == after_entity.label_]

            if entities_before:
                # use the last matching entity
                last_entity = entities_before[-1]
                before_item = {
                    'text': last_entity.text,
                    'start': last_entity.start_char,
                    'end': last_entity.end_char,
                    'type': 'entity'
                }
            else:
                # fall back to token immediately before marker (except for punctuation etc)
                tokens_before = [token for token in doc if token.idx < marker_start]
                for token in reversed(tokens_before):
                    if not token.is_punct and len(token.text) > 1:
                        before_item = {
                            'text': token.text,
                            'start': token.idx,
                            'end': token.idx + len(token.text),
                            'type': 'token'
                        }
                        break  # stop at first valid token
            
            if before_item:
                replacements[before_item['start']] = {
                    'before': before_item['text'],
                    'after': after_entity.text,
                    'before_end': before_item['end'],
                    'marker_start': marker_start,
                    'marker_end': after_entity.end_char,
                    'before_type': before_item['type']
                }
            
                corrections.append((before_item['text'], after_entity.text))
        
        # apply replacements from right to left to maintain positions
        cleaned_text = text
        for pos in sorted(replacements.keys(), reverse=True):
            repl = replacements[pos]
            cleaned_text = (
                cleaned_text[:pos] + 
                repl['after'] + 
                cleaned_text[repl['marker_end']:]
            )
        
        # entity tracking for state based monitoring, relies mostly on entity ruling above
        doc_corrected = self.nlp(cleaned_text)
        
        entities = {
            'medications': [],
            'symptoms': [],
            'body_parts': [],
        }
        
        for ent in doc_corrected.ents:
            if ent.label_ == "MEDICATION":
                entities['medications'].append(ent.text)
            elif ent.label_ in ["SYMPTOM"]:
                entities['symptoms'].append(ent.text)
            elif ent.label_ == "BODY_PART":
                entities['body_parts'].append(ent.text)
        
        return cleaned_text, corrections, entities


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

        # handle self-corrections and extract entities for state-based monitoring later
        text, metadata['corrections'], entities = self.clean_corrections(text)
        
        # just in case
        text = self.clean_whitespace(text)

        return {
            'cleaned_text': text,
            'metadata': metadata,
            'entities': entities
        }