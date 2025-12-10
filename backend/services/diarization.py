"""
Speaker Diarization Service using NVIDIA NeMo
Apache 2.0 Licensed - Commercial use allowed
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import torch

logger = logging.getLogger("Diarization")


class SpeakerDiarizer:
    """Handles speaker diarization using NVIDIA NeMo ClusteringDiarizer."""
    
    def __init__(self):
        self.diarizer = None
        self._initialized = False
        
    def _lazy_init(self):
        """Lazy initialization of NeMo models to avoid loading if not needed."""
        if self._initialized:
            return
            
        try:
            from nemo.collections.asr.models import ClusteringDiarizer
            from omegaconf import OmegaConf
            
            logger.info("Initializing NeMo ClusteringDiarizer...")
            
            # NeMo expects the config to have 'diarizer' as the root key
            # and internally accesses cfg.diarizer.* properties
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            
            config = {
                'device': device,  # Required by NeMo for model loading
                'num_workers': 0,  # Required for data loading
                'sample_rate': 16000,
                'batch_size': 64,
                'verbose': True,
                'diarizer': {
                    'manifest_filepath': None,
                    'out_dir': None,
                    'oracle_vad': False,
                    'collar': 0.25,
                    'ignore_overlap': True,
                    'device': device,
                    'num_workers': 0,
                    'batch_size': 64,
                    'verbose': True,
                    'clustering': {
                        'parameters': {
                            'oracle_num_speakers': False,
                            'max_num_speakers': 8,
                            'enhanced_count_thres': 80,
                            'max_rp_threshold': 0.25,
                            'sparse_search_volume': 30
                        }
                    },
                    'vad': {
                        'model_path': 'vad_multilingual_marblenet',
                        'device': device,
                        'num_workers': 0,
                        'batch_size': 64,
                        'parameters': {
                            'window_length_in_sec': 0.15,
                            'shift_length_in_sec': 0.01,
                            'smoothing': 'median',
                            'overlap': 0.5,
                            'onset': 0.8,
                            'offset': 0.6,
                            'pad_onset': 0.05,
                            'pad_offset': -0.1,
                            'min_duration_on': 0.2,
                            'min_duration_off': 0.2,
                            'filter_speech_first': True
                        }
                    },
                    'speaker_embeddings': {
                        'model_path': 'titanet_large',
                        'device': device,
                        'num_workers': 0,
                        'batch_size': 64,
                        'parameters': {
                            'window_length_in_sec': 1.5,
                            'shift_length_in_sec': 0.75,
                            'multiscale_weights': [1.0, 1.0, 1.0],
                            'save_embeddings': False
                        }
                    }
                }
            }
            
            cfg = OmegaConf.create(config)
            
            # Pass FULL cfg (with diarizer key), NOT cfg.diarizer
            # NeMo internally does cfg.diarizer.* access
            self.diarizer = ClusteringDiarizer(cfg=cfg)
            self._initialized = True
            logger.info("NeMo ClusteringDiarizer initialized successfully")
            
        except ImportError as e:
            logger.error(f"NeMo not installed: {e}")
            logger.error("Install with: pip install nemo_toolkit[asr]")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize diarizer: {e}")
            raise
    
    def create_manifest(self, audio_path: str, output_dir: Path) -> Path:
        """
        Create NeMo-compatible manifest file.
        Format: JSON lines with audio_filepath, offset, duration, label
        """
        import wave
        import contextlib
        
        # Get audio duration
        duration = 0.0
        try:
            if audio_path.endswith('.wav'):
                with contextlib.closing(wave.open(audio_path, 'r')) as f:
                    frames = f.getnframes()
                    rate = f.getframerate()
                    duration = frames / float(rate)
            else:
                # Fallback: use ffprobe
                import subprocess
                result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-show_entries', 
                     'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', 
                     audio_path],
                    capture_output=True,
                    text=True
                )
                duration = float(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Could not determine duration: {e}, using default")
            duration = 3600.0  # 1 hour default
        
        manifest_path = output_dir / "diarization_manifest.json"
        
        # Create manifest entry
        manifest_entry = {
            "audio_filepath": str(Path(audio_path).absolute()),
            "offset": 0,
            "duration": duration,
            "label": "infer",
            "text": "-",
            "num_speakers": None,
            "rttm_filepath": None,
            "uem_filepath": None
        }
        
        with open(manifest_path, 'w') as f:
            json.dump(manifest_entry, f)
            f.write('\n')
        
        logger.info(f"Created manifest: {manifest_path}")
        return manifest_path
    
    def diarize(self, audio_path: str, output_dir: str) -> Dict[str, Any]:
        """
        Run speaker diarization on audio file.
        
        Returns:
            Dictionary with speaker segments:
            {
                'speakers': ['SPEAKER_00', 'SPEAKER_01', ...],
                'segments': [
                    {'start': 0.0, 'end': 5.2, 'speaker': 'SPEAKER_00'},
                    {'start': 5.2, 'end': 10.5, 'speaker': 'SPEAKER_01'},
                    ...
                ]
            }
        """
        self._lazy_init()
        
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)
        
        try:
            logger.info(f"Starting diarization for: {audio_path}")
            
            # Create manifest file
            manifest_path = self.create_manifest(audio_path, output_path)
            
            # Update diarizer config - use _cfg (internal config attribute)
            self.diarizer._cfg.diarizer.manifest_filepath = str(manifest_path)
            self.diarizer._cfg.diarizer.out_dir = str(output_path)
            
            # Run diarization
            self.diarizer.diarize()
            
            logger.info("Diarization complete, parsing results...")
            
            # Parse RTTM output (Rich Transcription Time Marked)
            rttm_file = output_path / 'pred_rttms' / f"{Path(audio_path).stem}.rttm"
            
            if not rttm_file.exists():
                logger.warning("No RTTM file found, returning single speaker")
                return {
                    'speakers': ['SPEAKER_00'],
                    'segments': []
                }
            
            # Parse RTTM format
            segments = []
            speakers = set()
            
            with open(rttm_file, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 8 and parts[0] == 'SPEAKER':
                        start_time = float(parts[3])
                        duration = float(parts[4])
                        raw_speaker = parts[7]
                        
                        # Normalize speaker label to SPEAKER_XX format
                        # NeMo may output 'speaker_0' or 'SPEAKER_00' depending on version
                        if raw_speaker.startswith('speaker_'):
                            # Convert 'speaker_0' to 'SPEAKER_00'
                            num = raw_speaker.replace('speaker_', '')
                            speaker = f"SPEAKER_{int(num):02d}"
                        else:
                            speaker = raw_speaker
                        
                        segments.append({
                            'start': start_time,
                            'end': start_time + duration,
                            'speaker': speaker
                        })
                        speakers.add(speaker)
            
            # Sort segments by start time
            segments.sort(key=lambda x: x['start'])
            
            result = {
                'speakers': sorted(list(speakers)),
                'segments': segments,
                'num_speakers': len(speakers)
            }
            
            logger.info(f"Detected {len(speakers)} speakers in {len(segments)} segments")
            return result
            
        except Exception as e:
            logger.error(f"Diarization failed: {e}")
            # Return fallback: single speaker
            return {
                'speakers': ['SPEAKER_00'],
                'segments': [],
                'error': str(e)
            }
    
    def merge_with_transcript(
        self, 
        diarization: Dict[str, Any], 
        whisper_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge diarization speaker labels with Whisper transcript segments.
        
        Args:
            diarization: Output from diarize() method
            whisper_result: Whisper transcription result with segments
            
        Returns:
            Enhanced transcript with speaker labels
        """
        if not diarization.get('segments'):
            # No diarization data, assign default speaker
            segments = whisper_result.get('segments', [])
            for seg in segments:
                seg['speaker'] = 'SPEAKER_00'
            return whisper_result
        
        diar_segments = diarization['segments']
        whisper_segments = whisper_result.get('segments', [])
        
        # Assign speakers to Whisper segments based on overlap
        for w_seg in whisper_segments:
            w_start = w_seg.get('start', 0)
            w_end = w_seg.get('end', 0)
            w_mid = (w_start + w_end) / 2  # Use midpoint for assignment
            
            # Find which speaker segment this belongs to
            assigned_speaker = 'SPEAKER_00'  # Default
            
            for d_seg in diar_segments:
                if d_seg['start'] <= w_mid <= d_seg['end']:
                    assigned_speaker = d_seg['speaker']
                    break
            
            w_seg['speaker'] = assigned_speaker
        
        # Add speaker metadata
        whisper_result['speaker_info'] = {
            'num_speakers': diarization.get('num_speakers', 1),
            'speakers': diarization.get('speakers', ['SPEAKER_00'])
        }
        
        return whisper_result
    
    def format_speaker_transcript(
        self, 
        merged_result: Dict[str, Any],
        format_type: str = 'txt'
    ) -> str:
        """
        Format speaker-labeled transcript.
        
        Args:
            merged_result: Output from merge_with_transcript()
            format_type: 'txt', 'srt', or 'json'
            
        Returns:
            Formatted string
        """
        segments = merged_result.get('segments', [])
        
        if format_type == 'txt':
            lines = []
            current_speaker = None
            
            for seg in segments:
                speaker = seg.get('speaker', 'SPEAKER_00')
                text = seg.get('text', '').strip()
                
                if speaker != current_speaker:
                    if current_speaker is not None:
                        lines.append('')  # Blank line between speakers
                    lines.append(f"[{speaker}]")
                    current_speaker = speaker
                
                lines.append(text)
            
            return '\n'.join(lines)
        
        elif format_type == 'srt':
            srt_lines = []
            
            for i, seg in enumerate(segments, 1):
                start = seg.get('start', 0)
                end = seg.get('end', 0)
                speaker = seg.get('speaker', 'SPEAKER_00')
                text = seg.get('text', '').strip()
                
                # Format timestamps
                start_ts = self._format_srt_time(start)
                end_ts = self._format_srt_time(end)
                
                srt_lines.append(f"{i}")
                srt_lines.append(f"{start_ts} --> {end_ts}")
                srt_lines.append(f"[{speaker}] {text}")
                srt_lines.append("")  # Blank line
            
            return '\n'.join(srt_lines)
        
        elif format_type == 'json':
            return json.dumps(merged_result, indent=2, ensure_ascii=False)
        
        else:
            raise ValueError(f"Unknown format: {format_type}")
    
    def _format_srt_time(self, seconds: float) -> str:
        """Format seconds to SRT timestamp: HH:MM:SS,mmm"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds * 1000) % 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# Singleton instance
diarizer = SpeakerDiarizer()
