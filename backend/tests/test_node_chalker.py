
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from services.transcript_enhancer import TranscriptEnhancer, VisualTerm

enhancer = TranscriptEnhancer(match_threshold=0.55)
term = VisualTerm("Knowledgeworker", "ocr", 0.0, 0.99)

# Test cases
candidates = [
    "Node chalker",
    "node-chalker",
    "no chalker",
    "know ledge worker"
]

print(f"Target Visual Term: '{term.term}'")
print("-" * 50)

for c in candidates:
    # 1. Similarity as is
    score = enhancer._calculate_match_score(c, term, 0.0)
    print(f"'{c}' Score: {score:.4f}")
    
    # 2. Check individual components
    edit_dist = enhancer._levenshtein_distance(c.lower(), term.term.lower())
    max_len = max(len(c), len(term.term))
    edit_sim = 1.0 - (edit_dist / max_len)
    
    phon_sim = enhancer._phonetic_similarity(c, term.term)
    
    print(f"  -> Edit Sim: {edit_sim:.4f}, Phonetic Sim: {phon_sim:.4f}")
