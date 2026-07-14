from app.models import VisualBackgroundConfig, VisualCanvasElement, VisualProject
from app.visual_renderer import visual_project_to_plan_dict


def test_visual_project_contract_preserves_timeline_elements():
    project = VisualProject(
        title="后端渲染演示",
        description="从可视编辑器提交到 MomentWeaver 后端",
        weishi_caption="统一进入 MP4 和发布准备流程",
        timelineDuration=12,
        background=VisualBackgroundConfig(
            type="gradient",
            gradientColors=["#0f172a", "#1e40af"],
            showGrid=True,
        ),
        elements=[
            VisualCanvasElement(
                id="headline",
                type="text",
                textContent="第一幕：可视编辑",
                startTime=0,
                endTime=6,
                zIndex=2,
            ),
            VisualCanvasElement(
                id="cta",
                type="text",
                textContent="第二幕：后端 MP4",
                startTime=6,
                endTime=12,
                zIndex=3,
            ),
        ],
    )

    plan = visual_project_to_plan_dict(project)

    assert plan["source"] == "video-background-board"
    assert plan["visual_contract"] == "VisualProject/v1"
    assert plan["duration_seconds"] == 12
    assert plan["weishi_caption"] == "统一进入 MP4 和发布准备流程"
    assert [shot["title"] for shot in plan["shots"]] == [
        "第一幕：可视编辑",
        "第二幕：后端 MP4",
    ]
