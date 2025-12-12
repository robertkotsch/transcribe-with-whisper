"""
Report Generator Service

Generates merged JSON and PDF reports combining audio transcripts with visual analysis.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate merged outputs and PDF reports from pipeline results."""
    
    def generate_merged_json(
        self,
        output_dir: str,
        transcript_segments: List[Dict],
        visual_analysis: List[Dict],
        corrections: List[Dict],
        metadata: Dict,
        result: Dict
    ) -> str:
        """
        Generate merged JSON combining audio, visual, and metadata.
        
        Args:
            output_dir: Directory to save merged.json
            transcript_segments: Whisper transcript segments
            visual_analysis: VLM analysis results
            corrections: Transcript corrections applied
            metadata: Video metadata
            result: Full pipeline result
            
        Returns:
            Path to merged.json file
        """
        output_path = Path(output_dir) / "merged.json"
        
        # Build scene/timestamp lookup for visual data
        visual_by_time = {}
        sorted_visual = sorted(visual_analysis, key=lambda x: x.get("timestamp", 0))
        for visual in sorted_visual:
            timestamp = visual.get("timestamp", 0)
            visual_by_time[timestamp] = visual
        
        # Prepare scenes structure for report
        scenes = []
        for v in sorted_visual:
            scenes.append({
                "scene_index": v.get("scene_index"),
                "timestamp": v.get("timestamp"),
                "image_path": v.get("image_path"),
                "description": v.get("vlm_description", ""),
                "extracted_terms": v.get("extracted_terms", []),
                "transcript_text": ""
            })

        # Build timeline entries AND populate scene transcripts
        timeline = []
        
        for segment in transcript_segments:
            start_time = segment.get("start", 0)
            text = segment.get("text", "").strip()
            
            # Find closest visual analysis (within scene)
            closest_visual = None
            min_diff = float('inf')
            
            # Also find index for "scenes" list
            closest_scene_idx = -1
            
            for idx, (ts, visual) in enumerate(visual_by_time.items()):
                diff = abs(ts - start_time)
                if diff < min_diff:
                    min_diff = diff
                    closest_visual = visual
            
            # Find closest scene in our scenes list
            # Since both are based on same data, logical mapping should be robust
            min_scene_diff = float('inf')
            best_scene_match = None
            for scene in scenes:
                diff = abs(scene['timestamp'] - start_time)
                if diff < min_scene_diff:
                    min_scene_diff = diff
                    best_scene_match = scene
            
            # Append text to scene
            if best_scene_match:
                if best_scene_match["transcript_text"]:
                    best_scene_match["transcript_text"] += " " + text
                else:
                    best_scene_match["transcript_text"] = text

            # Find corrections for this segment
            segment_corrections = [
                c for c in corrections 
                if abs(c.get("timestamp", 0) - start_time) < 5.0  # Within 5s
            ]
            
            entry = {
                "timestamp": start_time,
                "duration": segment.get("end", start_time) - start_time,
                "transcript": {
                    "text": segment.get("text", ""),
                    "confidence": segment.get("confidence", 0.0),
                    "speaker": segment.get("speaker", "Unknown")
                }
            }
            
            # Add visual context if available
            if closest_visual:
                entry["visual"] = {
                    "scene_index": closest_visual.get("scene_index", 0),
                    "keyframe_path": closest_visual.get("image_path", ""),
                    "description": closest_visual.get("vlm_description", ""),
                    "extracted_terms": closest_visual.get("extracted_terms", []),
                    "timestamp_diff": min_diff
                }
            
            # Add corrections if any
            if segment_corrections:
                entry["corrections"] = segment_corrections
            
            timeline.append(entry)
        
        # Build merged structure
        merged = {
            "metadata": {
                "video_file": metadata.get("file_path", ""),
                "duration": metadata.get("duration", 0),
                "language": result.get("language", "unknown"),
                "processing_date": datetime.now().isoformat(),
                "vlm_model": metadata.get("vlm_model", ""),
                "vlm_enabled": metadata.get("vlm_enabled", False),
                "scenes_detected": len(visual_analysis),
                "corrections_applied": len(corrections)
            },
            "timeline": timeline,
            "scenes": scenes,  # New field for report.pdf
            "summary": {
                "total_segments": len(transcript_segments),
                "total_scenes": len(visual_analysis),
                "visual_terms_found": sum(len(v.get("extracted_terms", [])) for v in visual_analysis),
                "corrections_made": len(corrections)
            },
            "artifacts": {
                "transcript": result.get("transcript_path", ""),
                "visual": result.get("visual_path", ""),
                "corrections": result.get("corrections_path", ""),
                "audio": result.get("audio_path", ""),
                "keyframes_dir": metadata.get("keyframes_dir", "")
            }
        }
        
        # Save merged JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Generated merged JSON: {output_path}")
        return str(output_path)
    
    def generate_pdf_report(
        self,
        output_dir: str,
        merged_json_path: str,
        video_name: str
    ) -> str:
        """
        Generate PDF report with embedded keyframes.
        
        Args:
            output_dir: Directory to save report.pdf
            merged_json_path: Path to merged.json
            video_name: Name of video for title
            
        Returns:
            Path to report.pdf file
        """
        try:
            from reportlab.lib.pagesizes import A4, letter
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
            from reportlab.lib import colors
            from PIL import Image as PILImage
        except ImportError:
            logger.error("reportlab or Pillow not installed. Run: pip install reportlab Pillow")
            return ""
        
        output_path = Path(output_dir) / "report.pdf"
        
        # Load merged data
        with open(merged_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Create PDF
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            alignment=TA_CENTER,
            spaceAfter=30
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#333333'),
            spaceAfter=12,
            spaceBefore=12
        )
        
        # Title page
        story.append(Paragraph(f"Video Analysis Report", title_style))
        story.append(Paragraph(f"{video_name}", styles['Heading2']))
        story.append(Spacer(1, 0.3*inch))
        
        # Metadata table
        metadata = data['metadata']
        meta_data = [
            ['Processing Date:', metadata.get('processing_date', 'N/A')],
            ['Language:', metadata.get('language', 'N/A')],
            ['Duration:', f"{metadata.get('duration', 0):.2f}s"],
            ['VLM Model:', metadata.get('vlm_model', 'N/A')],
            ['Scenes Detected:', str(metadata.get('scenes_detected', 0))],
            ['Corrections Applied:', str(metadata.get('corrections_applied', 0))]
        ]
        
        meta_table = Table(meta_data, colWidths=[2*inch, 4*inch])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        
        story.append(meta_table)
        
        # Use scenes structure if available, otherwise fall back to timeline (but scenes is preferred)
        scenes = data.get('scenes', [])
        
        if not scenes:
            story.append(Spacer(1, 0.5*inch))
            story.append(Paragraph("No scenes data found. Please regenerate merged JSON.", styles['Normal']))
        
        for i, scene in enumerate(scenes):
            # One scene per page
            story.append(PageBreak())
            
            timestamp = scene.get('timestamp', 0)
            transcript_text = scene.get('transcript_text', '')
            
            # Scene Header
            story.append(Paragraph(f"Scene {scene.get('scene_index', i+1)} - {timestamp:.2f}s", heading_style))
            
            # Keyframe image
            keyframe_path = scene.get('image_path', '')
            if keyframe_path and os.path.exists(keyframe_path):
                try:
                    # Maximize width to fit page margins (approx 7 inches available width)
                    # Let's use 6 inches wide to look good
                    img = Image(keyframe_path, width=6*inch, height=4.5*inch, kind='proportional')
                    story.append(img)
                    story.append(Spacer(1, 0.2*inch))
                except Exception as e:
                    logger.warning(f"Could not embed image {keyframe_path}: {e}")
            
            # Visual Analysis (Full Text)
            description = scene.get('description', '')
            if description:
                story.append(Paragraph("<b>Visual Analysis:</b>", styles['Heading3']))
                story.append(Paragraph(description, styles['Normal'])) # No truncation
                story.append(Spacer(1, 0.15*inch))
            
            # Transcript
            if transcript_text:
                story.append(Paragraph("<b>Transcript:</b>", styles['Heading3']))
                story.append(Paragraph(transcript_text, styles['Normal']))
                story.append(Spacer(1, 0.15*inch))
            
            # Extracted Terms (Optional)
            terms = scene.get('extracted_terms', [])
            if terms:
                story.append(Paragraph(f"<b>Extracted Terms:</b> {', '.join(terms)}", styles['Normal']))

        # Build PDF
        doc.build(story)
        logger.info(f"Generated PDF report: {output_path}")
        return str(output_path)


# Singleton instance
report_generator = ReportGenerator()
