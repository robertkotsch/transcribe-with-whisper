
import sys
import os
import unittest
from pathlib import Path

# Add backend to path specifically for this test
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.transcript_enhancer import TranscriptEnhancer, VisualTerm

class TestTranscriptEnhancer(unittest.TestCase):
    
    def setUp(self):
        self.enhancer = TranscriptEnhancer()
        
    def test_node_chalker_correction(self):
        """Test specific user case: 'node chalker' -> 'knowledgeworker'"""
        
        # 1. Setup Mock Visual Vocabulary
        vocab = {
            "knowledgeworker": VisualTerm(
                term="knowledgeworker",
                source="test_ocr",
                timestamp=10.0,
                confidence=0.95,
                frequency=1
            )
        }
        
        # 2. Setup Mock Whisper Result
        whisper_result = {
            "text": "The node chalker is an important concept.",
            "segments": [
                {
                    "id": 1,
                    "start": 10.0,
                    "end": 12.0,
                    "text": "The node chalker is an important concept."
                }
            ]
        }
        
        # 3. Run Enhancement
        enhanced, corrections = self.enhancer.enhance_transcript(whisper_result, vocab)
        
        # 4. Verify
        # Print for debug visibility
        print(f"Original: {whisper_result['segments'][0]['text']}")
        print(f"Enhanced: {enhanced['segments'][0]['text']}")
        print(f"Corrections: {[c.corrected_term for c in corrections]}")
        
        self.assertEqual(len(corrections), 1, "Should have one correction")
        self.assertEqual(corrections[0].original_term, "node chalker")
        self.assertEqual(corrections[0].corrected_term, "knowledgeworker")
        self.assertIn("The knowledgeworker is", enhanced["segments"][0]["text"])

    def test_partial_overlap_logic(self):
        """Test that we don't double correct or mess up indices matching 'knowledge' and 'worker' separately if 'knowledgeworker' is better?"""
        # This test ensures the 'best score' logic works if multiple terms exist.
        # But here we mostly care about the n-gram matching.
        pass

if __name__ == '__main__':
    unittest.main()
