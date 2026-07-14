from pathlib import Path
import shutil
import tempfile
from app.models import VisualProject, VisualCanvasSpec, VisualBackgroundConfig, VisualCanvasElement
from app.visual_renderer import render_visual_project


def test_render_visual_project_generates_mp4():
    # Setup temp directory for testing output
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # Create a simple visual project
        project = VisualProject(
            title="测试可视编辑视频",
            description="这是一个用于自动化测试的 Canvas 视频渲染",
            weishi_caption="测试视频描述 #自动化 #测试",
            hashtags=["自动化", "测试"],
            timelineDuration=3.0,
            canvas=VisualCanvasSpec(width=640, height=360, aspect_ratio="16:9"),
            background=VisualBackgroundConfig(
                type="gradient",
                solidColor="#0f172a",
                gradientColors=["#0f172a", "#1e1b4b"]
            ),
            elements=[
                VisualCanvasElement(
                    id="text-1",
                    type="text",
                    textContent="Hello Automation! ✨",
                    x=50.0,
                    y=50.0,
                    fontSize=32.0,
                    color="#ffffff",
                    startTime=0.0,
                    endTime=3.0,
                    fadeInDuration=0.5,
                    fadeOutDuration=0.5,
                    animationType="fade"
                )
            ]
        )

        job_id = "test_visual_job"

        # Run visual project renderer
        output_file = render_visual_project(job_id, project, temp_dir)

        # Assertions
        assert output_file.exists(), f"Output video file should exist: {output_file}"
        assert output_file.suffix == ".mp4", "Output file should be an MP4 video"
        assert output_file.stat().st_size > 0, "Output file size should be greater than 0"

    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
