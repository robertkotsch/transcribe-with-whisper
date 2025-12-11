"""
Transcript Enhancer Service

Post-processing correction engine that uses visual vocabulary from OCR/VLM
to improve Whisper transcription accuracy.

Uses:
- Edit distance (Levenshtein) for typo detection
- Phonetic similarity (Double Metaphone) for German compound words
- Temporal proximity (visual terms near in time to audio)
"""

import json
import logging
import copy
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class VisualTerm:
    """A term extracted from visual analysis with context."""
    term: str
    source: str  # e.g., "scene_15_ocr" or "scene_15_vlm"
    timestamp: float
    confidence: float
    frequency: int = 1  # How many times this term appears


@dataclass
class Correction:
    """A single correction made to the transcript."""
    segment_id: int
    timestamp: float
    original_text: str
    corrected_text: str
    original_term: str
    corrected_term: str
    confidence: float
    evidence: Dict[str, Any]


class TranscriptEnhancer:
    """
    Enhance Whisper transcripts using visual vocabulary.
    
    1. Build vocabulary from visual analyses (OCR + VLM)
    2. For each Whisper segment, find matching visual terms
    3. Replace low-confidence or phonetically similar terms
    4. Maintain audit trail of all corrections
    """
    
    def __init__(
        self,
        match_threshold: float = 0.75,
        temporal_window: float = 2.0,  # seconds
        min_term_length: int = 3
    ):
        """
        Args:
            match_threshold: Minimum confidence for making a correction.
            temporal_window: Look for visual terms within ±N seconds of audio.
            min_term_length: Ignore terms shorter than this.
        """
        self.match_threshold = match_threshold
        self.temporal_window = temporal_window
        self.min_term_length = min_term_length
    
    def build_visual_vocabulary(
        self, 
        visual_analyses: List[Dict]
    ) -> Dict[str, VisualTerm]:
        """
        Build a vocabulary index from all visual analyses.
        
        Args:
            visual_analyses: List of VisualAnalysis dicts from visual_analyzer.
            
        Returns:
            Dict mapping lowercase terms to VisualTerm objects.
        """
        vocabulary = {}
        
        for analysis in visual_analyses:
            timestamp = analysis.get("timestamp", 0.0)
            scene_idx = analysis.get("scene_index", 0)
            
            # Extract terms from OCR results
            for ocr in analysis.get("ocr_results", []):
                text = ocr.get("text", "").strip()
                confidence = ocr.get("confidence", 0.8)
                
                if len(text) >= self.min_term_length:
                    key = text.lower()
                    if key in vocabulary:
                        vocabulary[key].frequency += 1
                    else:
                        vocabulary[key] = VisualTerm(
                            term=text,
                            source=f"scene_{scene_idx}_ocr",
                            timestamp=timestamp,
                            confidence=confidence
                        )
            
            # Also use pre-extracted technical terms
            for term in analysis.get("extracted_terms", []):
                if len(term) >= self.min_term_length:
                    key = term.lower()
                    if key in vocabulary:
                        vocabulary[key].frequency += 1
                    else:
                        vocabulary[key] = VisualTerm(
                            term=term,
                            source=f"scene_{scene_idx}_extracted",
                            timestamp=timestamp,
                            confidence=0.9  # Pre-filtered terms have high confidence
                        )
        
        logger.info(f"Built visual vocabulary with {len(vocabulary)} terms")
        return vocabulary
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein edit distance between two strings."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def _phonetic_similarity(self, s1: str, s2: str) -> float:
        """
        Calculate phonetic similarity using Double Metaphone.
        Falls back to basic similarity if jellyfish not available.
        """
        try:
            import jellyfish
            # Double Metaphone returns (primary, alternate) codes
            m1 = jellyfish.metaphone(s1)
            m2 = jellyfish.metaphone(s2)
            
            if m1 == m2:
                return 1.0
            
            # Calculate similarity of metaphone codes
            max_len = max(len(m1), len(m2))
            if max_len == 0:
                return 0.0
            
            dist = self._levenshtein_distance(m1, m2)
            return 1.0 - (dist / max_len)
            
        except ImportError:
            # Fallback: simple character overlap
            set1 = set(s1.lower())
            set2 = set(s2.lower())
            if not set1 or not set2:
                return 0.0
            return len(set1 & set2) / len(set1 | set2)
    
    def _calculate_match_score(
        self,
        whisper_term: str,
        visual_term: VisualTerm,
        timestamp_diff: float
    ) -> float:
        """
        Multi-factor scoring for correction confidence.
        
        Factors:
        1. Edit distance (Levenshtein)
        2. Phonetic similarity
        3. Temporal proximity
        4. Visual confidence (OCR quality)
        5. Frequency (repeated visual terms = more reliable)
        """
        w_lower = whisper_term.lower()
        v_lower = visual_term.term.lower()
        
        # Factor 1: Edit distance
        max_len = max(len(w_lower), len(v_lower))
        if max_len == 0:
            return 0.0
        edit_dist = self._levenshtein_distance(w_lower, v_lower)
        edit_score = 1.0 - (edit_dist / max_len)
        
        # Factor 2: Phonetic similarity
        phonetic_score = self._phonetic_similarity(w_lower, v_lower)
        
        # Factor 3: Temporal proximity
        temporal_score = 1.0 / (1.0 + abs(timestamp_diff))
        
        # Factor 4: Visual confidence
        visual_confidence = visual_term.confidence
        
        # Factor 5: Frequency boost
        frequency_boost = min(1.0, visual_term.frequency / 3.0)
        
        # Weighted combination
        final_score = (
            0.30 * edit_score +
            0.25 * phonetic_score +
            0.15 * temporal_score +
            0.15 * visual_confidence +
            0.15 * frequency_boost
        )
        
        return final_score
    
    def _extract_candidates(self, text: str) -> List[str]:
        """
        Extract candidate terms from Whisper text that might need correction.
        
        Focuses on:
        - Capitalized words (potential proper nouns/technical terms)
        - Words with numbers
        - Longer words (more likely to be technical)
        """
        import re
        
        words = text.split()
        candidates = []
        
        for word in words:
            # Clean punctuation
            clean = re.sub(r'^[^\w]+|[^\w]+$', '', word)
            if len(clean) < self.min_term_length:
                continue
            
            # Include if: capitalized, contains number, or long word
            if (clean[0].isupper() or 
                any(c.isdigit() for c in clean) or 
                len(clean) >= 8):
                candidates.append(clean)
        
        return candidates
    
    def _find_temporal_matches(
        self, 
        vocabulary: Dict[str, VisualTerm],
        segment_time: float
    ) -> List[VisualTerm]:
        """Find visual terms within temporal window of segment."""
        matches = []
        for term in vocabulary.values():
            if abs(term.timestamp - segment_time) <= self.temporal_window:
                matches.append(term)
        return matches
    
    def enhance_transcript(
        self,
        whisper_result: Dict,
        visual_vocabulary: Dict[str, VisualTerm],
        threshold: Optional[float] = None
    ) -> Tuple[Dict, List[Correction]]:
        """
        Enhance Whisper transcript using visual vocabulary.
        
        Args:
            whisper_result: Whisper JSON output with segments.
            visual_vocabulary: Built from build_visual_vocabulary().
            threshold: Override default match threshold.
            
        Returns:
            (enhanced_result, corrections_list)
        """
        threshold = threshold or self.match_threshold
        enhanced = copy.deepcopy(whisper_result)
        corrections = []
        
        segments = enhanced.get("segments", [])
        
        for segment in segments:
            segment_id = segment.get("id", 0)
            segment_time = segment.get("start", 0.0)
            original_text = segment.get("text", "")
            
            # Find visual terms in temporal window
            temporal_matches = self._find_temporal_matches(
                visual_vocabulary, 
                segment_time
            )
            
            if not temporal_matches:
                continue
            
            # Extract candidate terms for correction
            candidates = self._extract_candidates(original_text)
            
            corrected_text = original_text
            
            for candidate in candidates:
                best_match = None
                best_score = 0.0
                
                for visual_term in temporal_matches:
                    timestamp_diff = abs(visual_term.timestamp - segment_time)
                    score = self._calculate_match_score(
                        candidate,
                        visual_term,
                        timestamp_diff
                    )
                    
                    if score > best_score and score >= threshold:
                        # Don't correct if it's already the same
                        if candidate.lower() != visual_term.term.lower():
                            best_score = score
                            best_match = visual_term
                
                # Apply correction
                if best_match:
                    new_text = corrected_text.replace(candidate, best_match.term, 1)
                    
                    if new_text != corrected_text:
                        correction = Correction(
                            segment_id=segment_id,
                            timestamp=segment_time,
                            original_text=original_text,
                            corrected_text=new_text,
                            original_term=candidate,
                            corrected_term=best_match.term,
                            confidence=best_score,
                            evidence={
                                "visual_source": best_match.source,
                                "visual_timestamp": best_match.timestamp,
                                "edit_distance": self._levenshtein_distance(
                                    candidate.lower(), 
                                    best_match.term.lower()
                                ),
                                "frequency": best_match.frequency
                            }
                        )
                        corrections.append(correction)
                        corrected_text = new_text
            
            # Update segment with corrected text
            if corrected_text != original_text:
                segment["text"] = corrected_text
                segment["text_original"] = original_text
        
        # Update full text
        if corrections:
            enhanced["text"] = " ".join(s.get("text", "") for s in segments)
            enhanced["text_original"] = whisper_result.get("text", "")
        
        logger.info(f"Applied {len(corrections)} corrections to transcript")
        return enhanced, corrections
    
    def save_correction_log(
        self, 
        corrections: List[Correction],
        output_path: str,
        video_id: str = "unknown"
    ):
        """Save corrections to JSON file for audit trail."""
        log_data = {
            "video_id": video_id,
            "total_corrections": len(corrections),
            "corrections": [asdict(c) for c in corrections]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(corrections)} corrections to {output_path}")


# Singleton instance
transcript_enhancer = TranscriptEnhancer()
