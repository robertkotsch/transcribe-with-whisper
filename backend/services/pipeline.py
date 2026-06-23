import os
import subprocess
import json
import logging
from datetime import datetime
from pathlib import Path
import ollama
import httpx
from typing import Dict, Any, List, Optional

# Try imports ensuring we handle missing dependencies gracefully
try:
    import whisper
    import ollama
except ImportError:
    print("Warning: 'whisper' or 'ollama' module not found. Please pip install.")

# Import diarization service
try:
    try:
        from .diarization import diarizer
    except ImportError:
        # Fallback for when run directly (not as package)
        from diarization import diarizer
    DIARIZATION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Diarization not available: {e}")
    DIARIZATION_AVAILABLE = False

# Import VLM services
try:
    try:
        from .scene_detector import scene_detector
        from .visual_analyzer import visual_analyzer
        from .transcript_enhancer import transcript_enhancer
        from .report_generator import report_generator
    except ImportError:
        from scene_detector import scene_detector
        from visual_analyzer import visual_analyzer
        from transcript_enhancer import transcript_enhancer
        from report_generator import report_generator
    VLM_AVAILABLE = True
except ImportError as e:
    print(f"Warning: VLM services not available: {e}")
    VLM_AVAILABLE = False

class MediaPipeline:
    
    MODEL_MAP = {
        "German": {
            "Correction": "qwen2",
            "Refinement": "mistral",
            "Subtitles": "mistral",
            "Audit": "mistral",
            "Questions": "mistral",
            "Answers": "mistral",
            "Summary": "mistral"
        },
        "English": {
            "Correction": "llama3", # As per PS1 script
            "Refinement": "mistral",
            "Subtitles": "mistral",
            "Audit": "mistral",
            "Questions": "mistral",
            "Answers": "mistral",
            "Summary": "mistral"
        }
    }

    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("MediaPipeline")
        self.whisper_model = None # Lazy load

    def _load_whisper(self, model_size="small"):
        if not self.whisper_model:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.logger.info(f"Loading Whisper model: {model_size} on {device.upper()}")
            self.whisper_model = whisper.load_model(model_size, device=device)

    def extract_audio(self, video_path: str, output_wav: str):
        """Extract audio using ffmpeg, similar to PS1 script."""
        if os.path.exists(output_wav):
            self.logger.info("Audio already extracted.")
            return

        self.logger.info(f"Extracting audio from {video_path}")
        # ffmpeg -y -i input -vn -acodec pcm_s16le -ar 16000 -ac 1 output.wav
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            output_wav
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def transcribe(self, audio_path: str, output_dir: str) -> Dict[str, Any]:
        """Run Whisper transcription."""
        self._load_whisper()
        
        self.logger.info(f"Transcribing {audio_path}...")
        # Enable word_timestamps to get confidence scores for correction logic
        result = self.whisper_model.transcribe(audio_path, word_timestamps=True)
        
        # Save raw text
        text_path = os.path.join(output_dir, Path(audio_path).stem + ".txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(result["text"])
        
        # Save JSON (metadata)
        json_path = os.path.join(output_dir, Path(audio_path).stem + ".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        return result

    def detect_language(self, metadata: Dict[str, Any]) -> str:
        lang_code = metadata.get("language", "en")
        return "German" if lang_code == "de" else "English"

    def ollama_generate(self, model: str, prompt: str, output_format: str = None) -> str:
        """Wrapper for Ollama generation with explicit timeout, context, and format."""
        try:
            self.logger.info(f"Querying Ollama model: {model} (Format: {output_format})")
            url = "http://127.0.0.1:11434/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": 4096,
                    "num_predict": -1
                }
            }
            if output_format == "json":
                payload["format"] = "json"

            # Set a long timeout (e.g., 5 minutes)
            response = httpx.post(url, json=payload, timeout=300.0)
            if response.status_code == 200:
                resp_json = response.json()
                if "response" not in resp_json:
                    self.logger.error(f"Unexpected Ollama response: {resp_json}")
                    return ""
                return resp_json["response"]
            else:
                self.logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return ""
        except Exception as e:
            self.logger.error(f"Ollama error: {e}")
            return ""

    def correct_text(self, text: str, language: str) -> str:
        model = self.MODEL_MAP[language]["Correction"]
        # Logic from PS1: "Correct ONLY grammar..."
        instruction = "auf Deutsch (in German language)" if language == "German" else "in English"
        prompt = (
            f"Correct ONLY grammar, spelling, and punctuation errors in this {language} text. "
            f"DO NOT translate. DO NOT change the language. Your output must be {instruction}. "
            f"Keep all meaning and formatting intact.\n\n{text}"
        )
        return self.ollama_generate(model, prompt)

    def refine_text(self, text: str, language: str) -> str:
        model = self.MODEL_MAP[language]["Refinement"]
        instruction = "auf Deutsch (in German language)" if language == "German" else "in English"
        prompt = (
            f"Rewrite this {language} transcript into natural, idiomatic, grammatically correct {language} language. "
            f"DO NOT translate to any other language. Your output MUST be {instruction}. "
            f"Keep all meaning intact.\n\n{text}"
        )
        return self.ollama_generate(model, prompt)

    def generate_audit(self, text: str, language: str) -> str:
        model = self.MODEL_MAP[language]["Audit"]
        prompt = (
            f"Analyze this {language} transcript and return a Markdown report with ## headings, "
            f"**bold** for emphasis, bullet points. Cover: clarity, information level, tone, bias.\n\n{text}"
        )
        return self.ollama_generate(model, prompt)

    def generate_summary(self, text: str, language: str) -> str:
        model = self.MODEL_MAP[language]["Summary"]
        prompt = f"Summarize this {language} transcript into 5 bullet points.\n\n{text}"
        return self.ollama_generate(model, prompt)

    def generate_outputs(self, result: Dict[str, Any], output_path: str):
        """Generate standard Whisper outputs (srt, vtt, tsv)."""
        from whisper.utils import get_writer
        
        # Output directory is parent of the audio file in our structure? 
        # Actually pipeline.py passes str(wav_path) as output_path.
        # wav_path is .../output_dir/basename.wav
        # So parent is output_dir.
        output_dir = str(Path(output_path).parent)
        
        # We want to save plain .srt, .vtt, .tsv
        # Whisper writer appends extension automatically if not present, but here we explicitly call them
        for fmt in ["srt", "vtt", "tsv"]:
            writer = get_writer(fmt, output_dir)
            writer(result, output_path)     

    def generate_netflix_subtitles(self, target_path: str, language: str) -> str:
        """
        Deterministically reformat subtitles to Netflix standards using Python and Pydantic schema.
        Source: Whisper raw JSON output (single source of truth).
        Rules: Max 42 chars/line, Max 2 lines/block.
        """
        # target_path usually is the SRT or the JSON path. 
        # In pipeline, we pass 'srt_path'. Let's find the corresponding JSON.
        # srt_path: .../name.srt -> json_path: .../name.json
        
        json_path = target_path.replace('.srt', '.json')
        if not os.path.exists(json_path):
             self.logger.warning(f"Source JSON not found at {json_path}, falling back to SRT parsing.")
             # Fallback logic could go here or we just fail/return empty
             # For now, let's assume JSON exists as per standard pipeline
             return ""

        try:
            from pydantic import BaseModel, Field
            from typing import List, Optional
            import json
            import math

            # Load Whisper Raw JSON
            with open(json_path, 'r', encoding='utf-8') as f:
                whisper_data = json.load(f)
            
            segments = whisper_data.get('segments', [])
            if not segments: return ""

            # --- NFLX-TT Schema Definition ---
            class Metadata(BaseModel):
                title: str = "Unknown"
                language: str = "en"
            class Style(BaseModel):
                id: str
                textAlign: str = "center"
                fontFamily: str = "Arial"
                fontSizePct: int = 100
                color: str = "#FFFFFF"

            class Origin(BaseModel):
                x_pct: float
                y_pct: float

            class Extent(BaseModel):
                width_pct: float
                height_pct: float

            class Layout(BaseModel):
                id: str
                displayAlign: str
                origin: Origin
                extent: Extent

            class Subtitle(BaseModel):
                id: str
                begin: str
                end: str
                style: str
                region: str
                lines: List[str]

            class NetflixTT(BaseModel):
                metadata: Metadata
                styles: List[Style]
                layout: List[Layout]
                subtitles: List[Subtitle]

            # --- Formatting Logic ---
            subtitles_list = []
            
            def format_time(t_sec):
                h = int(t_sec // 3600)
                m = int((t_sec % 3600) // 60)
                s = int(t_sec % 60)
                ms = int((t_sec * 1000) % 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            global_index = 1

            for segment in segments:
                t0 = segment.get('start', 0.0)
                t1 = segment.get('end', 0.0)
                text = segment.get('text', '').strip()
                
                if not text: continue

                # Word wrap to 42 chars
                words = text.split()
                new_lines = []
                current_line = []
                current_len = 0
                
                for word in words:
                    if current_len + len(word) + (1 if current_len > 0 else 0) <= 42:
                        current_line.append(word)
                        current_len += len(word) + (1 if current_len > 0 else 0)
                    else:
                        new_lines.append(" ".join(current_line))
                        current_line = [word]
                        current_len = len(word)
                if current_line:
                    new_lines.append(" ".join(current_line))
                
                # Strict 2-line enforce: Split event if > 2 lines
                import math
                num_exceeding = len(new_lines)
                
                if num_exceeding > 2:
                    # Calculate how many 2-line blocks we need
                    num_chunks = math.ceil(num_exceeding / 2.0)
                    
                    duration = t1 - t0
                    chunk_dur = duration / num_chunks
                    
                    current_idx = 0
                    for c in range(num_chunks):
                        # Chunk logic
                        chunk_lines = new_lines[current_idx : current_idx + 2]
                        current_idx += 2
                        
                        chunk_start = t0 + (c * chunk_dur)
                        chunk_end = t0 + ((c + 1) * chunk_dur)
                        
                        subtitles_list.append(Subtitle(
                            id=str(global_index),
                            begin=format_time(chunk_start).replace(',', '.'),
                            end=format_time(chunk_end).replace(',', '.'),
                            style="s1",
                            region="bottom",
                            lines=chunk_lines
                        ))
                        global_index += 1
                else:
                    subtitles_list.append(Subtitle(
                        id=str(global_index),
                        begin=format_time(t0).replace(',', '.'),
                        end=format_time(t1).replace(',', '.'),
                        style="s1",
                        region="bottom",
                        lines=new_lines
                    ))
                    global_index += 1

            # Create full object
            nflx_data = NetflixTT(
                metadata=Metadata(title=Path(json_path).stem, language=language),
                styles=[Style(id="s1")],
                layout=[Layout(
                    id="bottom", 
                    displayAlign="after", 
                    origin=Origin(x_pct=10, y_pct=80), 
                    extent=Extent(width_pct=80, height_pct=20)
                )],
                subtitles=subtitles_list
            )
            
            # Save JSON artifact
            out_json_path = target_path.replace(".srt", "_netflix.json")
            with open(out_json_path, "w", encoding="utf-8") as f:
                f.write(nflx_data.model_dump_json(indent=2))

            # Generate SRT output from the structured data
            srt_output = []
            for sub in nflx_data.subtitles:
                # Convert time back to comma format for SRT
                t_start = sub.begin.replace('.', ',')
                t_end = sub.end.replace('.', ',')
                text_block = "\n".join(sub.lines)
                srt_output.append(f"{sub.id}\n{t_start} --> {t_end}\n{text_block}")
            
            return "\n\n".join(srt_output)

        except Exception as e:
            self.logger.error(f"Failed to generate Netflix TT: {e}")
            return Path(target_path).read_text(encoding="utf-8", errors="ignore")

    def generate_questions(self, text: str, language: str) -> str:
        model = self.MODEL_MAP[language]["Questions"]
        base_prompt = (
            f"Analyze this {language} transcript and generate questions NOT answered in the content. "
            "ONLY include questions where the answer is NOT explicitly stated. "
            "Focus on: information gaps, logical next steps, implied assumptions. "
            f"Return 10-20 numbered questions in {language}."
        )
        prompt = f"{base_prompt}\n\n{text}"
        return self.ollama_generate(model, prompt)

    def generate_answers(self, text: str, questions: str, language: str) -> str:
        model = self.MODEL_MAP[language]["Answers"]
        prompt = (
            f"Answer these questions based ONLY on the transcript. If unclear, propose hypotheses. "
            f"Format: Q1: [question] A1: [answer]\n\n--- TRANSCRIPT ---\n{text}\n\n--- QUESTIONS ---\n{questions}"
        )
        return self.ollama_generate(model, prompt)

    def compose_insight_report(self, base_dir: Path, base_name: str, language: str) -> str:
        """Aggregate all artifacts into one report."""
        files = {
            "Summary": base_dir / f"{base_name}_summary.txt",
            "Audit": base_dir / f"{base_name}_audit.md",
            "Questions": base_dir / f"{base_name}_questions.txt",
            "Answers": base_dir / f"{base_name}_answers.txt"
        }
        
        report = [
            f"# AI Insight Report ({base_name})",
            f"**Generated:** {language}",
            "---"
        ]
        
        for section, path in files.items():
            report.append(f"## {section}")
            if path.exists():
                report.append(path.read_text(encoding="utf-8"))
            else:
                report.append("> Not available")
            report.append("\n---\n")
            
        return "\n".join(report)

    def process_full_pipeline(self, video_path: str, progress_callback=None, options: Dict[str, bool] = None, cancel_callback=None):
        """
        Orchestrate the entire flow.
        progress_callback: function(stage, data)
        options: Dict with keys like 'run_transcription', 'skip_existing', etc.
        cancel_callback: function returning bool, true if cancelled
        """
        if options is None:
            options = {}

        # Default options (if not specified, perform the action)
        # However, if ANY specific 'run_' flag is explicitly passed as True, 
        # we might want to default others to False (like the PS script's $OnlyX logic).
        # But for the API, it's cleaner to just respect the explicit booleans passed from UI.
        # The UI will handle the "Only" logic by unchecking others.
        
        should_transcribe = options.get("run_transcription", True)
        should_correct = options.get("run_correction", True)
        should_subtitles = options.get("run_subtitles", True)
        should_audit = options.get("run_audit", True)
        should_qa = options.get("run_qa", True)
        should_insights = options.get("run_insights", True)
        should_diarize = options.get("run_diarization", False)  # Opt-in feature
        should_vlm = options.get("run_vlm", True)  # Default ON per user request
        vlm_model = options.get("vlm_model", "minicpm-v")  # Ollama vision model (MiniCPM-V default - best for technical content)
        scene_threshold = options.get("scene_threshold", 10.0)  # Scene detection sensitivity (lowered for more scenes)
        
        skip_existing = options.get("skip_existing", False)
        
        def notify(stage, data=None):
            if progress_callback:
                progress_callback(stage, data)
        
        def check_cancel():
            if cancel_callback and cancel_callback():
                notify("cancelled")
                raise Exception("Job Cancelled by User")

        video_path = Path(video_path)
        base_name = video_path.stem
        output_dir = video_path.parent / base_name
        output_dir.mkdir(exist_ok=True)
        
        check_cancel()
        notify("starting", {"output_dir": str(output_dir)})

        # 1. Audio Extraction (Always needed if we plan to transcribe)
        wav_path = output_dir / f"{base_name}.wav"
        if should_transcribe:
            if wav_path.exists() and skip_existing:
                notify("skipping_audio_extraction")
            elif not wav_path.exists():
                check_cancel()
                notify("extracting_audio")
                self.extract_audio(str(video_path), str(wav_path))

        # 2. Transcription
        srt_path = output_dir / f"{base_name}.srt"
        raw_text = ""
        result = {}
        
        check_cancel()
        
        if should_transcribe:
            txt_path = output_dir / f"{base_name}.txt"
            if skip_existing and txt_path.exists() and srt_path.exists():
                notify("skipping_transcription")
                # Load existing if available for downstream usage
                try:
                    raw_text = txt_path.read_text(encoding="utf-8")
                    json_path = output_dir / f"{base_name}.json"
                    if json_path.exists():
                        with open(json_path, "r", encoding="utf-8") as f:
                            result = json.load(f)
                except:
                    pass
            else:
                notify("transcribing")
                result = self.transcribe(str(wav_path), str(output_dir))
                raw_text = result["text"]
                self.generate_outputs(result, str(wav_path))
        
        # 3. Language Detection
        language = "English"
        if result:
            language = self.detect_language(result)
        else:
             # Try to load from JSON if we skipped transcription
             json_path = output_dir / f"{base_name}.json"
             if json_path.exists():
                 with open(json_path, "r", encoding="utf-8") as f:
                     loaded = json.load(f)
                     language = self.detect_language(loaded)
                     result = loaded # Ensure we have result for JSON card

        self.logger.info(f"Detected Language: {language}")
        
        # Collect generated artifact content
        transcription_data = {"language": language, "raw_text": raw_text}
        
        # SRT
        if srt_path.exists():
            transcription_data["srt"] = srt_path.read_text(encoding="utf-8")
            
        # VTT
        vtt_path = output_dir / f"{base_name}.vtt"
        if vtt_path.exists():
            transcription_data["vtt"] = vtt_path.read_text(encoding="utf-8")
            
        # JSON
        if result:
             transcription_data["json"] = json.dumps(result, indent=2)

        notify("transcription_complete", transcription_data)

        # 3.5. VLM Visual Analysis (Default ON per user request)
        visual_analyses = []
        vlm_corrections = []
        
        check_cancel()
        
        # Check if this is a video file (has video track)
        video_extensions = ['.mp4', '.mkv', '.mov', '.avi', '.webm', '.wmv']
        is_video = video_path.suffix.lower() in video_extensions
        
        if should_vlm and VLM_AVAILABLE and is_video and result:
            visual_json_path = output_dir / "visual.json"
            corrections_json_path = output_dir / "corrections.json"
            keyframes_dir = output_dir / "keyframes"
            
            if skip_existing and visual_json_path.exists() and corrections_json_path.exists():
                notify("skipping_vlm")
                # Load existing VLM results
                try:
                    with open(visual_json_path, 'r', encoding='utf-8') as f:
                        visual_analyses = json.load(f)
                    with open(corrections_json_path, 'r', encoding='utf-8') as f:
                        vlm_corrections = json.load(f).get("corrections", [])
                except Exception as e:
                    self.logger.warning(f"Could not load existing VLM results: {e}")
            else:
                try:
                    # Stage 1: Scene Detection
                    notify("detecting_scenes", {"threshold": scene_threshold})
                    scenes = scene_detector.detect_scenes(str(video_path), threshold=scene_threshold)
                    
                    if scenes:
                        # Stage 2: Keyframe Extraction
                        notify("extracting_keyframes", {"scene_count": len(scenes)})
                        keyframes_dir.mkdir(parents=True, exist_ok=True)
                        keyframe_paths = scene_detector.extract_keyframes(
                            str(video_path), 
                            scenes, 
                            str(keyframes_dir)
                        )
                        
                        # Stage 3: Visual Analysis (OCR + VLM)
                        if keyframe_paths:
                            notify("analyzing_visuals", {"keyframe_count": len(keyframe_paths)})
                            
                            # Configure VLM model if specified
                            if vlm_model:
                                visual_analyzer.vlm_model = vlm_model
                            
                            # Check if OCR container is available
                            ocr_available = visual_analyzer.check_ocr_available()
                            if not ocr_available:
                                self.logger.warning("EasyOCR not initialized - skipping OCR")
                                notify("vlm_warning", {"message": "OCR container not available"})
                            
                            # Analyze each keyframe
                            timestamps = [s.mid_time for s in scenes]
                            visual_analyses = visual_analyzer.analyze_all_keyframes(
                                keyframe_paths,
                                timestamps,
                                run_vlm=visual_analyzer.check_vlm_available()
                            )
                            
                            # Save visual analysis results
                            with open(visual_json_path, 'w', encoding='utf-8') as f:
                                json.dump(visual_analyses, f, indent=2, ensure_ascii=False)
                            
                            # Stage 4: Transcript Enhancement
                            if visual_analyses and should_correct:
                                notify("enhancing_transcript", {"term_count": sum(len(v.get("extracted_terms", [])) for v in visual_analyses)})
                                
                                # Build vocabulary and enhance
                                visual_vocab = transcript_enhancer.build_visual_vocabulary(visual_analyses)
                                enhanced_result, corrections = transcript_enhancer.enhance_transcript(
                                    result,
                                    visual_vocab
                                )
                                
                                # Update result with enhanced version
                                if corrections:
                                    result = enhanced_result
                                    raw_text = result.get("text", raw_text)
                                    vlm_corrections = [c.__dict__ if hasattr(c, '__dict__') else c for c in corrections]
                                
                                # Save corrections log
                                transcript_enhancer.save_correction_log(
                                    corrections,
                                    str(corrections_json_path),
                                    video_id=base_name
                                )
                                
                                notify("vlm_complete", {
                                    "scenes_detected": len(scenes),
                                    "keyframes_analyzed": len(keyframe_paths),
                                    "corrections_made": len(corrections),
                                    "visual_terms": len(visual_vocab)
                                })
                    else:
                        notify("vlm_warning", {"message": "No scenes detected in video"})
                        
                except Exception as e:
                    self.logger.error(f"VLM processing failed: {e}")
                    notify("vlm_error", {"error": str(e)})
                    # Continue pipeline without VLM enhancement
                    
                # Generate reports if VLM completed successfully
                if visual_json_path and visual_json_path.exists():
                    try:
                        notify("generating_reports", {"stage": "merged_json"})
                        
                        # Load visual analysis
                        with open(visual_json_path, 'r', encoding='utf-8') as f:
                            visual_analysis = json.load(f)
                        
                        # Load corrections
                        corrections_data = []
                        if corrections_json_path and corrections_json_path.exists():
                            with open(corrections_json_path, 'r', encoding='utf-8') as f:
                                corrections_data = json.load(f).get("corrections", [])
                        
                        # Prepare metadata for reports
                        report_metadata = {
                            "file_path": str(video_path),
                            "duration": result.get("duration", 0),
                            "vlm_model": vlm_model,
                            "vlm_enabled": True,
                            "keyframes_dir": str(keyframes_dir)
                        }
                        
                        # Generate merged JSON
                        merged_path = report_generator.generate_merged_json(
                            output_dir=str(output_dir),
                            transcript_segments=result.get("segments", []),
                            visual_analysis=visual_analysis,
                            corrections=corrections_data,
                            metadata=report_metadata,
                            result=result
                        )
                        result["merged_path"] = merged_path
                        self.logger.info(f"Generated merged.json: {merged_path}")
                        
                        # Generate PDF report
                        notify("generating_reports", {"stage": "pdf_report"})
                        pdf_path = report_generator.generate_pdf_report(
                            output_dir=str(output_dir),
                            merged_json_path=merged_path,
                            video_name=base_name
                        )
                        if pdf_path:
                            result["pdf_report_path"] = pdf_path
                            self.logger.info(f"Generated PDF report: {pdf_path}")
                        
                    except Exception as e:
                        self.logger.error(f"Report generation failed: {e}")
                        notify("report_error", {"error": str(e)})
        
        
        elif should_vlm and not VLM_AVAILABLE:
            self.logger.warning("VLM requested but services not available (missing dependencies)")
        elif should_vlm and not is_video:
            self.logger.info("VLM skipped - input is audio-only file")

        # 3.6. Speaker Diarization (Optional)
        diarization_result = None
        speaker_transcript = ""
        
        check_cancel()
        
        if should_diarize and DIARIZATION_AVAILABLE and result:
            speaker_json_path = output_dir / f"{base_name}_speakers.json"
            speaker_txt_path = output_dir / f"{base_name}_speaker_transcript.txt"
            speaker_srt_path = output_dir / f"{base_name}_speaker_transcript.srt"
            
            if skip_existing and speaker_json_path.exists():
                notify("skipping_diarization")
                # Load existing diarization
                try:
                    with open(speaker_json_path, 'r') as f:
                        diarization_result = json.load(f)
                    if speaker_txt_path.exists():
                        speaker_transcript = speaker_txt_path.read_text(encoding="utf-8")
                except Exception as e:
                    self.logger.warning(f"Could not load existing diarization: {e}")
            elif wav_path.exists():
                try:
                    notify("diarizing")
                    # Run diarization
                    diarization_result = diarizer.diarize(str(wav_path), str(output_dir))
                    
                    # Merge with Whisper result
                    merged_result = diarizer.merge_with_transcript(diarization_result, result)
                    
                    # Save speaker JSON
                    with open(speaker_json_path, 'w', encoding='utf-8') as f:
                        json.dump(diarization_result, f, indent=2)
                    
                    # Generate speaker-labeled formats
                    speaker_transcript = diarizer.format_speaker_transcript(merged_result, 'txt')
                    speaker_txt_path.write_text(speaker_transcript, encoding='utf-8')
                    
                    speaker_srt = diarizer.format_speaker_transcript(merged_result, 'srt')
                    speaker_srt_path.write_text(speaker_srt, encoding='utf-8')
                    
                    # Update result with speaker info
                    result = merged_result
                    
                    self.logger.info(f"Diarization complete: {diarization_result.get('num_speakers', 0)} speakers detected")
                    
                except Exception as e:
                    self.logger.error(f"Diarization failed: {e}")
                    # Continue pipeline without diarization
                    diarization_result = {"error": str(e)}
            
            if diarization_result:
                notify("diarization_complete", {
                    "speakers": diarization_result.get('speakers', []),
                    "num_speakers": diarization_result.get('num_speakers', 0),
                    "speaker_transcript": speaker_transcript
                })
        elif should_diarize and not DIARIZATION_AVAILABLE:
            self.logger.warning("Diarization requested but not available (NeMo not installed)")

        # 4. Correction
        clean_path = output_dir / f"{base_name}_clean.txt"
        corrected = ""
        
        check_cancel()
        
        if should_correct:
            if skip_existing and clean_path.exists():
                 notify("skipping_correction")
                 corrected = clean_path.read_text(encoding="utf-8")
            elif raw_text:
                notify("correcting")
                corrected = self.correct_text(raw_text, language)
                clean_path.write_text(corrected, encoding="utf-8")
            else:
                 # Try load if exists even if we didn't just generate it
                 if clean_path.exists(): corrected = clean_path.read_text(encoding="utf-8")

        # 5. Refinement
        refined_path = output_dir / f"{base_name}_refined.txt"
        refined = ""
        
        check_cancel()
        
        if should_correct: # Linked to correction often, but could be separate. The PS keeps them somewhat tied or sequentiual.
            if skip_existing and refined_path.exists():
                notify("skipping_refinement")
                refined = refined_path.read_text(encoding="utf-8")
            elif corrected:
                notify("refining")
                refined = self.refine_text(corrected, language)
                refined_path.write_text(refined, encoding="utf-8")
            else:
                if refined_path.exists(): refined = refined_path.read_text(encoding="utf-8")
        
        if refined:
            # Send both refined and corrected generic event or specific
            notify("refinement_complete", {"refined_text": refined, "clean_text": corrected})

        # 6. Netflix Subtitles
        check_cancel()
        if should_subtitles:
            netflix_path = output_dir / f"{base_name}_netflix.srt"
            netflix_srt = ""
            if skip_existing and netflix_path.exists():
                notify("skipping_subtitles")
                netflix_srt = netflix_path.read_text(encoding="utf-8")
            elif srt_path.exists():
                notify("generating_subtitles")
                netflix_srt = self.generate_netflix_subtitles(str(srt_path), language)
                netflix_path.write_text(netflix_srt, encoding="utf-8")
            
            if netflix_srt:
                notify("subtitles_complete", {"netflix_srt": netflix_srt})

        # 7. Analysis
        notify("analyzing")
        
        # Audit
        check_cancel()
        if should_audit:
            audit_path = output_dir / f"{base_name}_refined_audit.md"
            audit = ""
            if skip_existing and audit_path.exists():
                audit = audit_path.read_text(encoding="utf-8")
            elif refined:
                audit = self.generate_audit(refined, language)
                audit_path.write_text(audit, encoding="utf-8")
            if audit: notify("audit_complete", {"audit": audit})
        
        # Summary (Usually part of insights/general analysis)
        check_cancel()
        if should_insights:
            summary_path = output_dir / f"{base_name}_refined_summary.txt"
            summary = ""
            if skip_existing and summary_path.exists():
                summary = summary_path.read_text(encoding="utf-8")
            elif refined:
                summary = self.generate_summary(refined, language)
                summary_path.write_text(summary, encoding="utf-8")
            if summary: notify("summary_complete", {"summary": summary})
        
        # Questions
        check_cancel()
        questions_path = output_dir / f"{base_name}_refined_questions.txt"
        questions = ""
        if should_qa:
            if skip_existing and questions_path.exists():
                questions = questions_path.read_text(encoding="utf-8")
            elif refined:
                questions = self.generate_questions(refined, language)
                questions_path.write_text(questions, encoding="utf-8")
            if questions: notify("questions_complete", {"questions": questions})
        
        # Answers
        check_cancel()
        if should_qa and questions: # Answers depend on QA
            answers_path = output_dir / f"{base_name}_refined_answers.txt"
            answers = ""
            if skip_existing and answers_path.exists():
                answers = answers_path.read_text(encoding="utf-8")
            elif refined:
                answers = self.generate_answers(refined, questions, language)
                answers_path.write_text(answers, encoding="utf-8")
            if answers: notify("answers_complete", {"answers": answers})

        # 8. Compose Final Report
        check_cancel()
        if should_insights:
            notify("composing")
            insights = self.compose_insight_report(output_dir, base_name, language)
            (output_dir / f"{base_name}_insights.md").write_text(insights, encoding="utf-8")

        final_result = {
            "status": "completed",
            "output_dir": str(output_dir),
            "language": language,
            "artifacts": [
                f"{base_name}_clean.txt",
                f"{base_name}_refined.txt",
                f"{base_name}_netflix.srt",
                f"{base_name}_insights.md",
                f"{base_name}_refined_audit.md",
                f"{base_name}_refined_summary.txt",
                f"{base_name}_refined_questions.txt",
                f"{base_name}_refined_answers.txt",
                f"{base_name}_speakers.json",
                f"{base_name}_speaker_transcript.txt",
                f"{base_name}_speaker_transcript.srt"
            ]
        }
        notify("complete", final_result)
        return final_result

# Singleton instance
pipeline = MediaPipeline()
