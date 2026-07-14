from app.models import VisualAudioSegment, VisualCanvasElement, VisualProject
from app.voiceover_sync import VoiceoverSegmentDuration, build_voiceover_timeline, sync_visual_project_to_voiceover


def test_build_voiceover_timeline_uses_measured_duration_pause_and_minimum():
    timings = build_voiceover_timeline(
        [
            VoiceoverSegmentDuration(id="intro", duration_seconds=5.0, pause_seconds=1.0, minimum_scene_seconds=8.0),
            VoiceoverSegmentDuration(id="data", duration_seconds=6.0, pause_seconds=2.0, minimum_scene_seconds=0.0),
        ]
    )

    assert timings[0].start == 0
    assert timings[0].voice_end == 5
    assert timings[0].end == 8
    assert timings[0].pause_duration == 3

    assert timings[1].start == 8
    assert timings[1].voice_end == 14
    assert timings[1].end == 16
    assert timings[1].pause_duration == 2


def test_sync_visual_project_to_voiceover_retimes_elements_and_keeps_scene_hold_silent():
    project = VisualProject(
        title="分段配音测试",
        timelineDuration=4,
        elements=[
            VisualCanvasElement(
                id="intro-card",
                type="text",
                textContent="第一段",
                startTime=0,
                endTime=2,
                audioSegments=[VisualAudioSegment(id="intro", startTime=0, endTime=2, text="第一段旁白")],
            ),
            VisualCanvasElement(
                id="data-card",
                type="text",
                textContent="第二段",
                startTime=2,
                endTime=4,
                audioSegments=[VisualAudioSegment(id="data", startTime=2, endTime=4, text="第二段旁白")],
            ),
        ],
    )

    synced, timings = sync_visual_project_to_voiceover(
        project,
        [
            VoiceoverSegmentDuration(id="intro", duration_seconds=3.0, pause_seconds=1.0),
            VoiceoverSegmentDuration(id="data", duration_seconds=1.0, pause_seconds=1.0),
        ],
    )

    assert [(round(item.start, 3), round(item.voice_end, 3), round(item.end, 3)) for item in timings] == [
        (0, 3, 4),
        (4, 5, 6),
    ]
    assert synced.timelineDuration == 6

    intro_element = synced.elements[0]
    data_element = synced.elements[1]
    assert (intro_element.startTime, intro_element.endTime) == (0, 4)
    assert (data_element.startTime, data_element.endTime) == (4, 6)

    assert (intro_element.audioSegments[0].startTime, intro_element.audioSegments[0].endTime) == (0, 3)
    assert (data_element.audioSegments[0].startTime, data_element.audioSegments[0].endTime) == (4, 5)
