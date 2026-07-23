---
name: momentweaver
description: Operate and develop the MomentWeaver（圈影）short-video pipeline that turns Moments-style images and copy or video-background-board projects into rendered MP4s and complete publishing packages. Use when Codex needs to configure or start MomentWeaver, generate storyboards and timelines, call or modify its Visual Project Render API, integrate SAK BGM or segmented narration through local-chinese-tts, debug local ffmpeg rendering, or prepare and validate final video, 4:3 cover, publishing copy, hashtags, and narration handoff assets.
---

# MomentWeaver

把朋友圈图文或可视编辑项目转为可发布的短视频交付包。把“生成 MP4”视为中间步骤；公开发布任务只有在视频、4:3 封面与发布文案齐全并通过验收后才算完成。

## 定位项目

1. 从当前工作区向下查找同时包含 `backend/app/`、`start.sh` 和 `README.md` 的 `MomentWeaver/` 目录。
2. 将找到的目录作为项目根目录；不要假定调用技能时的当前目录。
3. 先检查工作树状态，保留用户已有改动，避免修改 `.env`、`.sak_config.json`、本机 TTS 设置和 `storage/jobs/` 中无关任务。
4. 需要命令、环境变量、API 契约、产物路径或发布规范时，读取 [references/project-guide.md](references/project-guide.md)。

## 选择工作流

- 对朋友圈图片与文案，使用旧版图片/文案流程生成分镜、标题、字幕、发布文案和音乐方向。
- 对 `video-background-board` 输出，使用 Visual Project Render API；浏览器录屏只能作为可选前端工具，正式成片必须来自后端渲染器。
- 对带旁白视频，按场景生成分段音频，测量真实时长，再同步视觉时间轴。
- 对公开发布、宣发或正式交付，始终执行完整发布素材验收，不接受只有 MP4 的结果。

## 执行任务

### 启动或配置

1. 优先从 `.env.example` 识别可配置项，绝不输出或提交真实密钥。
2. 使用项目内置 `lib/nebula_llm_sdk` 处理文本规划；没有 LLM key 时允许使用本地分镜回退。
3. 使用项目内置 `lib/smart-asset-kit` 处理 BGM；使用 `/Users/lm/pyProj/local-chinese-tts` 处理配音与旁白 TTS。
4. 确认本机 `ffmpeg` 可用后再承诺渲染。
5. 需要合并版编辑器时先构建同级 `video-background-board`；构建产物不存在时，说明系统会回退到旧版静态前端。

### 渲染或开发

1. 在改代码前读取相关后端模型、规划器、音频适配器和渲染器，保持现有请求与产物契约。
2. 为 Visual Project 请求保留 `title`、发布描述、微视文案、话题、时间轴、画布、背景、元素和来源信息。
3. 提交渲染后轮询状态，检查 `visual_project.json`、`render_status.json`、`plan.json`、最终视频和 `publish.json`。
4. 让最终视频使用 H.264/AAC MP4；朋友圈转微视成片默认按 1080×1920 竖版交付，除非输入项目明确规定其他画布。
5. 对修改运行与任务相关的轻量测试；优先运行覆盖 Visual Project 契约、画布渲染、回退规划和旁白同步的测试。

### 处理音频

1. 让内置 BGM 通过 SAK `gen-audio` 流程生成或下载。
2. 启动 `/Users/lm/pyProj/local-chinese-tts/start_local_tts.sh`，并通过 `http://127.0.0.1:8765/v1/audio/speech` 为每个场景生成旁白。
3. 默认使用完全离线的 `K01`；用 `K02`–`K04` 切换轻量本地说话人，仅在用户要求更高质量或更强表现力时使用较重的 Q 系列。
4. 仅在用户明确要求在线音色时使用 `F*` 或 `M*`。
5. 在 manifest 中明确记录 `provider=local-chinese-tts`、`tts_backend=local-chinese-tts`、具体 `voice` 和真实音频时长。
6. 不得回退到 macOS `say` 或其他 TTS 后端；本机服务或所需本地模型不可用时让任务明确失败。
7. 对每段旁白测量真实音频时长，将视觉段设为“语音时长 + 停顿”，并让 `voice_end` 早于场景 `end`，保留自然静默。
8. 优先复用 `backend/app/voiceover_sync.py` 的时间轴构建和视觉项目同步能力。

## 完成发布交付

1. 生成可播放的最终 MP4，并确认音轨、旁白和画面同步正常。
2. 单独设计 4:3 横屏封面，同时输出 JPEG 与 PNG；推荐 1600×1200，最低 1200×900。
3. 在封面上保留至少 5% 四边安全区，并在约 320×240 缩略图尺寸检查产品名与核心钩子仍可读。
4. 不要拉伸竖版画面，也不要直接使用带字幕的视频帧代替横屏封面。
5. 编写先说明产品或内容、再给最强钩子的短标题。
6. 编写包含开场问题、核心卖点、可信证据与行动邀请的发布描述，并控制话题标签数量。
7. 有旁白时交付逐段旁白稿、音色、真实时长和同步信息。
8. 在交接说明中记录所有最终文件的绝对路径。

推荐交付结构：

```text
publish-assets/
  final-video.mp4
  cover-4x3.jpg
  cover-4x3.png
  PUBLISH_COPY.md
  narration.md
```

仅在实际任务含旁白时创建 `narration.md`。

## 验收底线

- 不把 Demo 描述成正式商业发行，不使用无法核验的数据，不宣传未实现功能。
- 不把“已有 `publish.json`”误判为封面已完成；当前后端稳定产物仍以 MP4 和 `publish.json` 为主，4:3 封面通常需要下游补齐。
- 不执行直接发布到微视；MomentWeaver 的边界是准备本地成片和发布素材。
- 不在未检查视频可播放、音频可听、封面比例与发布文案前宣告完成。
