"""
Seedance (ByteDance) video generation via fal.ai.

Provider: fal.ai  (https://fal.ai/models/fal-ai/bytedance/seedance)
Auth:     FAL_KEY environment variable (read automatically by fal_client)

Endpoints (verified against the fal OpenAPI schema, June 2026):
  - Text-to-video:  fal-ai/bytedance/seedance/v1/{pro,lite}/text-to-video
  - Image-to-video: fal-ai/bytedance/seedance/v1/{pro,lite}/image-to-video

Modality: T2V + I2V. fal does NOT expose a Seedance video-to-video endpoint
(the only video-conditioned variant is lite/reference-to-video, which takes
reference *images*, not a video), so this wrapper does not implement v2v.

The wrapper routes by input: if an image is provided it calls image-to-video
(image uploaded to fal storage to obtain image_url), otherwise text-to-video.
"""

from __future__ import annotations

import os
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union

import httpx

from .base import ModelWrapper

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=os.getenv("LOGLEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)

# Best-effort .env hydration (mirrors the other commercial wrappers).
try:
    from dotenv import load_dotenv, find_dotenv
    _p = find_dotenv(usecwd=True)
    load_dotenv(_p, override=False) if _p else load_dotenv(override=False)
except Exception:
    pass


def _hydrate_fal_key() -> str:
    """Return FAL_KEY, loading a nearby .env if needed."""
    key = os.environ.get("FAL_KEY", "")
    if key:
        return key
    here = Path(__file__).resolve()
    for i in range(1, 6):
        env_path = here.parents[i] / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "FAL_KEY" and "FAL_KEY" not in os.environ:
                    os.environ["FAL_KEY"] = v.strip().strip('"').strip("'")
            break
    return os.environ.get("FAL_KEY", "")


# Valid duration / resolution / aspect-ratio values per the fal schema.
_DURATIONS = {str(n) for n in range(2, 13)}            # "2".."12"
_ASPECT_RATIOS = {"21:9", "16:9", "4:3", "1:1", "3:4", "9:16", "auto"}
_RESOLUTIONS = {"pro": {"480p", "720p", "1080p"}, "lite": {"480p", "720p"}}


class SeedanceService:
    """Calls Seedance on fal.ai for text-to-video and image-to-video."""

    def __init__(self, model: str = "pro", duration: str = "5",
                 resolution: str = "720p", aspect_ratio: str = "auto", **kwargs):
        tier = (model or "pro").lower()
        if tier not in ("pro", "lite"):
            raise ValueError(f"Seedance tier must be 'pro' or 'lite', got {model!r}")
        self.tier = tier
        self.duration = str(duration)
        self.resolution = resolution
        self.aspect_ratio = aspect_ratio

        if not _hydrate_fal_key():
            raise ValueError("FAL_KEY not found. Set it in your environment or .env file.")
        try:
            import fal_client  # noqa: F401
        except ImportError:
            raise ImportError("fal-client not installed. Run: pip install fal-client")
        logger.info(f"Initialized SeedanceService tier={self.tier}")

    def _endpoint(self, image: bool) -> str:
        kind = "image-to-video" if image else "text-to-video"
        return f"fal-ai/bytedance/seedance/v1/{self.tier}/{kind}"

    def _arguments(self, prompt: str, image_url: Optional[str],
                   end_image_url: Optional[str], **over) -> Dict[str, Any]:
        duration = str(over.get("duration", self.duration))
        if duration not in _DURATIONS:
            logger.warning(f"duration {duration} invalid; using 5"); duration = "5"
        resolution = over.get("resolution", self.resolution)
        if resolution not in _RESOLUTIONS[self.tier]:
            fallback = "720p"
            logger.warning(f"resolution {resolution} unsupported for {self.tier}; using {fallback}")
            resolution = fallback
        aspect_ratio = over.get("aspect_ratio", self.aspect_ratio)
        if aspect_ratio not in _ASPECT_RATIOS:
            aspect_ratio = "auto"

        args: Dict[str, Any] = {
            "prompt": prompt,
            "duration": duration,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
        }
        if image_url:
            args["image_url"] = image_url
        if end_image_url:
            args["end_image_url"] = end_image_url
        if over.get("seed") is not None:
            args["seed"] = int(over["seed"])
        return args

    async def generate_video(
        self,
        prompt: str,
        image_path: Optional[Union[str, Path]] = None,
        end_image_path: Optional[Union[str, Path]] = None,
        output_path: Optional[Path] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate a video (image-to-video if image_path given, else text-to-video)."""
        import fal_client

        def _upload(p: Union[str, Path]) -> str:
            return fal_client.upload_file(str(p))

        loop = asyncio.get_event_loop()
        image_url = await loop.run_in_executor(None, _upload, image_path) if image_path else None
        end_url = await loop.run_in_executor(None, _upload, end_image_path) if end_image_path else None

        endpoint = self._endpoint(image=bool(image_url))
        arguments = self._arguments(prompt, image_url, end_url, **kwargs)
        logger.info(f"Submitting Seedance request: {endpoint} ({arguments['resolution']}, {arguments['duration']}s)")

        def _run():
            return fal_client.subscribe(endpoint, arguments=arguments, with_logs=False)

        result = await loop.run_in_executor(None, _run)

        video = (result or {}).get("video") or {}
        video_url = video.get("url")
        if not video_url:
            raise Exception(f"No video URL in Seedance response: {result}")

        out: Dict[str, Any] = {
            "video_url": video_url,
            "seed": (result or {}).get("seed"),
            "endpoint": endpoint,
            "status": "success",
        }
        if output_path:
            saved = await self._download_video(video_url, output_path)
            out["video_path"] = str(saved)
        return out

    async def _download_video(self, url: str, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=600.0) as client:
            r = await client.get(url)
            if r.status_code != 200:
                raise Exception(f"Failed to download video: {r.status_code}")
            output_path.write_bytes(r.content)
        logger.info(f"Downloaded video to: {output_path}")
        return output_path


class SeedanceWrapper(ModelWrapper):
    """ModelWrapper for Seedance (fal.ai). Returns the 8 standardized fields."""

    def __init__(self, model: str = "pro", output_dir: str = "./outputs", **kwargs):
        self.model = model
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.kwargs = kwargs
        self.service = SeedanceService(model=model, **kwargs)

    def generate(
        self,
        image_path: Optional[Union[str, Path]] = None,
        text_prompt: str = "",
        duration: float = 5.0,
        output_filename: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        start_time = time.time()
        output_path = self.output_dir / (output_filename or "video.mp4")

        # The runner always passes image_path; treat a missing/empty path as text-to-video.
        use_image = bool(image_path) and Path(str(image_path)).exists()

        allowed = {"resolution", "aspect_ratio", "seed", "end_image_path"}
        svc_kwargs = {k: v for k, v in kwargs.items() if k in allowed}
        if duration is not None:
            svc_kwargs["duration"] = str(int(duration))

        try:
            result = asyncio.run(
                self.service.generate_video(
                    prompt=text_prompt,
                    image_path=str(image_path) if use_image else None,
                    output_path=output_path,
                    **svc_kwargs,
                )
            )
        except Exception as e:
            logger.error(f"Seedance generation failed: {e}")
            return {
                "success": False, "video_path": None, "error": str(e),
                "duration_seconds": time.time() - start_time, "generation_id": None,
                "model": self.model, "status": "failed",
                "metadata": {"prompt": text_prompt, "modality": "i2v" if use_image else "t2v"},
            }

        return {
            "success": bool(result.get("video_path")),
            "video_path": result.get("video_path"),
            "error": None,
            "duration_seconds": time.time() - start_time,
            "generation_id": str(result.get("seed", "unknown")),
            "model": self.model,
            "status": "success" if result.get("video_path") else "failed",
            "metadata": {
                "prompt": text_prompt,
                "modality": "i2v" if use_image else "t2v",
                "endpoint": result.get("endpoint"),
                "video_url": result.get("video_url"),
                "seed": result.get("seed"),
            },
        }
