from pathlib import Path

from fastapi.testclient import TestClient

from app import main


def test_visual_project_render_api_writes_status_video_and_publish(tmp_path, monkeypatch):
    def fake_job_dir(job_id: str) -> Path:
        return tmp_path / "jobs" / job_id

    monkeypatch.setattr(main, "job_dir", fake_job_dir)

    client = TestClient(main.app)
    payload = {
        "job_id": "api_visual_test",
        "project": {
            "title": "API Visual Test",
            "description": "Submitted through FastAPI TestClient",
            "weishi_caption": "API smoke caption",
            "hashtags": ["api", "visual"],
            "timelineDuration": 1,
            "canvas": {
                "width": 320,
                "height": 320,
                "aspect_ratio": "1:1",
            },
            "background": {
                "type": "solid",
                "solidColor": "#0f172a",
                "gradientAngle": 135,
                "gradientColors": ["#0f172a", "#1e1b4b"],
                "glassBlur": 16,
                "glassOpacity": 0.08,
                "glassBorderOpacity": 0.15,
                "showNoise": False,
                "showGrid": True,
                "gridColor": "rgba(255,255,255,0.1)",
                "embellishments": [],
            },
            "elements": [
                {
                    "id": "title",
                    "type": "text",
                    "textContent": "API OK",
                    "x": 50,
                    "y": 50,
                    "rotation": 0,
                    "scale": 1,
                    "zIndex": 1,
                    "color": "#ffffff",
                    "fontSize": 30,
                    "opacity": 1,
                    "startTime": 0,
                    "endTime": 1,
                    "fadeInDuration": 0,
                    "fadeOutDuration": 0,
                    "animationType": "fade",
                }
            ],
            "source": "video-background-board",
        },
    }

    response = client.post("/api/visual-projects/render", json=payload)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["job_id"] == "api_visual_test"
    assert data["status"] == "rendered"
    assert data["video_url"].endswith("/api_visual_test_visual.mp4")
    assert "短标题" in data["publish_text"]

    video_path = Path(data["video_path"])
    assert video_path.exists()
    assert video_path.stat().st_size > 0
    assert Path(data["project_path"]).exists()
    assert Path(data["status_path"]).exists()
    assert Path(data["publish_path"]).exists()

    status_response = client.get("/api/visual-projects/api_visual_test/status")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["status"] == "rendered"
    assert status_data["video_path"] == data["video_path"]
