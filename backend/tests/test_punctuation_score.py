
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from services.transcript_enhancer import TranscriptEnhancer, VisualTerm

enhancer = TranscriptEnhancer(match_threshold=0.55)
term = VisualTerm("Knowledgeworker", "ocr", 0.0, 0.99)

# Case 1: Clean
s1 = "Knowledge-Burger"
score1 = enhancer._calculate_match_score(s1, term, 0.0)
print(f"'{s1}' Score: {score1}")

# Case 2: With Comma
s2 = "Knowledge-Burger,"
score2 = enhancer._calculate_match_score(s2, term, 0.0)
print(f"'{s2}' Score: {score2}")

# Case 3: With Trailing Space inside n-gram? 
# (Split stripped spaces, but join adds them back. split() removes trailing comma if attached? No.)

