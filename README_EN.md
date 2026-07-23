# MomentWeaver - 圈影

[中文](README.md) | English

Turn social-post images and copy into publish-ready 9:16 short videos.

## Product Showcase

MomentWeaver provides a visual canvas, asset and background editing, a draggable timeline, and a backend MP4 rendering entry point. The screenshot below shows the actual interface with the built-in sample script loaded:

![MomentWeaver visual editor product showcase](assets/momentweaver-product-showcase.jpg)

The core workflow from draft content to delivery:

```text
Images / copy -> storyboard and timeline -> canvas preview -> BGM / voiceover -> backend-rendered 1080x1920 MP4
```

## What It Does

- Upload social-post images or screenshots and paste the original copy.
- Use the bundled `lib/nebula_llm_sdk` package to generate a short-video storyboard, title, subtitles, and publishing copy.
- Optionally use the bundled `lib/smart-asset-kit` package to generate background music. The same SAK audio configuration can also be reused by course voiceover/TTS pipelines.
- Render a 1080x1920 MP4 locally with `ffmpeg`, ready to share or upload.
- Browse local export history and prepare short titles, descriptions, hashtags, 4:3 landscape covers, and file paths for a selected video.
- Accept visual stage/timeline projects from `video-background-board`, render them through the backend, and write the publishing handoff state.

Project identity:

- Chinese name: 圈影
- Engineering name: MomentWeaver
- Meaning: weaving the “moments” from social posts into shareable short-video imagery.

## Release Asset Contract

For public release, promotion, or delivery, a short-video task is not complete when it only has an MP4. It must also prepare:

1. A vertical master: 1080x1920, H.264/AAC MP4.
2. **A 4:3 landscape cover (required)** for content lists, article headers, landscape recommendation slots, or publishing previews.
3. A short publishing title that identifies the product or content first and then adds the strongest hook.
4. A description containing the opening question, key value, credible evidence, and a call to action.
5. A focused set of hashtags, prioritizing the product name, category, and core topic.
6. When narration is used: the segment script, voice preset, measured audio duration, and synchronization data.

Recommended delivery structure:

```text
publish-assets/
  final-video.mp4
  cover-4x3.jpg
  cover-4x3.png
  PUBLISH_COPY.md
  narration.md          # when narration is used
```

### 4:3 Landscape Cover Specification

| Item | Requirement |
| --- | --- |
| Aspect ratio | Fixed at 4:3; do not substitute a 16:9 video frame |
| Recommended size | 1600x1200; minimum 1200x900 |
| Format | JPEG for publishing, with a lossless PNG retained |
| Color | sRGB; avoid obvious color shifts after platform conversion |
| Safe area | Keep key titles, product names, and status marks at least 5% from each edge |
| Hierarchy | Product name largest; one-line hook next; version or “public preview” as a badge |
| Thumbnail check | Product name and core value should remain legible at roughly 320x240 |
| Visual consistency | Reuse the master video's visual language, font, palette, and assets |
| Content accuracy | Do not claim unimplemented features or present a demo as a commercial release |
| File naming | `<project>-cover-4x3.jpg` and `<project>-cover-4x3.png` |

Compose the cover separately. A landscape cover should rebalance the visual focus and text hierarchy for 4:3 reading; do not simply stretch the vertical frame or use a subtitle-heavy video frame. It should include:

- A clear product or content name.
- A short hook that immediately communicates the category.
- Any necessary version, chapter, public-preview, or release-status mark.
- The same visual language as the master video, recropped for landscape reading.
- A gradient, paper texture, outline, or shadow when the background is too busy for readable text.

Before delivery:

- [ ] The MP4 plays correctly, with a clear audio track and narration when applicable.
- [ ] Both JPEG and PNG versions of the 4:3 cover are available.
- [ ] Cover dimensions, ratio, safe area, and thumbnail readability pass review.
- [ ] The short title includes the product or content subject, not only the production method.
- [ ] The description sells the viewing experience before explaining the production process and quality checks.
- [ ] Final file paths are recorded in the publishing handoff document.

The stable outputs of the current Visual Project Render API are still the MP4 and `publish.json`. Until automatic cover generation is part of the backend, the caller or downstream publishing workflow must add the 4:3 cover before marking a task complete.

## Quick Start

```bash
cd MomentWeaver
python3 -m pip install -r requirements.txt
cp .env.example .env
./start.sh
```

