"""
OpenAI Sora via WaveSpeed (https://wavespeed.ai).

WaveSpeed serves Sora-2 with no OpenAI account required — auth is a single
WAVESPEED_API_KEY. Use this when you have a WaveSpeed key rather than direct
OpenAI access (the direct-OpenAI path lives in openai_inference.py).

Auth: WAVESPEED_API_KEY  (Authorization: Bearer ...)

Endpoints (verified against the WaveSpeed v3 model schema, June 2026):
  POST https://api.wavespeed.ai/api/v3/openai/sora-2/{text,image}-to-video
  POST https://api.wavespeed.ai/api/v3/openai/sora-2-pro/{text,image}-to-video
Submit returns a prediction id + a poll URL (data.urls.get); poll until
status == completed, then download data.outputs[0].

Modality: T2V + I2V (routed by whether an input image is present). The image
is sent inline as a base64 data URI, so no separate upload is needed.
"""

from __future__ import annotations

import os
import time
import base64
import asyncio
import logging
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, Union

import httpx

from .base import ModelWrapper

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=os.getenv("LOGLEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)

try:
    from dotenv import load_dotenv, find_dotenv
    _p = find_dotenv(usecwd=True)
    load_dotenv(_p, override=False) if _p else load_dotenv(override=False)
except Exception:
    pass


def _hydrate_wavespeed_key() -> str:
    key = os.environ.get("WAVESPEED_API_KEY", "")
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
                if k.strip() == "WAVESPEED_API_KEY" and "WAVESPEED_API_KEY" not in os.environ:
                    os.environ["WAVESPEED_API_KEY"] = v.strip().strip('"').strip("'")
            break
    return os.environ.get("WAVESPEED_API_KEY", "")


_BASE = "https://api.wavespeed.ai/api/v3"
_DURATIONS = {4, 8, 12, 16, 20}


class SoraWaveSpeedService:
    """Calls OpenAI Sora-2 on WaveSpeed for text-to-video and image-to-video."""

    def __init__(self, model: str = "sora-2", duration: int = 4,
                 size: str = "1280*720", resolution: str = "720p", **kwargs):
        tier = (model or "sora-2").lower()
        if tier not in ("sora-2", "sora-2-pro"):
            raise ValueError(f"WaveSpeed Sora model must be 'sora-2' or 'sora-2-pro', got {model!r}")
        self.tier = tier
        self.duration = int(duration)
        self.size = size
        self.resolution = resolution
        self._key = _hydrate_wavespeed_key()
        if not self._key:
            raise ValueError("WAVESPEED_API_KEY not found. Set it in your environment or .env file.")
        logger.info(f"Initialized SoraWaveSpeedService tier={self.tier}")

    def _endpoint(self, image: bool) -> str:
        kind = "image-to-video" if image else "text-to-video"
        return f"{_BASE}/openai/{self.tier}/{kind}"

    @staticmethod
    def _to_data_uri(image_path: Union[str, Path]) -> str:
        p = Path(image_path)
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    def _payload(self, prompt: str, image: bool, **over) -> Dict[str, Any]:
        duration = int(over.get("duration", self.duration))
        if duration not in _DURATIONS:
            logger.warning(f"duration {duration} invalid; using 4"); duration = 4
        payload: Dict[str, Any] = {"prompt": prompt, "duration": duration}
        if image:
            if self.tier == "sora-2-pro":
                payload["resolution"] = over.get("resolution", self.resolution)
        else:
            payload["size"] = over.get("size", self.size)
        return payload

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}

    async def generate_video(
        self,
        prompt: str,
        image_path: Optional[Union[str, Path]] = None,
        output_path: Optional[Path] = None,
        max_wait: int = 1800,
        poll_interval: int = 5,
        **kwargs,
    ) -> Dict[str, Any]:
        use_image = bool(image_path)
        endpoint = self._endpoint(image=use_image)
        payload = self._payload(prompt, image=use_image, **kwargs)
        if use_image:
            payload["image"] = self._to_data_uri(image_path)

        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(endpoint, headers=self._headers(), json=payload)
            if r.status_code != 200:
                raise Exception(f"WaveSpeed submit failed: {r.status_code} - {r.text[:400]}")
            data = r.json().get("data", {})
            pred_id = data.get("id")
            poll_url = (data.get("urls") or {}).get("get") or f"{_BASE}/predictions/{pred_id}/result"
            if not pred_id:
                raise Exception(f"No prediction id in response: {r.text[:400]}")
            logger.info(f"WaveSpeed Sora submitted: {pred_id} ({self.tier}, {'i2v' if use_image else 't2v'})")

            video_url = await self._poll(client, poll_url, max_wait, poll_interval)

        out: Dict[str, Any] = {"video_url": video_url, "prediction_id": pred_id,
                               "endpoint": endpoint, "status": "success"}
        if output_path:
            out["video_path"] = str(await self._download(video_url, output_path))
        return out

    async def _poll(self, client: httpx.AsyncClient, poll_url: str,
                    max_wait: int, poll_interval: int) -> str:
        start = time.time()
        while time.time() - start < max_wait:
            r = await client.get(poll_url, headers={"Authorization": f"Bearer {self._key}"})
            if r.status_code != 200:
                await asyncio.sleep(poll_interval); continue
            d = r.json().get("data", {})
            status = d.get("status")
            if status in ("completed", "succeeded"):
                outputs = d.get("outputs") or []
                if outputs:
                    return outputs[0]
                raise Exception(f"WaveSpeed completed but no outputs: {d}")
            if status in ("failed", "error"):
                raise Exception(f"WaveSpeed generation failed: {d.get('error') or d}")
            await asyncio.sleep(poll_interval)
        raise TimeoutError(f"WaveSpeed Sora timed out after {max_wait}s")

    async def _download(self, url: str, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=600.0) as client:
            r = await client.get(url)
            if r.status_code != 200:
                raise Exception(f"Failed to download video: {r.status_code}")
            output_path.write_bytes(r.content)
        logger.info(f"Downloaded video to: {output_path}")
        return output_path


