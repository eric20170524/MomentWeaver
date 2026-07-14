import asyncio
from PySide6.QtCore import QThread, Signal
from smart_asset_kit.llm.client import AIClient
from smart_asset_kit.core.image_engine import ImageEngine
from smart_asset_kit.core.video_engine import VideoEngine
from smart_asset_kit.core.audio_engine import AudioEngine

class GenWorker(QThread):
    finished_task = Signal(list)  # Signal list of urls or data uris
    error_task = Signal(str)

    def __init__(self, task_type: str, prompt: str, **kwargs):
        super().__init__()
        self.task_type = task_type
        self.prompt = prompt
        self.kwargs = kwargs

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(self.run_async_gen())
            loop.close()
            self.finished_task.emit(results)
        except Exception as e:
            self.error_task.emit(str(e))

    async def run_async_gen(self):
        if self.task_type == "image":
            client = AIClient(model_type="image", target_model=self.kwargs.get("model"))
            engine = ImageEngine(client)
            batch = self.kwargs.get("batch", 1)
            states = self.kwargs.get("states")
            
            if states:
                state_list = [s.strip() for s in states.split(",")]
                res_dict = await engine.generate_states(self.prompt, state_list)
                results = [url for url in res_dict.values()]
            else:
                results = await engine.generate_batch(self.prompt, n=batch, auto_enhance=self.kwargs.get("auto_enhance", False))
                
            do_pbr = self.kwargs.get("pbr", False)
            do_seamless = self.kwargs.get("seamless", False)
            do_remove_bg = self.kwargs.get("remove_bg", False)
            
            if do_pbr or do_seamless or do_remove_bg:
                from smart_asset_kit.utils.texture_ops import make_seamless_blend, generate_normal_map, generate_roughness_map, remove_black_background
                from PIL import Image
                import io
                import base64
                
                final_results = []
                for res in results:
                    b64_data = res.split(",")[1] if "," in res else res
                    img_bytes = base64.b64decode(b64_data)
                    img = Image.open(io.BytesIO(img_bytes))
                    
                    if do_remove_bg:
                        img = remove_black_background(img)
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        res = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")
                        
                    if do_seamless:
                        img = make_seamless_blend(img)
                        # save seamless as main image
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        res = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")
                        
                    final_results.append(res) # Primary image (Albedo)
                    
                    if do_pbr:
                        normal_img = generate_normal_map(img)
                        buf_n = io.BytesIO()
                        normal_img.save(buf_n, format="PNG")
                        res_n = "data:image/png;pbr_type=normal;base64," + base64.b64encode(buf_n.getvalue()).decode("utf-8")
                        final_results.append(res_n)
                        
                        rough_img = generate_roughness_map(img)
                        buf_r = io.BytesIO()
                        rough_img.save(buf_r, format="PNG")
                        res_r = "data:image/png;pbr_type=roughness;base64," + base64.b64encode(buf_r.getvalue()).decode("utf-8")
                        final_results.append(res_r)
                return final_results
            return results
                
        elif self.task_type == "video":
            client = AIClient(model_type="video", target_model=self.kwargs.get("model"))
            engine = VideoEngine(client)
            opts = {}
            if self.kwargs.get("image"):
                opts["images"] = [self.kwargs.get("image")]
            return await engine.generate_vfx(self.prompt, options=opts)
            
        elif self.task_type == "audio":
            client = AIClient(model_type="audio", target_model=self.kwargs.get("model"))
            engine = AudioEngine(client)
            aud_type = self.kwargs.get("aud_type", "tts")
            
            if aud_type == "apple_say":
                voice_raw = self.kwargs.get("voice", "Flo")
                voice = voice_raw.split("】")[-1].strip() if "】" in voice_raw else voice_raw
                import subprocess
                import tempfile
                import os
                import base64
                from pydub import AudioSegment
                
                # Use a temp directory for safe intermediate files
                temp_dir = tempfile.gettempdir()
                tmp_aiff = os.path.join(temp_dir, f"temp_{os.getpid()}.aiff")
                tmp_mp3 = os.path.join(temp_dir, f"temp_{os.getpid()}.mp3")
                
                try:
                    # 1. Generate via macOS say
                    subprocess.run(["say", "-v", voice, self.prompt, "-o", tmp_aiff], check=True)
                    # 2. Convert to MP3
                    sound = AudioSegment.from_file(tmp_aiff, format="aiff")
                    sound.export(tmp_mp3, format="mp3", bitrate="192k")
                    # 3. Read data
                    with open(tmp_mp3, "rb") as f:
                        b64_data = base64.b64encode(f.read()).decode("utf-8")
                        
                    res = f"data:audio/mp3;base64,{b64_data}"
                    return [res]
                finally:
                    # Clean up
                    if os.path.exists(tmp_aiff): os.remove(tmp_aiff)
                    if os.path.exists(tmp_mp3): os.remove(tmp_mp3)

            elif aud_type == "tts":
                voice_label = self.kwargs.get("voice", "")
                prefix = ""
                if "甜美" in voice_label or "娇柔" in voice_label: 
                    prefix = "请用非常甜美、清澈、娇柔的中国女声朗读："
                    fallback_voice = "nova"
                elif "性感" in voice_label or "诱惑" in voice_label: 
                    prefix = "请用成熟、性感的中国女声，带一点诱惑的语气朗读："
                    fallback_voice = "nova"
                elif "清冷" in voice_label or "孤傲" in voice_label: 
                    prefix = "请用清脆、空灵、不带口音的中国女声朗读："
                    fallback_voice = "shimmer"
                elif "低沉" in voice_label or "霸气" in voice_label: 
                    prefix = "请用低沉、冷艳、带点御姐气息的中国女声朗读："
                    fallback_voice = "alloy"
                else:
                    fallback_voice = "nova"
                    
                final_prompt = f"{prefix}{self.prompt}" if prefix else self.prompt
                res = await engine.generate_tts(final_prompt, voice=fallback_voice)
                return [res]
            elif aud_type == "pixabay":
                # Translate to English keywords via LLM
                from smart_asset_kit.core.config import load_config
                # Need to explicitly use text type model
                cfg = load_config()
                client_text = AIClient(model_type="text", provider=cfg.provider) 
                prompt = f"Extract the core search keywords from the following text and translate them into English keywords separated by space (max 4 words). Do not include any other text or punctuation. Text: {self.prompt}"
                translated = ""
                try:
                    result = await client_text.generate_asset(prompt)
                    translated = result.content.strip().lower()
                except Exception as e:
                    # fallback if LLM fails
                    translated = "bamboo forest" 
                
                # Sanitize response
                translated = translated.replace('"', '').replace('.', '').replace(',', '')
                import urllib.parse
                safe_kw = urllib.parse.quote(translated)
                
                target = self.kwargs.get("pixabay_target", "music")
                url = f"https://pixabay.com/{target}/search/{safe_kw}/"
                
                return [f"action:open_url:{url}|keyword:{translated}"]
            elif aud_type == "eleven_tts" or aud_type == "eleven_sfx":
                import requests
                import base64
                from smart_asset_kit.core.config import load_config
                cfg = load_config()
                if not cfg.eleven_api_key:
                    raise ValueError("未配置 ElevenLabs API Key，请在【⚙️ 基础配置】中填写。")
                    
                headers = {
                    "xi-api-key": cfg.eleven_api_key,
                    "Content-Type": "application/json"
                }
                
                if aud_type == "eleven_tts":
                    voice_label = self.kwargs.get("voice", "")
                    # Default to Rachel if not matched
                    voice_id = "21m00Tcm4TlvDq8ikWAM"
                    if "Bella" in voice_label: voice_id = "EXAVITQu4vr4xnSDxMaL"
                    elif "Charlotte" in voice_label: voice_id = "XB0fDUnXU5ywg46cPtcg"
                    elif "Drew" in voice_label: voice_id = "29vD33N1CtxCmqQRPOZB"
                    
                    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                    data = {
                        "text": self.prompt,
                        "model_id": "eleven_multilingual_v2",
                        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                    }
                    resp = requests.post(url, headers=headers, json=data)
                    if resp.status_code != 200:
                        raise Exception(f"ElevenLabs TTS 失败: {resp.text}")
                    audio_bytes = resp.content
                else: # eleven_sfx
                    url = "https://api.elevenlabs.io/v1/sound-generation"
                    data = {
                        "text": self.prompt,
                        "duration_seconds": 10 # Default duration for BGM/Ambient
                    }
                    resp = requests.post(url, headers=headers, json=data)
                    if resp.status_code != 200:
                        raise Exception(f"ElevenLabs SFX 失败: 请确保你的账号权限开通了 Sound Generation，详情: {resp.text}")
                    audio_bytes = resp.content
                    
                if self.kwargs.get("seamless"):
                    import io
                    buf_temp = io.BytesIO(audio_bytes)
                    from pydub import AudioSegment
                    # ElevenLabs returns MP3 by default
                    mixed = AudioSegment.from_file(buf_temp, format="mp3")
                    buf_wav = io.BytesIO()
                    mixed.export(buf_wav, format="wav")
                    looped_bytes = engine.create_seamless_loop(buf_wav.getvalue(), format="wav", crossfade_ms=1000)
                    audio_bytes = looped_bytes
                    
                b64_data = base64.b64encode(audio_bytes).decode('utf-8')
                res = f"data:audio/mp3;base64,{b64_data}"
                return [res]
            elif aud_type in ["minimax_tts", "minimax_bgm", "minimax_sfx"]:
                from smart_asset_kit.core.config import load_config
                cfg = load_config()
                if not cfg.minimax_api_key:
                    raise ValueError("未配置 MiniMax API Key，请在【⚙️ 基础配置】中填写。")
                
                client_minimax = AIClient(model_type="audio", provider="minimax", api_key=cfg.minimax_api_key)
                
                if aud_type == "minimax_tts":
                    voice_label = self.kwargs.get("voice", "")
                    voice_id = "male-qn-qingse"
                    if "Qingse" in voice_label or "青涩" in voice_label:
                        voice_id = "male-qn-qingse"
                    elif "Jingying" in voice_label or "精英" in voice_label:
                        voice_id = "male-qn-jingying"
                    elif "Shaonv" in voice_label or "少女" in voice_label:
                        voice_id = "female-shaonv"
                    elif "Yujie" in voice_label or "御姐" in voice_label:
                        voice_id = "female-yujie"
                    elif "Tianmei" in voice_label or "甜美" in voice_label:
                        voice_id = "female-tianmei"
                    elif "】" in voice_label:
                        voice_id = voice_label.split("】")[-1].strip()
                    else:
                        voice_id = voice_label or "male-qn-qingse"
                        
                    res_obj = await client_minimax.generate_asset(
                        self.prompt,
                        type="audio",
                        voice_id=voice_id,
                        output_format="hex"
                    )
                    return [res_obj.assets[0]]
                else: # minimax_bgm or minimax_sfx
                    options = {
                        "type": "music",
                        "output_format": "url"
                    }
                    if "bgm" in aud_type:
                        options["is_instrumental"] = True
                    else:
                        options["lyrics_optimizer"] = True
                    
                    res_obj = await client_minimax.generate_asset(
                        self.prompt,
                        **options
                    )
                    
                    audio_res = res_obj.assets[0]
                    
                    if self.kwargs.get("seamless") and audio_res.startswith("http"):
                        # Download and seamless loop if needed
                        import requests
                        import io
                        from pydub import AudioSegment
                        self.log.emit(f"📥 正在下载背景音乐用于无缝混音...")
                        resp = requests.get(audio_res)
                        resp.raise_for_status()
                        
                        looped_bytes = engine.create_seamless_loop(resp.content, format="mp3", crossfade_ms=1000)
                        b64_data = base64.b64encode(looped_bytes).decode('utf-8')
                        audio_res = f"data:audio/mp3;base64,{b64_data}"
                        
                    return [audio_res]
            else:
                # BGM / SFX Generation
                # ❗️ Gemini 2.5 Flash / Grok Audio 目前只支持 Text-to-Speech (文本转语音说话)。
                # 它们无法根据文本生成纯音乐或环境音 (需要 Suno/Udio/MusicGen 类专用模型)。
                # 如果强行调用 tts 接口，大模型会直接把“宁静的古筝”这句话用人声读出来。
                # 由于这是当前可用模型的接口物理限制，我们在这里进行异常拦截，并生成一个纯本地合成的氛围音作为 Placeholder 演示。
                
                import base64
                from pydub import AudioSegment
                from pydub.generators import Sine
                import io
                
                # 模拟生成一个 10 秒的空灵氛围音 (环境白噪音+低频)
                tone1 = Sine(432).to_audio_segment(duration=10000).apply_gain(-20)
                tone2 = Sine(436).to_audio_segment(duration=10000).apply_gain(-25)
                mixed = tone1.overlay(tone2)
                
                # 添加一点点淡入淡出模拟环境音
                mixed = mixed.fade_in(2000).fade_out(2000)
                
                # 如果勾选了无缝循环，调用我们的引擎后处理
                if self.kwargs.get("seamless"):
                    import tempfile
                    import os
                    buf_temp = io.BytesIO()
                    mixed.export(buf_temp, format="wav")
                    looped_bytes = engine.create_seamless_loop(buf_temp.getvalue(), format="wav", crossfade_ms=1000)
                    
                    # 重新包裹为 mp3 base64 以兼容后续处理
                    # looped_bytes is already MP3 data from create_seamless_loop
                    res_bytes = looped_bytes
                else:
                    buf = io.BytesIO()
                    mixed.export(buf, format="mp3", bitrate="192k")
                    res_bytes = buf.getvalue()
                    
                b64_data = base64.b64encode(res_bytes).decode('utf-8')
                res = f"data:audio/mp3;base64,{b64_data}"
                
                return [res]
        
        elif self.task_type == "asset_search":
            from smart_asset_kit.core.asset_search import (
                build_asset_search_results,
                extract_keywords,
                filter_sources,
            )

            target = self.kwargs.get("target", "sprites")
            source = self.kwargs.get("source", "all")
            deep = self.kwargs.get("deep", False)

            if deep:
                from smart_asset_kit.core.asset_scorer import search_and_rank_assets
                src_filter = "all"
                if source in ["kenney", "opengameart"]:
                    src_filter = source
                
                keywords = await extract_keywords(self.prompt, keyword=self.kwargs.get("keyword"))
                ranked_results = await search_and_rank_assets(
                    self.prompt,
                    source=src_filter,
                    provider=self.kwargs.get("provider"),
                    query=keywords,
                )
                
                actions = []
                import urllib.parse
                for result in ranked_results:
                    safe_title = urllib.parse.quote(result.title)
                    safe_desc = urllib.parse.quote(result.description)
                    safe_reason = urllib.parse.quote(result.reason)
                    safe_license = urllib.parse.quote(result.license)
                    safe_preview = urllib.parse.quote(result.preview_url or "")
                    safe_downloads = urllib.parse.quote(",".join(result.download_urls))
                    
                    actions.append(
                        f"action:scraped_asset:{result.url}|title:{safe_title}|source:{result.source}"
                        f"|desc:{safe_desc}|license:{safe_license}|score:{result.score}"
                        f"|reason:{safe_reason}|preview:{safe_preview}|downloads:{safe_downloads}"
                    )
                return actions
            else:
                keywords = await extract_keywords(self.prompt, keyword=self.kwargs.get("keyword"))
                results = filter_sources(build_asset_search_results(keywords, target=target), source)
                if not results:
                    raise ValueError(f"未知素材来源: {source}")

                actions = []
                for idx, result in enumerate(results):
                    reasons = "; ".join(result.score_reasons or [])
                    actions.append(
                        "action:open_url:"
                        f"{result.url}|kind:asset_search|open:{1 if idx == 0 else 0}"
                        f"|keyword:{result.keywords}|source:{result.source}|target:{result.target}"
                        f"|license:{result.license_hint}|focus:{result.focus}|notes:{result.notes}"
                        f"|rank:{result.rank}|score:{result.score}"
                        f"|recommended:{1 if result.recommended else 0}|reasons:{reasons}"
                    )
                return actions

        else:
            raise ValueError(f"Unknown task type: {self.task_type}")