To serve the merged visual editor from the MomentWeaver backend, build the React frontend first:

```bash
cd ../video-background-board
npm install
npm run build
cd ../MomentWeaver
./start.sh
```

If `video-background-board/dist` does not exist, MomentWeaver falls back to its legacy static frontend.

When the build exists, the merged editor is the default homepage. The legacy image/caption workflow remains available at:

```text
http://127.0.0.1:8787/legacy
```

Then open:

```text
http://127.0.0.1:8787
```

You can edit `.env` from the in-app settings panel. Host, port, reload, and Python runtime changes take effect after restarting `./start.sh`; Nebula and Smart Asset Kit settings apply immediately to new requests.

The app works without an LLM key by using a local storyboard fallback. To enable the model planner, set these values in `.env`:

```bash
NEBULA_API_KEY=...
NEBULA_PROVIDER=openai
NEBULA_MODEL=gpt-4o-mini
NEBULA_BASE_URL=
NEBULA_SDK_PATH=lib/nebula_llm_sdk
```

By default, MomentWeaver uses the installed SDK package under `MomentWeaver/lib/nebula_llm_sdk`, not a source checkout. Relative SDK paths in `.env` are resolved from the `MomentWeaver/` project root.

## Visual Project Render API

MomentWeaver also accepts visual editing output from `video-background-board`.

```text
POST /api/visual-projects/render
GET  /api/visual-projects/{job_id}/status
```

Example render request:

```json
{
  "project": {
    "title": "Visual editing short video",
    "description": "Publishing description",
    "weishi_caption": "Short-video caption",
    "hashtags": ["visual-editing", "MomentWeaver"],
    "timelineDuration": 15,
    "canvas": { "width": 1920, "height": 1080, "aspect_ratio": "16:9" },
    "background": {},
    "elements": [],
    "source": "video-background-board"
  }
}
```

The backend writes:

- `storage/jobs/{job_id}/visual_project.json`
- `storage/jobs/{job_id}/render_status.json`
- `storage/jobs/{job_id}/plan.json`
- `storage/jobs/{job_id}/videos/{job_id}_visual.mp4`
- `storage/jobs/{job_id}/publish.json`

Browser recording remains an optional frontend tool; the final deliverable MP4 comes from MomentWeaver's backend renderer.

## Smart Asset Kit

The default SAK path points to the installed SDK package in this project:

```text
MomentWeaver/lib/smart-asset-kit
```

Override it when needed:

```bash
SMART_ASSET_KIT_PATH=/path/to/smart-asset-kit
```

Local SAK credentials remain in `$SMART_ASSET_KIT_PATH/.sak_config.json`. That file is ignored and is not copied from an external SDK checkout.

The current SAK CLI supports `sak gen-audio`. MomentWeaver uses it directly for BGM, and companion course/video pipelines can reuse the same SAK MiniMax audio configuration for formal voiceover or TTS.

Built-in BGM flow:

1. Generate a storyboard.
2. MomentWeaver automatically creates a BGM prompt and searches candidates.
3. Download a selected candidate.
4. After the MP3 is downloaded or generated successfully, MomentWeaver automatically renders the MP4 with that music.

Voiceover/TTS reuse:

- MomentWeaver itself does not currently expose a narrator-recording UI.
- For course pipelines such as `AICodingCLI`, point `SMART_ASSET_KIT_PATH` to this SAK directory and use the pipeline's SAK MiniMax TTS provider, for example `COURSE_TTS_PROVIDER=sak-minimax`.
- The MiniMax key and model live in `smart-asset-kit/.sak_config.json` as `minimax_api_key` and `minimax_audio_model`; a separate `MINIMAX_GROUP_ID` is not required by this path.
- Generated manifests should make the backend explicit, for example `provider=minimax` and `tts_backend=sak-minimax`, so the narration source is clear.
- Narration must not fall back to macOS `say` or another local system voice. Missing MiniMax/SAK credentials should fail the job instead of producing release audio.
- Voice selection should remain scene-aware. `Yujie`, `Tianmei`, and `Shaonv` are reliable local MiniMax wrapper presets, but any available MiniMax `voice_id` may be passed when it better fits the scene.

### Segmented Narration Synchronization

