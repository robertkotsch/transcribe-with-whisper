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
            self.logger.info(f"Loading Whisper model: {model_size}")
            self.whisper_model = whisper.load_model(model_size)

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

    def generate_subtitles(self, result: Dict[str, Any], output_path: str):
        """Generate standard SRT using Whisper's writer."""
        from whisper.utils import get_writer
        writer = get_writer("srt", str(Path(output_path).parent))
        writer(result, str(output_path))     

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

    def process_full_pipeline(self, video_path: str, progress_callback=None):
        """
        Orchestrate the entire flow.
        progress_callback: function(stage, data)
        """
        def notify(stage, data=None):
            if progress_callback:
                progress_callback(stage, data)

        video_path = Path(video_path)
        base_name = video_path.stem
        output_dir = video_path.parent / base_name
        output_dir.mkdir(exist_ok=True)
        
        notify("starting", {"output_dir": str(output_dir)})

        # 1. Audio Extraction
        wav_path = output_dir / f"{base_name}.wav"
        if not wav_path.exists():
            notify("extracting_audio")
            self.extract_audio(str(video_path), str(wav_path))

        # 2. Transcription
        notify("transcribing")
        result = self.transcribe(str(wav_path), str(output_dir))
        raw_text = result["text"]
        
        # Save Standard SRT
        self.generate_subtitles(result, str(wav_path)) # Writes .srt to wav_path base
        srt_path = output_dir / f"{base_name}.srt"
        
        # 3. Language Detection
        language = self.detect_language(result)
        self.logger.info(f"Detected Language: {language}")
        notify("transcription_complete", {"language": language, "raw_text": raw_text})

        # 4. Correction
        notify("correcting")
        corrected = self.correct_text(raw_text, language)
        (output_dir / f"{base_name}_clean.txt").write_text(corrected, encoding="utf-8")

        # 5. Refinement
        notify("refining")
        refined = self.refine_text(corrected, language)
        refined_path = output_dir / f"{base_name}_refined.txt"
        with open(refined_path, "w", encoding="utf-8") as f:
            f.write(refined)
        
        notify("refinement_complete", {"refined_text": refined})

        # 6. Netflix Subtitles
        if srt_path.exists():
            notify("generating_subtitles")
            netflix_srt = self.generate_netflix_subtitles(str(srt_path), language)
            (output_dir / f"{base_name}_netflix.srt").write_text(netflix_srt, encoding="utf-8")

        # 7. Analysis (Parallel-ish in concept, sequential here)
        notify("analyzing")
        
        audit = self.generate_audit(refined, language)
        (output_dir / f"{base_name}_refined_audit.md").write_text(audit, encoding="utf-8")
        notify("audit_complete", {"audit": audit})
        
        summary = self.generate_summary(refined, language)
        (output_dir / f"{base_name}_refined_summary.txt").write_text(summary, encoding="utf-8")
        notify("summary_complete", {"summary": summary})
        
        questions = self.generate_questions(refined, language)
        (output_dir / f"{base_name}_refined_questions.txt").write_text(questions, encoding="utf-8")
        notify("questions_complete", {"questions": questions})
        
        answers = self.generate_answers(refined, questions, language)
        (output_dir / f"{base_name}_refined_answers.txt").write_text(answers, encoding="utf-8")
        notify("answers_complete", {"answers": answers})

        # 8. Compose Final Report
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
