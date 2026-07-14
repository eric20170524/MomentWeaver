import asyncio
import os
import time
from typing import List, Optional
from rich.progress import Progress, SpinnerColumn, TextColumn
from smart_asset_kit.llm.client import AIClient
import cv2
import numpy as np
from PIL import Image

class VideoEngine:
    def __init__(self, client: AIClient):
        self.client = client

    async def generate_vfx(self, prompt: str, options: dict = None) -> List[str]:
        """Generate dynamic VFX or animated assets."""
        if options is None:
            options = {}
            
        # Handle local reference image
        import base64
        def path_to_b64(path):
            if path and os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                        mime = "image/png"
                        if path.lower().endswith(".jpg") or path.lower().endswith(".jpeg"):
                            mime = "image/jpeg"
                        return f"data:{mime};base64,{b64}"
                except Exception as e:
                    print(f"Warning: Failed to load local reference image {path}: {e}")
            return path

        # Check 'images' list
        if "images" in options and isinstance(options["images"], list):
            options["images"] = [path_to_b64(img) for img in options["images"]]
        
        # Check 'ref_image' or 'image'
        for key in ["ref_image", "image"]:
            if key in options:
                options[key] = path_to_b64(options[key])

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task_id = progress.add_task(description="Submitting video task...", total=None)
            
            try:
                # Duration handling
                if "duration" in options:
                    pass # Already in options
                
                result = await self.client.generate_asset(prompt, **options)
                
                progress.update(task_id, description="Processing video...")
                
                return result.assets
            except Exception as e:
                raise Exception(f"Video generation failed: {e}")

    def extract_spritesheet(self, video_path: str, output_path: str, grid_size: tuple = (4, 4), fps: int = 12, remove_bg: str = "black"):
        """Extract frames and stitch into a spritesheet."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception(f"Cannot open video: {video_path}")
            
        # Simplified placeholder for SpriteSheet extraction logic
        frames = []
        orig_fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = max(1, int(orig_fps / fps))
        
        count = 0
        while True:
            ret, frame = cap.read()
            if not ret: break
            
            if count % frame_interval == 0:
                # Convert BGR to BGRA
                frame_bgra = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
                
                if remove_bg == "black":
                    # Simple thresholding for black bg removal
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    _, mask = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
                    frame_bgra[:, :, 3] = mask
                elif remove_bg == "green":
                     # Simple green chroma key
                     hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                     mask = cv2.inRange(hsv, (36, 25, 25), (86, 255,255))
                     frame_bgra[:, :, 3] = cv2.bitwise_not(mask)
                     
                frames.append(frame_bgra)
            count += 1
            
            if len(frames) >= grid_size[0] * grid_size[1]:
                break # Reached grid limit
                
        cap.release()
        
        if not frames:
             raise Exception("No frames extracted")
             
        h, w = frames[0].shape[:2]
        cols, rows = grid_size
        sheet = np.zeros((h * rows, w * cols, 4), dtype=np.uint8)
        
        for i, fr in enumerate(frames):
            r = i // cols
            c = i % cols
            if r >= rows: break
            sheet[r*h:(r+1)*h, c*w:(c+1)*w] = fr
            
        cv2.imwrite(output_path, sheet)
        return output_path