For narrated videos, avoid placing one long voice track over a fixed timeline. Generate narration per scene or segment, measure the real audio duration, then set the visual segment duration to `voice duration + pause` while honoring any minimum scene duration.

Keep `voice_end` separate from the visual segment `end`: the visual scene should hold briefly after speech finishes, leaving natural silence before the next scene.

MomentWeaver includes `backend/app/voiceover_sync.py` for this pattern. `build_voiceover_timeline()` creates measured segment timings, and `sync_visual_project_to_voiceover()` can retime a `VisualProject` by matching `VoiceoverSegmentDuration.id` to `VisualAudioSegment.id`.

This is the preferred path for 3–5 minute explainers, course videos, and any micro-video where subtitles or scene content must stay aligned with narration.

If SAK later adds network music search and download, only `backend/app/music_assets.py` needs to change for MomentWeaver's built-in BGM step.

## Project Layout

```text
MomentWeaver/
  backend/app/       FastAPI API, Nebula planner, SAK adapter, ffmpeg renderer
  frontend/          Static app shell
  lib/               Installed Nebula SDK and Smart Asset Kit packages
  start.sh           Default launcher using system python3
  scripts/dev.sh     Local dev server
  storage/jobs/      Uploaded images and rendered videos
  tests/             Lightweight backend tests
```

## AI Capabilities in Use

MomentWeaver currently uses two kinds of model capability:

| Capability | Current use | Configuration |
| --- | --- | --- |
| Text model | Convert social-post copy into a short-video storyboard, title, subtitles, publishing copy, and initial music direction | MomentWeaver `.env` / settings panel |
| Audio generation model | Generate or download BGM in MomentWeaver; optionally provide the voiceover/TTS backend for course and video pipelines | `smart-asset-kit/.sak_config.json` |

It does not currently use:

- A vision model to understand image content; images are passed in as assets with their dimensions.
- A video generation model; MP4 files are composited locally with `ffmpeg`.
- An additional LLM for BGM prompts; prompts are generated locally from the storyboard using rules.
- A built-in narrator recording or voiceover UI; external course/video pipelines reuse SAK audio capabilities.

### Required Text Model Configuration

Set these values in the settings panel or `.env`:

```bash
NEBULA_API_KEY=your-key
NEBULA_PROVIDER=openai
NEBULA_MODEL=gpt-4o-mini
NEBULA_BASE_URL=
NEBULA_SDK_PATH=lib/nebula_llm_sdk
```

A good starting configuration is:

```bash
NEBULA_PROVIDER=openai
NEBULA_MODEL=gpt-4o-mini
```

For an OpenAI-compatible gateway, set:

```bash
NEBULA_BASE_URL=https://your-compatible-endpoint/v1
```

### Required Audio Configuration

MomentWeaver's built-in BGM only needs the SAK path. Course voiceover should reuse the same path:

```bash
SMART_ASSET_KIT_PATH=lib/smart-asset-kit
SAK_PYTHON=python3
```

Configure the actual audio provider, API key, and audio model in:

```text
MomentWeaver/lib/smart-asset-kit/.sak_config.json
```

MomentWeaver currently calls `sak gen-audio` for BGM, while course/video pipelines can use SAK MiniMax for narration. Typical provider-specific settings include:

- `provider=minimax`: configure `minimax_api_key` and `minimax_audio_model`.
- `provider=gemini`: configure `gemini_api_key` and `gemini_audio_model`.
- `provider=xai`: configure `xai_api_key` and `xai_audio_model`.

Course voiceover convention:

```bash
SMART_ASSET_KIT_PATH=lib/smart-asset-kit
COURSE_TTS_PROVIDER=sak-minimax
```

Formal `AICodingCLI` course narration should use this path and mark `tts_backend=sak-minimax` in the audio manifest. Narration must not fall back to macOS `say` or another system voice; missing MiniMax/SAK credentials should fail the job. Voices are recommended by scene, with `Yujie`, `Tianmei`, and `Shaonv` as common local wrapper candidates rather than the full MiniMax voice limit.

In one sentence: **MomentWeaver needs one text model; audio—BGM and reusable voiceover/TTS—uses the SAK audio model.**

## Notes

- Exported MP4 files are generated locally. Uploaded assets do not leave the machine unless you enable network-based LLM or SAK generation.
- Direct posting to 微视 is intentionally outside this MVP. The first reliable artifact is a local MP4 ready for manual upload.