class DownloadWorker(QThread):
    finished_download = Signal(list)
    error_download = Signal(str)

    def __init__(self, asset_dict: dict, dest_dir: str):
        super().__init__()
        self.asset_dict = asset_dict
        self.dest_dir = dest_dir

    def run(self):
        try:
            from smart_asset_kit.core.asset_scorer import ScrapedAsset, download_asset

            items = self.asset_dict if isinstance(self.asset_dict, list) else [self.asset_dict]
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            downloaded_files = []
            for idx, item in enumerate(items, start=1):
                urls = [u.strip() for u in item["downloads"].split(",") if u.strip()]
                asset = ScrapedAsset(
                    title=item["title"],
                    url=item["url"],
                    source=item["source"],
                    description=item.get("desc", ""),
                    preview_url=item.get("preview", ""),
                    download_urls=urls,
                    license=item.get("license", ""),
                    score=float(item.get("score", 0.0) or 0.0),
                    reason=item.get("reason", ""),
                )
                target_dir = self.dest_dir
                if isinstance(self.asset_dict, list):
                    import re
                    import os
                    safe_title = re.sub(r"[^a-zA-Z0-9._-]+", "-", asset.title.lower()).strip("-._") or "asset"
                    target_dir = os.path.join(self.dest_dir, f"{idx:02d}-{asset.source}-{safe_title}")
                downloaded_files.extend(loop.run_until_complete(download_asset(asset, target_dir)))
            loop.close()
            self.finished_download.emit(downloaded_files)
        except Exception as e:
            self.error_download.emit(str(e))
