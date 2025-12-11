"""
Scene Detection Service

Uses PySceneDetect to detect scene changes in videos and extract keyframes.
"""

import os
import logging
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Scene:
    """Represents a detected scene in a video."""
    index: int
    start_time: float  # seconds
    end_time: float    # seconds
    start_frame: int
    end_frame: int
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def mid_time(self) -> float:
        """Mid-point timestamp for keyframe extraction."""
        return self.start_time + (self.duration / 2)


class SceneDetector:
    """
    Detect scene changes in video files using PySceneDetect.
    
    Uses ContentDetector which analyzes changes in content (luminance, color)
    between frames to detect cuts and scene transitions.
    """
    
    def __init__(self, threshold: float = 27.0, min_scene_len: int = 15):
        """
        Initialize the scene detector.
        
        Args:
            threshold: Scene detection sensitivity (lower = more sensitive).
                      Default 27.0 works well for slides/explainer videos.
            min_scene_len: Minimum scene length in frames to avoid false positives.
        """
        self.threshold = threshold
        self.min_scene_len = min_scene_len
    
    def detect_scenes(self, video_path: str, threshold: Optional[float] = None) -> List[Scene]:
        """
        Detect scene changes in a video.
        
        Args:
            video_path: Path to the video file.
            threshold: Override default threshold for this detection.
            
        Returns:
            List of Scene objects with timestamps.
        """
        try:
            from scenedetect import detect, ContentDetector
        except ImportError:
            logger.error("scenedetect not installed. Run: pip install scenedetect[opencv]")
            return []
        
        video_path = Path(video_path)
        if not video_path.exists():
            logger.error(f"Video not found: {video_path}")
            return []
        
        threshold = threshold or self.threshold
        logger.info(f"Detecting scenes in {video_path.name} (threshold={threshold})")
        
        try:
            # Detect scenes using ContentDetector
            scene_list = detect(
                str(video_path),
                ContentDetector(threshold=threshold, min_scene_len=self.min_scene_len)
            )
            
            scenes = []
            for i, (start, end) in enumerate(scene_list):
                scene = Scene(
                    index=i,
                    start_time=start.get_seconds(),
                    end_time=end.get_seconds(),
                    start_frame=start.get_frames(),
                    end_frame=end.get_frames()
                )
                scenes.append(scene)
            
            logger.info(f"Detected {len(scenes)} scenes")
            return scenes
            
        except Exception as e:
            logger.error(f"Scene detection failed: {e}")
            return []
    
    def extract_keyframes(
        self, 
        video_path: str, 
        scenes: List[Scene], 
        output_dir: str,
        use_mid_point: bool = True
    ) -> List[str]:
        """
        Extract keyframe images from detected scenes.
        
        Args:
            video_path: Path to the video file.
            scenes: List of scenes from detect_scenes().
            output_dir: Directory to save keyframe images.
            use_mid_point: If True, extract frame at scene mid-point.
                          If False, extract first frame of scene.
                          
        Returns:
            List of paths to extracted keyframe images.
        """
        try:
            import cv2
        except ImportError:
            logger.error("opencv-python not installed. Run: pip install opencv-python")
            return []
        
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if not scenes:
            logger.warning("No scenes provided for keyframe extraction")
            return []
        
        logger.info(f"Extracting {len(scenes)} keyframes to {output_dir}")
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error(f"Could not open video: {video_path}")
            return []
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        keyframe_paths = []
        
        try:
            for scene in scenes:
                # Calculate target frame
                if use_mid_point:
                    target_time = scene.mid_time
                else:
                    target_time = scene.start_time
                
                target_frame = int(target_time * fps)
                
                # Seek to frame
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                ret, frame = cap.read()
                
                if ret:
                    # Save keyframe
                    filename = f"scene_{scene.index:04d}_{target_time:.2f}s.jpg"
                    output_path = output_dir / filename
                    cv2.imwrite(str(output_path), frame)
                    keyframe_paths.append(str(output_path))
                    logger.debug(f"Extracted keyframe: {filename}")
                else:
                    logger.warning(f"Could not extract frame at {target_time:.2f}s")
        
        finally:
            cap.release()
        
        logger.info(f"Extracted {len(keyframe_paths)} keyframes")
        return keyframe_paths


# Singleton instance
scene_detector = SceneDetector()
