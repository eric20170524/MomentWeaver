# MomentWeaver 项目参考

## 目录

- [产品与能力边界](#产品与能力边界)
- [启动与页面入口](#启动与页面入口)
- [环境配置](#环境配置)
- [Visual Project Render API](#visual-project-render-api)
- [Smart Asset Kit BGM 与本机旁白](#smart-asset-kit-bgm-与本机旁白)
- [分段旁白同步](#分段旁白同步)
- [发布素材规范](#发布素材规范)
- [项目目录与验证入口](#项目目录与验证入口)

## 产品与能力边界

MomentWeaver（圈影）把朋友圈图片和文案转换为适合微视的短视频，并接收 `video-background-board` 的可视舞台/时间轴项目进行后端渲染。

核心流程：

```text
图片 / 文案 → 分镜与时间轴 → 画布预览 → BGM / 配音 → 后端渲染 MP4
```

当前模型能力只有：

| 能力 | 用途 | 配置位置 |
| --- | --- | --- |
| 文本大模型 | 生成分镜、标题、字幕、发布文案和初始音乐方向 | MomentWeaver `.env` 或设置界面 |
| BGM 音频生成 | 内置背景音乐 | Smart Asset Kit `.sak_config.json` |
| 本机中文 TTS | 外部课程/视频管线的配音与分段旁白 | `/Users/lm/pyProj/local-chinese-tts` |

不要假定系统具备以下能力：

- 不使用视觉模型理解图片内容，只把图片作为素材和尺寸传入。
- 不使用视频生成模型；MP4 由本机 `ffmpeg` 合成。
- BGM 提示词由本地规则从分镜生成，不额外调用 LLM。
- MomentWeaver 尚无内置旁白录制或配音界面；旁白由外部管线调用本机 `local-chinese-tts`。
- 不直接发布到微视，只准备本地交付文件。

## 启动与页面入口

基础启动：

```bash
cd MomentWeaver
python3 -m pip install -r requirements.txt
cp .env.example .env
./start.sh
```

需要合并版 React 编辑器时：

```bash
cd ../video-background-board
npm install
npm run build
cd ../MomentWeaver
./start.sh
```

当 `video-background-board/dist` 存在时，合并版编辑器是默认首页；不存在时回退到旧版静态前端。

```text
默认入口：http://127.0.0.1:8787
旧版入口：http://127.0.0.1:8787/legacy
```

可从应用设置面板编辑 `.env`。主机、端口、reload 和 Python runtime 变更需重启 `./start.sh`；Nebula 与 Smart Asset Kit 配置对新请求立即生效。

## 环境配置

没有 LLM key 时，系统使用本地分镜回退。启用文本规划器时配置：

```bash
NEBULA_API_KEY=...
NEBULA_PROVIDER=openai
NEBULA_MODEL=gpt-4o-mini
NEBULA_BASE_URL=
NEBULA_SDK_PATH=lib/nebula_llm_sdk
```

使用 OpenAI 兼容网关时：

```bash
NEBULA_BASE_URL=https://your-compatible-endpoint/v1
```

相对 SDK 路径从 `MomentWeaver/` 项目根目录解析。默认使用项目内已安装的 `lib/nebula_llm_sdk`，不要依赖外部源码检出目录。

配置 SAK 路径：

```bash
SMART_ASSET_KIT_PATH=lib/smart-asset-kit
SAK_PYTHON=python3
```

SAK 凭据保存在：

```text
MomentWeaver/lib/smart-asset-kit/.sak_config.json
```

此文件应保持私密且不从外部 SDK 目录复制。SAK 只负责 BGM。音频供应商配置示例：

- `provider=minimax`：配置 `minimax_api_key`、`minimax_audio_model`
- `provider=gemini`：配置 `gemini_api_key`、`gemini_audio_model`
- `provider=xai`：配置 `xai_api_key`、`xai_audio_model`

课程、解说或外部视频管线生成正式旁白时，启动独立的本机 TTS：

```bash
LOCAL_CHINESE_TTS_HOME=/Users/lm/pyProj/local-chinese-tts
cd "$LOCAL_CHINESE_TTS_HOME"
./start_local_tts.sh
```

使用 `http://127.0.0.1:8765/v1/audio/speech`，默认音色为完全离线的 `K01`。

## Visual Project Render API

接口：

```text
POST /api/visual-projects/render
GET  /api/visual-projects/{job_id}/status
```

请求结构：

```json
{
  "project": {
    "title": "可视编辑短视频",
    "description": "发布描述",
    "weishi_caption": "微视文案",
    "hashtags": ["可视编辑", "MomentWeaver"],
    "timelineDuration": 15,
    "canvas": {
      "width": 1920,
      "height": 1080,
      "aspect_ratio": "16:9"
    },
    "background": {},
    "elements": [],
    "source": "video-background-board"
  }
}
```

后端产物：

```text
storage/jobs/{job_id}/visual_project.json
storage/jobs/{job_id}/render_status.json
storage/jobs/{job_id}/plan.json
storage/jobs/{job_id}/videos/{job_id}_visual.mp4
storage/jobs/{job_id}/publish.json
```

正式交付 MP4 必须来自后端渲染器。浏览器录屏只能作为可选前端工具。

## Smart Asset Kit BGM 与本机旁白

默认 SAK 路径：

```text
MomentWeaver/lib/smart-asset-kit
```

可通过 `SMART_ASSET_KIT_PATH` 覆盖。当前 CLI 使用 `sak gen-audio`：

1. 生成分镜。
2. 根据分镜创建 BGM 提示词并搜索候选。
3. 下载或生成所选候选。
4. 音频成功后自动渲染带音乐 MP4。

正式旁白约定：

- 固定使用 `/Users/lm/pyProj/local-chinese-tts`，不要通过 SAK 生成旁白。
- 启动 `/Users/lm/pyProj/local-chinese-tts/start_local_tts.sh`，并检查本机服务可用。
- 调用 `http://127.0.0.1:8765/v1/audio/speech`；请求使用 OpenAI Speech 兼容的 `model`、`input`、`voice` 和 `response_format` 字段。
- 默认使用完全离线、低内存且响应快的 `K01`。使用 `K02`–`K04` 选择其他轻量本地说话人。
- 仅在用户要求最佳本地质量或更强表现力，且可接受较高内存和延迟时使用 `QF*`/`QM*`。
- 仅在用户明确选择在线神经音色时使用 `F*`/`M*`。
- 在音频 manifest 中记录 `provider=local-chinese-tts`、`tts_backend=local-chinese-tts`、具体 `voice` 和真实音频时长。
- 不回退到 macOS `say` 或其他 TTS 后端；服务或所需模型缺失时明确失败。

请求示例：

```bash
curl http://127.0.0.1:8765/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"local-chinese-tts","input":"这是 MomentWeaver 的本机旁白。","voice":"K01","response_format":"mp3"}' \
  --output narration.mp3
```

## 分段旁白同步

不要把一条长旁白覆盖在固定视觉时间轴上。按以下顺序处理：

1. 按场景或段落生成独立旁白。
2. 测量每段真实音频时长。
3. 将视觉段时长设为 `voice duration + pause`，同时满足最小场景时长。
4. 将 `voice_end` 与视觉段 `end` 分开，让画面在语音结束后短暂停留。
5. 按 ID 把旁白段与视觉音频段对应起来。

复用：

- `backend/app/voiceover_sync.py`
- `build_voiceover_timeline()`：创建基于实测时长的分段时间线。
- `sync_visual_project_to_voiceover()`：按 `VoiceoverSegmentDuration.id` 与 `VisualAudioSegment.id` 匹配并重定时 `VisualProject`。

此流程适用于 3–5 分钟解说、课程视频，以及所有字幕/场景必须与旁白同步的短视频。

## 发布素材规范

公开发布、宣发或正式交付必须包括：

1. 1080×1920、H.264/AAC 的竖版 MP4。
2. 4:3 横屏封面 JPEG 与 PNG。
3. 先说明主体、再给最强钩子的短标题。
4. 包含开场问题、核心卖点、可信证据和行动邀请的发布描述。
5. 数量克制的话题标签，优先产品名、品类和核心主题。
6. 有旁白时的逐段文稿、音色、真实时长和同步信息。

推荐目录：

```text
publish-assets/
  final-video.mp4
  cover-4x3.jpg
  cover-4x3.png
  PUBLISH_COPY.md
  narration.md
```

4:3 封面：

| 项目 | 要求 |
| --- | --- |
| 比例 | 固定 4:3 |
| 推荐尺寸 | 1600×1200；最低 1200×900 |
| 格式 | 发布用 JPEG，同时保留 PNG |
| 色彩 | sRGB |
| 安全区 | 关键内容距离四边至少 5% |
| 层级 | 产品名最大，核心钩子次之，版本/状态作为角标 |
| 缩略图 | 缩到约 320×240 仍能读出产品名与卖点 |
| 一致性 | 复用成片主视觉、品牌字体、色板与角色/场景资产 |
| 真实性 | 不宣传未实现功能，不伪造数据，不把 Demo 包装成商业发行 |
| 命名 | `<project>-cover-4x3.jpg` 和 `<project>-cover-4x3.png` |

封面需为 4:3 重新构图。不要拉伸竖版画面，不要直接截取带字幕的视频帧，不要用 16:9 截图代替。

交付检查：

- MP4 可正常播放，音轨可听，旁白清晰。
- JPEG 与 PNG 封面齐全，比例、尺寸、安全区和缩略图可读性合格。
- 标题包含产品名或内容主体，而非只描述制作过程。
- 描述先表达体验价值，再说明制作方式和质控证据。
- 所有最终文件路径已写入交接说明。

当前 Visual Project Render API 的稳定产物仍以 MP4 和 `publish.json` 为主。自动封面进入后端前，下游必须补齐 4:3 封面；没有封面不能标记为完成。

## 项目目录与验证入口

```text
MomentWeaver/
  backend/app/       FastAPI API、Nebula 规划器、SAK 适配器、ffmpeg 渲染器
  frontend/          旧版静态应用
  lib/               已安装的 Nebula SDK 与 Smart Asset Kit
  start.sh           默认启动器
  scripts/dev.sh     本地开发服务器
  storage/jobs/      上传素材、任务状态和渲染结果
  tests/             后端轻量测试
```

按改动范围选择验证：

```bash
python3 -m pytest tests/test_visual_project_contract.py
python3 -m pytest tests/test_canvas_render.py
python3 -m pytest tests/test_fallback_plan.py
python3 -m pytest tests/test_voiceover_sync.py
```

涉及兼容入口、SDK 发布包或完整 API 时，再运行对应测试或整个 `tests/`。
