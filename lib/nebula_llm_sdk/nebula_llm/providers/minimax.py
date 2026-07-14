import asyncio
import base64
import json
import os
import uuid
import httpx
from typing import Any, AsyncGenerator, Dict, List, Optional

from ..base import ExecutionResult
from .openai import OpenAIProvider
from ..types import ModelInfo
from ..logger import logger

class MinimaxProvider(OpenAIProvider):
    async def execute(
        self, model_config: ModelInfo, api_key: str, prompt: str, messages: List[Dict[str, Any]] = [], options: Dict[str, Any] = {}
    ) -> ExecutionResult:
        if options is None:
            options = {}

        task_type = str(options.get("type") or options.get("mode") or model_config.type).lower()
        target_model = model_config.target_model_id.lower()

        # Route to specific capability
        is_tts = (
            task_type == "audio"
            or "tts" in task_type
            or target_model.startswith("speech-")
        )
        is_async_tts = (
            task_type == "async_tts"
        )
        is_voice_clone = (
            task_type == "voice_clone"
        )
        is_lyrics = (
            task_type == "lyrics" or task_type == "lyrics_generation"
        )
        is_music = (
            task_type == "music"
            or "music" in target_model
        )
        is_cover_preprocess = (
            task_type == "music_cover_preprocess"
        )

        if is_voice_clone:
            return await self._execute_voice_clone(model_config, api_key, prompt, options)
        elif is_async_tts:
            return await self._execute_async_tts(model_config, api_key, prompt, options)
        elif is_cover_preprocess:
            return await self._execute_cover_preprocess(model_config, api_key, prompt, options)
        elif is_lyrics:
            return await self._execute_lyrics(model_config, api_key, prompt, options)
        elif is_music:
            return await self._execute_music(model_config, api_key, prompt, options)
        elif is_tts:
            return await self._execute_tts(model_config, api_key, prompt, options)

        # Fallback to standard OpenAI compatible chat
        if "base_url" not in options:
            options["base_url"] = "https://api.minimaxi.com/v1"
        return await super().execute(model_config, api_key, prompt, messages, options)

    async def execute_stream(
        self, model_config: ModelInfo, api_key: str, prompt: str, messages: List[Dict[str, Any]] = [], options: Dict[str, Any] = {}
    ) -> AsyncGenerator[str, None]:
        if options is None:
            options = {}

        task_type = str(options.get("type") or options.get("mode") or model_config.type).lower()
        target_model = model_config.target_model_id.lower()

        is_custom = (
            task_type in ["audio", "async_tts", "voice_clone", "lyrics", "lyrics_generation", "music", "music_cover_preprocess", "music_cover"]
            or target_model.startswith("speech-")
            or "music" in target_model
        )

        if is_custom:
            res = await self.execute(model_config, api_key, prompt, messages, options)
            yield json.dumps(res.model_dump(), ensure_ascii=False)
            return

        if "base_url" not in options:
            options["base_url"] = "https://api.minimaxi.com/v1"
        async for chunk in super().execute_stream(model_config, api_key, prompt, messages, options):
            yield chunk

    # --- Helper: File Upload ---
    async def _upload_file(self, api_key: str, purpose: str, file_source: Any) -> str:
        """
        Uploads a file to MiniMax files upload API.
        file_source can be a file path (str), file bytes (bytes), or file-like object.
        """
        url = "https://api.minimaxi.com/v1/files/upload"
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "purpose": purpose
        }

        async def perform_post(files_dict):
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers=headers, data=data, files=files_dict)
            if resp.status_code != 200:
                raise Exception(f"MiniMax file upload failed ({resp.status_code}): {resp.text}")
            res_json = resp.json()
            if "file" not in res_json or "file_id" not in res_json["file"]:
                raise Exception(f"MiniMax upload response missing file_id: {res_json}")
            return str(res_json["file"]["file_id"])

        if isinstance(file_source, str):
            filename = os.path.basename(file_source)
            with open(file_source, "rb") as f:
                return await perform_post({"file": (filename, f, "application/octet-stream")})
        elif isinstance(file_source, bytes):
            import io
            filename = f"upload_{purpose}.mp3"
            return await perform_post({"file": (filename, io.BytesIO(file_source), "application/octet-stream")})
        else:
            filename = getattr(file_source, "name", f"upload_{purpose}.mp3")
            return await perform_post({"file": (filename, file_source, "application/octet-stream")})

    # --- Capability 1: Synchronous TTS ---
    async def _execute_tts(
        self, model_config: ModelInfo, api_key: str, prompt: str, options: Dict[str, Any]
    ) -> ExecutionResult:
        url = "https://api.minimaxi.com/v1/t2a_v2"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Build voice setting
        voice_opt = options.get("voice_setting") or {}
        voice_id = options.get("voice_id") or voice_opt.get("voice_id") or "male-qn-qingse"
        speed = int(options.get("speed") or voice_opt.get("speed") or 1)
        vol = int(options.get("vol") or voice_opt.get("vol") or 1)
        pitch = int(options.get("pitch") or voice_opt.get("pitch") or 0)
        english_normalization = bool(options.get("english_normalization") or voice_opt.get("english_normalization") or False)

        voice_setting = {
            "voice_id": voice_id,
            "speed": speed,
            "vol": vol,
            "pitch": pitch,
            "english_normalization": english_normalization
        }

        # Build audio setting
        audio_opt = options.get("audio_setting") or {}
        sample_rate = int(options.get("sample_rate") or audio_opt.get("sample_rate") or 32000)
        bitrate = int(options.get("bitrate") or audio_opt.get("bitrate") or 128000)
        file_format = str(options.get("format") or audio_opt.get("format") or "mp3")
        channel = int(options.get("channel") or audio_opt.get("channel") or 1)

        audio_setting = {
            "sample_rate": sample_rate,
            "bitrate": bitrate,
            "format": file_format,
            "channel": channel
        }

        output_format = options.get("output_format") or "hex"

        payload = {
            "model": model_config.target_model_id,
            "text": prompt,
            "voice_setting": voice_setting,
            "audio_setting": audio_setting,
            "output_format": output_format
        }

        logger.info(f"[MiniMax TTS] Request: {json.dumps(self.sanitize_payload(payload), ensure_ascii=False)}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code != 200:
            raise Exception(f"MiniMax TTS failed ({resp.status_code}): {resp.text}")

        res_json = resp.json()
        if "base_resp" in res_json and res_json["base_resp"].get("status_code", 0) != 0:
            raise Exception(f"MiniMax TTS error: {res_json['base_resp'].get('status_msg')}")

        audio_val = res_json.get("data", {}).get("audio", "")
        if not audio_val:
            raise Exception(f"MiniMax TTS returned no audio data: {res_json}")

        if output_format == "hex":
            audio_bytes = bytes.fromhex(audio_val)
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            asset_uri = f"data:audio/{file_format};base64,{audio_b64}"
            return ExecutionResult(assets=[asset_uri], usage={"input": len(prompt), "output": len(audio_bytes)})
        else:
            return ExecutionResult(assets=[audio_val], usage={"input": len(prompt), "output": 0})

    # --- Capability 2: Asynchronous TTS ---
    async def _execute_async_tts(
        self, model_config: ModelInfo, api_key: str, prompt: str, options: Dict[str, Any]
    ) -> ExecutionResult:
        create_url = "https://api.minimaxi.com/v1/t2a_async_v2"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Resolve input: text_file_id or prompt text
        text_file_id = options.get("text_file_id")
        file_path = options.get("file_path")
        file_bytes = options.get("file_bytes")
        file_source = file_path or file_bytes

        if not text_file_id and file_source:
            logger.info("[MiniMax Async TTS] Uploading source file...")
            text_file_id = await self._upload_file(api_key, "t2a_async_input", file_source)

        voice_opt = options.get("voice_setting") or {}
        voice_id = options.get("voice_id") or voice_opt.get("voice_id") or "audiobook_male_1"
        speed = float(options.get("speed") or voice_opt.get("speed") or 1.1)
        vol = int(options.get("vol") or voice_opt.get("vol") or 10)
        pitch = int(options.get("pitch") or voice_opt.get("pitch") or 1)

        voice_setting = {
            "voice_id": voice_id,
            "speed": speed,
            "vol": vol,
            "pitch": pitch
        }

        audio_opt = options.get("audio_setting") or {}
        sample_rate = int(options.get("audio_sample_rate") or audio_opt.get("audio_sample_rate") or 32000)
        bitrate = int(options.get("bitrate") or audio_opt.get("bitrate") or 128000)
        file_format = str(options.get("format") or audio_opt.get("format") or "mp3")
        channel = int(options.get("channel") or audio_opt.get("channel") or 2)

        audio_setting = {
            "audio_sample_rate": sample_rate,
            "bitrate": bitrate,
            "format": file_format,
            "channel": channel
        }

        payload = {
            "model": model_config.target_model_id or "speech-2.8-hd",
            "voice_setting": voice_setting,
            "audio_setting": audio_setting
        }

        if text_file_id:
            payload["text_file_id"] = text_file_id
        else:
            payload["text"] = prompt

        for key in ["language_boost", "pronunciation_dict", "voice_modify"]:
            if options.get(key):
                payload[key] = options[key]

        logger.info(f"[MiniMax Async TTS] Creating task: {json.dumps(self.sanitize_payload(payload), ensure_ascii=False)}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(create_url, headers=headers, json=payload)

        if resp.status_code != 200:
            raise Exception(f"MiniMax async TTS task creation failed ({resp.status_code}): {resp.text}")

        res_json = resp.json()
        if "base_resp" in res_json and res_json["base_resp"].get("status_code", 0) != 0:
            raise Exception(f"MiniMax async TTS task creation error: {res_json['base_resp'].get('status_msg')}")

        task_id = res_json.get("task_id")
        if not task_id:
            raise Exception(f"MiniMax async TTS returned no task_id: {res_json}")

        poll = options.get("poll", True)
        if not poll:
            return ExecutionResult(content=task_id, usage={"input": len(prompt) if not text_file_id else 0, "output": 0})

        # Polling
        logger.info(f"[MiniMax Async TTS] Polling status for task {task_id}...")
        query_url = f"https://api.minimaxi.com/v1/query/t2a_async_query_v2?task_id={task_id}"
        query_headers = {
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json"
        }

        status = "preparing"
        result_file_id = None
        max_attempts = options.get("max_attempts", 60)
        interval = options.get("poll_interval", 5)

        for attempt in range(max_attempts):
            await asyncio.sleep(interval)
            async with httpx.AsyncClient(timeout=30.0) as client:
                query_resp = await client.get(query_url, headers=query_headers)

            if query_resp.status_code != 200:
                logger.warning(f"[MiniMax Async TTS] Query status request failed: {query_resp.text}")
                continue

            query_json = query_resp.json()
            if "base_resp" in query_json and query_json["base_resp"].get("status_code", 0) != 0:
                raise Exception(f"MiniMax async TTS status query error: {query_json['base_resp'].get('status_msg')}")

            status = query_json.get("status", "preparing")
            logger.info(f"[MiniMax Async TTS] Task {task_id} status: {status} (attempt {attempt + 1}/{max_attempts})")

            if status == "success":
                result_file_id = query_json.get("file_id")
                break
            elif status == "fail":
                raise Exception(f"MiniMax async TTS task failed: {query_json}")

        if status != "success" or not result_file_id:
            raise Exception(f"MiniMax async TTS task timed out or failed with status '{status}'")

        # Retrieve/Download content
        logger.info(f"[MiniMax Async TTS] Task complete. Downloading result file {result_file_id}...")
        download_url = f"https://api.minimaxi.com/v1/files/retrieve_content?file_id={result_file_id}"
        download_headers = {
            "Authorization": f"Bearer {api_key}"
        }

        async with httpx.AsyncClient(timeout=180.0) as client:
            file_resp = await client.get(download_url, headers=download_headers)

        if file_resp.status_code != 200:
            raise Exception(f"MiniMax async TTS download failed ({file_resp.status_code}): {file_resp.text}")

        audio_bytes = file_resp.content
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        asset_uri = f"data:audio/{file_format};base64,{audio_b64}"

        return ExecutionResult(
            content=task_id,
            assets=[asset_uri],
            usage={"input": len(prompt) if not text_file_id else 0, "output": len(audio_bytes)}
        )

    # --- Capability 3: Voice Cloning ---
    async def _execute_voice_clone(
        self, model_config: ModelInfo, api_key: str, prompt: str, options: Dict[str, Any]
    ) -> ExecutionResult:
        clone_url = "https://api.minimaxi.com/v1/voice_clone"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        clone_file = options.get("clone_file") or options.get("clone_file_path")
        if not clone_file:
            raise ValueError("voice_clone requires 'clone_file' (path or bytes)")

        # Upload clone audio
        logger.info("[MiniMax Voice Clone] Uploading clone reference audio...")
        file_id = await self._upload_file(api_key, "voice_clone", clone_file)

        # Upload prompt audio if provided
        prompt_file = options.get("prompt_file") or options.get("prompt_file_path")
        prompt_file_id = None
        if prompt_file:
            logger.info("[MiniMax Voice Clone] Uploading prompt audio...")
            prompt_file_id = await self._upload_file(api_key, "prompt_audio", prompt_file)

        # Unique voice id
        voice_id = options.get("voice_id") or f"clone_{uuid.uuid4().hex[:8]}"

        payload = {
            "file_id": file_id,
            "voice_id": voice_id,
            "model": model_config.target_model_id or "speech-2.8-hd"
        }

        if prompt_file_id:
            payload["clone_prompt"] = {
                "prompt_audio": prompt_file_id,
                "prompt_text": options.get("prompt_text") or ""
            }

        # Preview text to generate audio demo
        preview_text = prompt or options.get("text")
        if preview_text:
            payload["text"] = preview_text

        logger.info(f"[MiniMax Voice Clone] Submitting clone request: {json.dumps(self.sanitize_payload(payload), ensure_ascii=False)}")

        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(clone_url, headers=headers, json=payload)

        if resp.status_code != 200:
            raise Exception(f"MiniMax Voice Clone failed ({resp.status_code}): {resp.text}")

        res_json = resp.json()
        if "base_resp" in res_json and res_json["base_resp"].get("status_code", 0) != 0:
            raise Exception(f"MiniMax Voice Clone error: {res_json['base_resp'].get('status_msg')}")

        demo_audio = res_json.get("demo_audio") or res_json.get("demo_audio_url") or ""
        assets = []
        if demo_audio:
            if demo_audio.startswith(("http://", "https://")):
                assets.append(demo_audio)
            else:
                try:
                    # If it's a hex string
                    audio_bytes = bytes.fromhex(demo_audio)
                    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                    assets.append(f"data:audio/mp3;base64,{audio_b64}")
                except Exception:
                    assets.append(demo_audio)

        return ExecutionResult(
            content=voice_id,
            assets=assets,
            usage={"input": len(preview_text) if preview_text else 0, "output": 0}
        )

    # --- Capability 4: Music / Lyrics / Cover Generation ---
    async def _execute_lyrics(
        self, model_config: ModelInfo, api_key: str, prompt: str, options: Dict[str, Any]
    ) -> ExecutionResult:
        url = "https://api.minimaxi.com/v1/lyrics_generation"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "mode": options.get("mode") or "write_full_song",
            "prompt": prompt
        }

        logger.info(f"[MiniMax Lyrics] Request: {json.dumps(self.sanitize_payload(payload), ensure_ascii=False)}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code != 200:
            raise Exception(f"MiniMax Lyrics generation failed ({resp.status_code}): {resp.text}")

        res_json = resp.json()
        if "base_resp" in res_json and res_json["base_resp"].get("status_code", 0) != 0:
            raise Exception(f"MiniMax Lyrics error: {res_json['base_resp'].get('status_msg')}")

        lyrics = res_json.get("lyrics", "")
        return ExecutionResult(content=lyrics, usage={"input": len(prompt), "output": len(lyrics)})

    async def _execute_music(
        self, model_config: ModelInfo, api_key: str, prompt: str, options: Dict[str, Any]
    ) -> ExecutionResult:
        url = "https://api.minimaxi.com/v1/music_generation"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model_config.target_model_id or "music-2.6",
            "prompt": prompt,
            "output_format": options.get("output_format", "url")
        }

        # For Cover mode, we might pass cover_feature_id / audio_url / audio_base64
        for k in ["lyrics", "lyrics_optimizer", "is_instrumental", "audio_setting", "cover_feature_id", "audio_url", "audio_base64"]:
            if options.get(k) is not None:
                payload[k] = options[k]

        logger.info(f"[MiniMax Music] Request: {json.dumps(self.sanitize_payload(payload), ensure_ascii=False)}")

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code != 200:
            raise Exception(f"MiniMax Music generation failed ({resp.status_code}): {resp.text}")

        res_json = resp.json()
        if "base_resp" in res_json and res_json["base_resp"].get("status_code", 0) != 0:
            raise Exception(f"MiniMax Music error: {res_json['base_resp'].get('status_msg')}")

        # Try to retrieve url or hex
        audio_val = res_json.get("data", {}).get("audio", "") or res_json.get("music_url") or ""
        if not audio_val:
            # Check other possible locations
            audio_val = res_json.get("audio_url") or ""

        if not audio_val:
            raise Exception(f"MiniMax Music generation returned no audio field: {res_json}")

        if payload["output_format"] == "hex" and not audio_val.startswith("http"):
            try:
                audio_bytes = bytes.fromhex(audio_val)
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                # Default format is mp3
                fmt = payload.get("audio_setting", {}).get("format", "mp3")
                asset_uri = f"data:audio/{fmt};base64,{audio_b64}"
                return ExecutionResult(assets=[asset_uri])
            except Exception:
                pass

        return ExecutionResult(assets=[audio_val])

    async def _execute_cover_preprocess(
        self, model_config: ModelInfo, api_key: str, prompt: str, options: Dict[str, Any]
    ) -> ExecutionResult:
        url = "https://api.minimaxi.com/v1/music_cover_preprocess"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "music-cover",
            "audio_url": options.get("audio_url")
        }
        if options.get("audio_base64"):
            payload["audio_base64"] = options["audio_base64"]

        logger.info(f"[MiniMax Cover Preprocess] Request: {json.dumps(self.sanitize_payload(payload), ensure_ascii=False)}")

        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(url, headers=headers, json=payload)

        if resp.status_code != 200:
            raise Exception(f"MiniMax Cover Preprocess failed ({resp.status_code}): {resp.text}")

        res_json = resp.json()
        if "base_resp" in res_json and res_json["base_resp"].get("status_code", 0) != 0:
            raise Exception(f"MiniMax Cover Preprocess error: {res_json['base_resp'].get('status_msg')}")

        # Return structural data in content as JSON
        content_data = {
            "cover_feature_id": res_json.get("cover_feature_id"),
            "formatted_lyrics": res_json.get("formatted_lyrics"),
            "structure_result": res_json.get("structure_result"),
            "audio_duration": res_json.get("audio_duration")
        }

        return ExecutionResult(content=json.dumps(content_data, ensure_ascii=False))
