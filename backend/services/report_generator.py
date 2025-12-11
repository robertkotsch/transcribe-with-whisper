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
        for visual in visual_analysis:
            timestamp = visual.get("timestamp", 0)
            visual_by_time[timestamp] = visual
        
        # Build timeline entries
        timeline = []
        
        for segment in transcript_segments:
            start_time = segment.get("start", 0)
            
            # Find closest visual analysis (within scene)
            closest_visual = None
            min_diff = float('inf')
            for ts, visual in visual_by_time.items():
                diff = abs(ts - start_time)
                if diff < min_diff:
                    min_diff = diff
                    closest_visual = visual
            
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
            fontSize=14,
            textColor=colors.HexColor('#333333'),
            spaceAfter=12
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
        story.append(PageBreak())
        
        # Timeline sections
        story.append(Paragraph("Visual Timeline", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        timeline = data.get('timeline', [])
        for i, entry in enumerate(timeline):
            if i >= 50:  # Limit to first 50 entries
                story.append(Paragraph(f"... and {len(timeline) - 50} more entries", styles['Normal']))
                break
            
            timestamp = entry.get('timestamp', 0)
            transcript_text = entry.get('transcript', {}).get('text', '')
            visual = entry.get('visual', {})
            
            # Section heading
            story.append(Paragraph(f"Scene at {timestamp:.2f}s", heading_style))
            
            # Keyframe image (if exists)
            keyframe_path = visual.get('keyframe_path', '')
            if keyframe_path and os.path.exists(keyframe_path):
                try:
                    img = Image(keyframe_path, width=4*inch, height=3*inch, kind='proportional')
                    story.append(img)
                    story.append(Spacer(1, 0.1*inch))
                except Exception as e:
                    logger.warning(f"Could not embed image {keyframe_path}: {e}")
            
            # Transcript
            if transcript_text:
                story.append(Paragraph(f"<b>Transcript:</b> {transcript_text}", styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
            
            # Visual description
            description = visual.get('description', '')
            if description:
                story.append(Paragraph(f"<b>Visual Analysis:</b> {description[:200]}...", styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
            
            # Corrections
            corrections = entry.get('corrections', [])
            if corrections:
                story.append(Paragraph(f"<b>Corrections:</b> {len(corrections)} applied", styles['Normal']))
            
            story.append(Spacer(1, 0.3*inch))
        
        # Build PDF
        doc.build(story)
        logger.info(f"Generated PDF report: {output_path}")
        return str(output_path)


# Singleton instance
report_generator = ReportGenerator()
