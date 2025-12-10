import os
import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Try imports ensuring we handle missing dependencies gracefully
try:
    import whisper
    import ollama
except ImportError:
    print("Warning: 'whisper' or 'ollama' module not found. Please pip install.")

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
        result = self.whisper_model.transcribe(audio_path)
        
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

    def ollama_generate(self, model: str, prompt: str) -> str:
        """Wrapper for Ollama generation."""
        try:
            self.logger.info(f"Querying Ollama model: {model}")
            response = ollama.generate(model=model, prompt=prompt)
            return response.get("response", "")
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
        # Whisper writer saves <audio_filename>.<format>
        
        for fmt in ["srt", "vtt", "tsv"]:
            writer = get_writer(fmt, output_dir)
            writer(result, output_path)     

    def generate_netflix_subtitles(self, srt_path: str, language: str) -> str:
        """Use generic model to reformat SRT to Netflix standards."""
        if not os.path.exists(srt_path): return ""
        
        model = self.MODEL_MAP[language]["Subtitles"]
        prompt = "Reformat to Netflix style: max 42 chars/line, 2 lines, 1-7s duration. Return valid .srt only."
        content = Path(srt_path).read_text(encoding="utf-8")
        
        # Only process reasonable chunks to avoid context limits or weird hallucinations
        # For simplicity in this port, we send the whole thing (assuming < 5 mins video)
        # In prod, you'd chunk this.
        return self.ollama_generate(model, f"{prompt}\n\n{content}")

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
        
        # 3. Language Detection (Need result or loaded json)
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
        
        self.logger.info(f"Detected Language: {language}")
        notify("transcription_complete", {"language": language, "raw_text": raw_text})

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
            notify("refinement_complete", {"refined_text": refined})

        # 6. Netflix Subtitles
        check_cancel()
        if should_subtitles:
            netflix_path = output_dir / f"{base_name}_netflix.srt"
            if skip_existing and netflix_path.exists():
                notify("skipping_subtitles")
            elif srt_path.exists():
                notify("generating_subtitles")
                netflix_srt = self.generate_netflix_subtitles(str(srt_path), language)
                netflix_path.write_text(netflix_srt, encoding="utf-8")

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
                f"{base_name}_refined_answers.txt"
            ]
        }
        notify("complete", final_result)
        return final_result

# Singleton instance
pipeline = MediaPipeline()
