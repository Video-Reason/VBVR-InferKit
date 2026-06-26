"""
Luma Ray inference implementation.

Direct inference API for Luma's text+image→video generation.
Uses the Luma Agents API (agents.lumalabs.ai/v1) with fal CDN for image hosting.
"""

import os
import time
import requests
from typing import Optional, Dict, Any, Union
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from dotenv import load_dotenv

from .base import ModelWrapper

load_dotenv()


class LumaAPIError(Exception):
    pass


class LumaAuthError(LumaAPIError):
    """Non-retryable authentication error."""
    pass


def _is_retryable(exc):
    return not isinstance(exc, LumaAuthError)


class LumaInference:

    BASE_URL = "https://agents.lumalabs.ai/v1"

    def __init__(
        self,
        aspect_ratio: str = "16:9",
        model: str = "ray-3.2",
        verbose: bool = True,
        output_dir: str = "./outputs",
        **kwargs,
    ):
        self.api_key = os.getenv("LUMA_AGENTS_API_KEY") or os.getenv("LUMA_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Luma API not configured.\n"
                "Set LUMA_AGENTS_API_KEY (preferred) or LUMA_API_KEY in your environment."
            )

        self.aspect_ratio = aspect_ratio
        self.model = model
        self.verbose = verbose

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate(
        self,
        image_path: Union[str, Path],
        text_prompt: str,
        duration: float = 5.0,
        output_filename: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        start_time = time.time()

        try:
            image_url = self._get_image_url(image_path)
            generation_id = self._create_generation(image_url, text_prompt)

            if self.verbose:
                print(f"Started generation: {generation_id}")

            video_url = self._poll_generation(generation_id)

            if not output_filename:
                output_filename = "video.mp4"

            video_path = self.output_dir / output_filename
            self._download_video(video_url, video_path)

            duration_seconds = time.time() - start_time

            if self.verbose:
                print(f"Generated video: {video_path}")
                print(f"   Time taken: {duration_seconds:.1f}s")

            return {
                "success": True,
                "video_path": str(video_path),
                "error": None,
                "duration_seconds": duration_seconds,
                "generation_id": generation_id,
                "model": self.model,
                "status": "success",
                "metadata": {"prompt": text_prompt, "image_path": str(image_path)},
            }

        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "last_attempt") and e.last_attempt.failed:
                error_msg = str(e.last_attempt.exception())
            return {
                "success": False,
                "video_path": None,
                "error": error_msg,
                "duration_seconds": time.time() - start_time,
                "generation_id": "unknown",
                "model": self.model,
                "status": "failed",
                "metadata": {"prompt": text_prompt, "image_path": str(image_path)},
            }

    def _get_image_url(self, image_path: Union[str, Path]) -> str:
        import fal_client

        image_url = fal_client.upload_file(str(image_path))
        if not image_url:
            raise LumaAPIError("Failed to upload image to fal CDN")

        if self.verbose:
            print(f"Serving image at: {image_url}")

        return image_url

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception(_is_retryable),
    )
    def _create_generation(self, image_url: str, text_prompt: str) -> str:
        payload = {
            "prompt": text_prompt,
            "type": "video",
            "model": self.model,
            "aspect_ratio": self.aspect_ratio,
            "video": {
                "resolution": "720p",
                "duration": "5s",
                "start_frame": {
                    "url": image_url,
                },
            },
        }

        response = requests.post(
            f"{self.BASE_URL}/generations",
            headers=self.headers,
            json=payload,
        )

        if response.status_code in (401, 403):
            raise LumaAuthError(f"Authentication failed ({response.status_code}): {response.text}")
        if response.status_code not in (200, 201):
            raise LumaAPIError(f"Failed to create generation ({response.status_code}): {response.text}")

        return response.json()["id"]

    def _poll_generation(self, generation_id: str, timeout: int = 1800) -> str:
        start_time = time.time()

        while time.time() - start_time < timeout:
            response = requests.get(
                f"{self.BASE_URL}/generations/{generation_id}",
                headers=self.headers,
            )

            if response.status_code != 200:
                raise LumaAPIError(f"Failed to check generation: {response.text}")

            data = response.json()
            state = data.get("state")

            if state == "completed":
                output = data.get("output") or []
                if output:
                    return output[0]["url"]
                raise LumaAPIError("Generation completed but no video URL found")

            elif state == "failed":
                reason = data.get("failure_reason", "Unknown error")
                raise LumaAPIError(f"Generation failed: {reason}")

            if self.verbose:
                elapsed = int(time.time() - start_time)
                print(f"   Generating... ({elapsed}s)", end="\r")

            time.sleep(5)

        raise LumaAPIError(f"Generation timed out after {timeout} seconds")

    def _download_video(self, video_url: str, output_path: Path):
        response = requests.get(video_url, stream=True)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)


class LumaWrapper(ModelWrapper):
    """
    VBVR-InferKit wrapper for Luma Dream Machine to match standard interface.
    """
    
    def __init__(
        self,
        model: str,
        output_dir: str = "./outputs",
        **kwargs
    ):
        """Initialize Luma wrapper."""
        self.model = model
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.kwargs = kwargs
        
        # Create LumaInference instance
        self.luma_service = LumaInference(
            model=model,
            output_dir=output_dir,
            **kwargs
        )
    
    def generate(
        self,
        image_path: Union[str, Path],
        text_prompt: str,
        duration: float = 8.0,
        output_filename: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate video using Luma Dream Machine (matches VBVR-InferKit interface).
        
        Args:
            image_path: Path to input image
            text_prompt: Text prompt for video generation
            duration: Video duration in seconds
            output_filename: Optional output filename
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with generation results
        """
        # Sync service output_dir with wrapper output_dir before each generation
        # This ensures videos are saved to the correct location when wrapper is cached
        self.luma_service.output_dir = self.output_dir
        
        return self.luma_service.generate(
            image_path=image_path,
            text_prompt=text_prompt,
            duration=duration,
            output_filename=output_filename,
            **kwargs
        )


def generate_video(
    image_path: str,
    text_prompt: str,
    output_dir: str = "./outputs",
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function for one-shot video generation.
    
    Args:
        image_path: Path to input image
        text_prompt: Text instructions
        output_dir: Where to save the video
        **kwargs: Additional parameters passed to LumaInference
    
    Returns:
        Dictionary with generation results
    """
    client = LumaInference(output_dir=output_dir, **kwargs)
    return client.generate(image_path, text_prompt)
