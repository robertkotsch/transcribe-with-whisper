"""
Visual Analyzer Service

OCR extraction via EasyOCR + VLM descriptions via Ollama.
Builds visual vocabulary for transcript enhancement.
"""

import os
import json
import base64
import logging
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import easyocr

logger = logging.getLogger(__name__)



# Ollama endpoint for VLM
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


@dataclass
class OCRResult:
    """Single OCR detection result."""
    text: str
    confidence: float
    bbox: List[List[int]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]


@dataclass
class VisualAnalysis:
    """Complete analysis of a keyframe."""
    image_path: str
    timestamp: float
    scene_index: int
    ocr_results: List[Dict]
    vlm_description: str
    extracted_terms: List[str]  # Technical terms, acronyms, etc.


class VisualAnalyzer:
    """
    Analyze keyframes using OCR (EasyOCR) and VLM (Ollama).
    
    Requires:
    - EasyOCR (installs models on first run)
    - Ollama with a vision model (llava, bakllava, etc.)
    """
    
    def __init__(
        self, 
        ollama_url: str = OLLAMA_URL,
        vlm_model: str = "llava"
    ):
        self.ollama_url = ollama_url
        self.vlm_model = vlm_model
        try:
            logger.info("Initializing EasyOCR reader (en, de)...")
            self.reader = easyocr.Reader(['en', 'de'])
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            self.reader = None
    
    def check_ocr_available(self) -> bool:
        """Check if OCR is available."""
        return self.reader is not None
    
    def check_vlm_available(self) -> bool:
        """Check if Ollama VLM model is available."""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return any(m["name"].startswith(self.vlm_model) for m in models)
            return False
        except requests.RequestException:
            return False
    
    def run_ocr(self, image_path: str) -> List[OCRResult]:
        """
        Run OCR on an image via EasyOCR.
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            List of detected text elements.
        """
        if not self.reader:
            return []
            
        try:
            results = self.reader.readtext(image_path)
            ocr_results = []
            for (bbox, text, prob) in results:
                ocr_results.append(OCRResult(
                    text=text,
                    confidence=float(prob),
                    bbox=[[int(p[0]), int(p[1])] for p in bbox]
                ))
            return ocr_results
        except Exception as e:
            logger.error(f"OCR failed for {image_path}: {e}")
            return []
    
    def run_vlm(self, image_path: str, scene_type: str = "general") -> str:
        """
        Run VLM description on an image via Ollama.
        
        Args:
            image_path: Path to the image file.
            scene_type: Hint for prompt selection (diagram, slide, screen, general).
            
        Returns:
            Text description of the image.
        """
        if not os.path.exists(image_path):
            logger.error(f"Image not found: {image_path}")
            return ""
        
        # Build prompt based on scene type - REVISED to reduce hallucinations
        prompts = {
            "diagram": """List EXACTLY what you see in this training video frame:
1. ALL visible text (word-for-word, preserve exact spelling/formatting)
2. Visual elements (diagrams, charts, icons - describe what's actually shown, not what you think it means)
3. Numbers and measurements (exact values only)

DO NOT:
- Guess or interpret meanings
- Mention things you're not certain about
- Add context not visible in the image
Output in the same language as visible text.""",
            
            "slide": """Extract EXACTLY what is visible in this slide:
1. Title (exact text)
2. ALL bullet points or text boxes (word-for-word)
3. Visible labels, numbers, footer text (exact)

DO NOT add interpretation or guess meanings. Only describe what you can clearly see.
Output in the same language as visible text.""",
            
            "screen": """Describe this software screenshot:
1. Visible text: window titles, buttons, labels (EXACT wording)
2. UI elements: what type (dialog, menu, etc.)
3. Visible data or values (exact)

DO NOT speculate about function or meaning. Only describe visible elements.
Output in the same language as visible text.""",
            
            "general": """List what is ACTUALLY VISIBLE in this frame:
1. Text overlays (EXACT words, preserve spelling)
2. Diagrams or charts (describe shapes/structure only)
3. Numbers, dates, times (exact values)
4. UI elements (buttons, icons - describe appearance only)

DO NOT:
- Interpret or speculate
- Mention version numbers unless clearly visible
- Describe processes or meanings
- Add context not in the image

Be factual. If uncertain, skip it. Output in the same language as visible text."""
        }
        
        prompt = prompts.get(scene_type, prompts["general"])
        
        try:
            # Read and encode image as base64
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Ollama vision API format
            payload = {
                "model": self.vlm_model,
                "prompt": prompt,
                "images": [image_data],
                "stream": False,
                "options": {
                    "temperature": 0.1,  # REDUCED from 0.3 - more factual, less creative
                    "num_predict": 400,  # Reduced from 512 - encourage conciseness
                    "top_p": 0.9,  # Add nucleus sampling for better factuality
                }
            }
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                logger.error(f"VLM request failed: {response.status_code}")
                return ""
            
            result = response.json()
            description = result.get("response", "").strip()
            
            logger.info(f"VLM generated {len(description)} char description for {Path(image_path).name}")
            return description
            
        except requests.RequestException as e:
            logger.error(f"VLM request error: {e}")
            return ""
        except Exception as e:
            logger.error(f"VLM error: {e}")
            return ""
    
    def extract_technical_terms(self, ocr_results: List[OCRResult]) -> List[str]:
        """
        Extract technical terms from OCR results.
        
        Filters for:
        - Acronyms (uppercase 2-6 chars)
        - Numbers with units (20 km/h, 45 dB)
        - Regulation references (ISO 45001, DIN 4844-2)
        - Compound words (German technical terms)
        """
        import re
        
        terms = []
        
        for ocr in ocr_results:
            text = ocr.text.strip()
            if not text or ocr.confidence < 0.7:
                continue
            
            # Acronyms: 2-6 uppercase letters
            if re.match(r'^[A-Z]{2,6}$', text):
                terms.append(text)
            
            # Regulation references: DIN, ISO, EN, etc.
            elif re.match(r'^(DIN|ISO|EN|IEC)\s*[-\d]+', text, re.IGNORECASE):
                terms.append(text)
            
            # Numbers with units
            elif re.match(r'^\d+[\.,]?\d*\s*(km/h|m/s|dB|Hz|kW|V|A|°C|mm|cm|m|kg|bar|psi)', text):
                terms.append(text)
            
            # German compound words (capitalized, 10+ chars)
            elif re.match(r'^[A-ZÄÖÜ][a-zäöüß]+[A-ZÄÖÜ][a-zäöüß]+', text) and len(text) >= 10:
                terms.append(text)
            
            # Any text with high confidence (0.9+) that looks like a label
            elif ocr.confidence >= 0.9 and len(text) >= 3:
                terms.append(text)
        
        # Deduplicate while preserving order
        seen = set()
        unique_terms = []
        for term in terms:
            if term.lower() not in seen:
                seen.add(term.lower())
                unique_terms.append(term)
        
        return unique_terms
    
    def analyze_keyframe(
        self, 
        image_path: str, 
        timestamp: float,
        scene_index: int = 0,
        run_vlm: bool = True,
        scene_type: str = "general"
    ) -> VisualAnalysis:
        """
        Complete analysis of a keyframe: OCR + VLM + term extraction.
        
        Args:
            image_path: Path to keyframe image.
            timestamp: Timestamp in video (seconds).
            scene_index: Scene number this keyframe belongs to.
            run_vlm: Whether to run VLM description (slower).
            scene_type: Hint for VLM prompt.
            
        Returns:
            VisualAnalysis object with all extracted data.
        """
        logger.info(f"Analyzing keyframe: {Path(image_path).name} @ {timestamp:.2f}s")
        
        # Run OCR
        ocr_results = self.run_ocr(image_path)
        
        # Extract technical terms
        extracted_terms = self.extract_technical_terms(ocr_results)
        
        # Run VLM description (optional, slower)
        vlm_description = ""
        if run_vlm:
            vlm_description = self.run_vlm(image_path, scene_type)
        
        return VisualAnalysis(
            image_path=image_path,
            timestamp=timestamp,
            scene_index=scene_index,
            ocr_results=[asdict(r) for r in ocr_results],
            vlm_description=vlm_description,
            extracted_terms=extracted_terms
        )
    
    def analyze_all_keyframes(
        self,
        keyframe_paths: List[str],
        timestamps: List[float],
        run_vlm: bool = True,
        progress_callback: Optional[callable] = None
    ) -> List[Dict]:
        """
        Analyze multiple keyframes in sequence.
        
        Args:
            keyframe_paths: List of keyframe image paths.
            timestamps: Corresponding timestamps for each keyframe.
            run_vlm: Whether to run VLM on each frame.
            progress_callback: Optional callback(current, total) for progress.
            
        Returns:
            List of VisualAnalysis dicts.
        """
        results = []
        total = len(keyframe_paths)
        
        for i, (path, ts) in enumerate(zip(keyframe_paths, timestamps)):
            analysis = self.analyze_keyframe(
                image_path=path,
                timestamp=ts,
                scene_index=i,
                run_vlm=run_vlm
            )
            results.append(asdict(analysis))
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return results


# Singleton instance
visual_analyzer = VisualAnalyzer()