class WaveSpeedSoraWrapper(ModelWrapper):
    """ModelWrapper for Sora-2 via WaveSpeed. Returns the 8 standardized fields."""

    def __init__(self, model: str = "sora-2", output_dir: str = "./outputs", **kwargs):
        self.model = model
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.kwargs = kwargs
        self.service = SoraWaveSpeedService(model=model, **kwargs)

    def generate(
        self,
        image_path: Optional[Union[str, Path]] = None,
        text_prompt: str = "",
        duration: float = 4.0,
        output_filename: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        start_time = time.time()
        output_path = self.output_dir / (output_filename or "video.mp4")
        use_image = bool(image_path) and Path(str(image_path)).exists()

        allowed = {"size", "resolution", "duration"}
        svc_kwargs = {k: v for k, v in kwargs.items() if k in allowed}
        if duration is not None:
            svc_kwargs["duration"] = int(duration)

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
            logger.error(f"WaveSpeed Sora generation failed: {e}")
            return {
                "success": False, "video_path": None, "error": str(e),
                "duration_seconds": time.time() - start_time, "generation_id": None,
                "model": self.model, "status": "failed",
                "metadata": {"prompt": text_prompt, "modality": "i2v" if use_image else "t2v",
                             "provider": "wavespeed"},
            }

        return {
            "success": bool(result.get("video_path")),
            "video_path": result.get("video_path"),
            "error": None,
            "duration_seconds": time.time() - start_time,
            "generation_id": result.get("prediction_id", "unknown"),
            "model": self.model,
            "status": "success" if result.get("video_path") else "failed",
            "metadata": {
                "prompt": text_prompt,
                "modality": "i2v" if use_image else "t2v",
                "provider": "wavespeed",
                "endpoint": result.get("endpoint"),
                "video_url": result.get("video_url"),
            },
        }
