
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from services.transcript_enhancer import TranscriptEnhancer, VisualTerm

enhancer = TranscriptEnhancer(match_threshold=0.55)
term = VisualTerm("Knowledgeworker", "ocr", 0.0, 0.99)

# Case 1: Internal Hyphen (Current state)
s1 = "Knowledge-Burger"
# My code does: s1.strip('...') -> "Knowledge-Burger"
score1 = enhancer._calculate_match_score(s1, term, 0.0)
print(f"'{s1}' Score (with hyphen): {score1}")

# Case 2: Removed Hyphen
s2 = "KnowledgeBurger"
score2 = enhancer._calculate_match_score(s2, term, 0.0)
print(f"'{s2}' Score (no hyphen): {score2}")

# Case 3: Replaced hyphen with space (2 words)
s3 = "Knowledge Burger"
score3 = enhancer._calculate_match_score(s3, term, 0.0)
print(f"'{s3}' Score (space): {score3}")
