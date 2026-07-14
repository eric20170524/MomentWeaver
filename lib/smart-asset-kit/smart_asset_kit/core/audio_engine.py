import asyncio
import io
import math
import os
from typing import List, Optional
from rich.progress import Progress, SpinnerColumn, TextColumn
from smart_asset_kit.llm.client import AIClient
from pydub import AudioSegment

class AudioEngine:
    def __init__(self, client: AIClient):
        self.client = client

    async def local_say(self, text: str, voice: str = "Grandpa") -> bytes:
        """Fallback to macOS native 'say' command."""
        import subprocess
        import tempfile
        import os
        from pydub import AudioSegment
        
        temp_dir = tempfile.gettempdir()
        tmp_aiff = os.path.join(temp_dir, f"say_{os.getpid()}.aiff")
        tmp_mp3 = os.path.join(temp_dir, f"say_{os.getpid()}.mp3")
        
        try:
            # 1. Generate via macOS say
            subprocess.run(["say", "-v", voice, text, "-o", tmp_aiff], check=True)
            # 2. Convert to MP3 using pydub
            sound = AudioSegment.from_file(tmp_aiff, format="aiff")
            out = io.BytesIO()
            sound.export(out, format="mp3", bitrate="192k")
            return out.getvalue()
        except Exception as e:
            raise Exception(f"Local say failed: {e}")
        finally:
            if os.path.exists(tmp_aiff): os.remove(tmp_aiff)
            if os.path.exists(tmp_mp3): os.remove(tmp_mp3)

    async def add_voice(self, name: str, file_path: str, description: str = "") -> str:
        """Add a new voice for Instant Voice Cloning (ElevenLabs / MiniMax)."""
        if self.client.provider_name not in ["eleven", "minimax"]:
            raise Exception("Voice cloning is only supported with 'eleven' or 'minimax' provider.")
            
        if self.client.provider_name == "minimax":
            try:
                res = await self.client.generate_asset(
                    prompt=description or "大兄弟，听您口音不是本地人吧，头回来天津卫，啊，待会您可甭跟着导航走，那玩意儿净给您往大马路上绕。",
                    clone_file=file_path,
                    voice_id=name,
                    type="voice_clone"
                )
                return res.content
            except Exception as e:
                raise Exception(f"MiniMax voice cloning error: {e}")

        import httpx
        url = "https://api.elevenlabs.io/v1/voices/add"
        headers = {
            "xi-api-key": self.client.api_key
        }
        
        try:
            with open(file_path, "rb") as f:
                files = {
                    "files": (os.path.basename(file_path), f, "audio/wav")
                }
                data = {
                    "name": name,
                    "description": description
                }
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(url, headers=headers, data=data, files=files)
                    if resp.status_code != 200:
                        raise Exception(f"Failed to add voice: {resp.text}")
                    
                    result = resp.json()
                    return result.get("voice_id")
        except Exception as e:
            raise Exception(f"Voice cloning error: {e}")

    async def generate_tts(self, text: str, voice: str = "ara", options: dict = None) -> str:
        """Generate Text-to-Speech audio."""
        if options is None:
            options = {}
            
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description=f"Generating voice {voice}...", total=None)
            
            try:
                # If it's ElevenLabs, we might want to map some names to voice_ids
                if self.client.provider_name == "eleven":
                    # Mapping known labels to IDs for convenience
                    mapping = {
                        "Rachel": "21m00Tcm4TlvDq8ikWAM",
                        "Bella": "EXAVITQu4vr4xnSDxMaL",
                        "Charlotte": "XB0fDUnXU5ywg46cPtcg",
                        "Drew": "29vD33N1CtxCmqQRPOZB"
                    }
                    if voice in mapping:
                        options["voice_id"] = mapping[voice]
                    elif not options.get("voice_id"):
                        options["voice_id"] = voice # Assume the voice string IS the ID
                elif self.client.provider_name == "minimax":
                    mapping = {
                        "Qingse": "male-qn-qingse",
                        "Jingying": "male-qn-jingying",
                        "Shaonv": "female-shaonv",
                        "Yujie": "female-yujie",
                        "Tianmei": "female-tianmei"
                    }
                    if voice in mapping:
                        options["voice_id"] = mapping[voice]
                    elif not options.get("voice_id"):
                        options["voice_id"] = voice
                
                if "voice" not in options:
                    options["voice"] = voice
                
                result = await self.client.generate_asset(text, **options)
                
                if result.assets and len(result.assets) > 0:
                    return result.assets[0]
                return result.content
            except Exception as e:
                raise Exception(f"Audio generation failed: {e}")

    def create_seamless_loop(self, audio_data: bytes, format: str = "mp3", crossfade_ms: int = 1000) -> bytes:
        """Create a seamless loop using zero-crossing and crossfade."""
        try:
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format=format)
            if len(audio) < crossfade_ms * 2:
                return audio_data # Too short to crossfade safely
                
            # Create a crossfade between start and end
            beginning = audio[:crossfade_ms]
            ending = audio[-crossfade_ms:]
            
            seamless = audio[:-crossfade_ms].append(beginning, crossfade=crossfade_ms)
            
            out = io.BytesIO()
            seamless.export(out, format=format)
            return out.getvalue()
        except Exception as e:
            raise Exception(f"Failed to create seamless loop: {e}")
