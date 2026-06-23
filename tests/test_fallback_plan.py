from app.llm_planner import fallback_plan
from app.models import UploadedAsset


def test_fallback_plan_uses_assets_and_duration():
    assets = [
        UploadedAsset(
            filename="a.png",
            url="/a.png",
            path="/tmp/a.png",
            width=100,
            height=100,
        )
    ]
    plan = fallback_plan("创意时代，已经到来。\n\n这是一次新的机会。", assets, duration_seconds=18)
    assert plan.aspect_ratio == "9:16"
    assert len(plan.shots) >= 3
    assert all(shot.image_index == 0 for shot in plan.shots)
    assert 12 <= plan.duration_seconds <= 45
