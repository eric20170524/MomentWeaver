from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .models import VisualAudioSegment, VisualCanvasElement, VisualProject


@dataclass(frozen=True)
class VoiceoverSegmentDuration:
    """Measured narration duration for one storyboard/scene segment."""

    id: str
    duration_seconds: float
    pause_seconds: float | None = None
    minimum_scene_seconds: float = 0
    old_start: float = 0
    old_end: float | None = None


@dataclass(frozen=True)
class VoiceoverSegmentTiming:
    id: str
    old_start: float
    old_end: float
    start: float
    voice_end: float
    end: float
    voice_duration: float
    pause_duration: float


def build_voiceover_timeline(
    segments: Sequence[VoiceoverSegmentDuration],
    *,
    default_pause_seconds: float = 1.0,
) -> list[VoiceoverSegmentTiming]:
    """Build a scene timeline from measured narration duration.

    Each visual scene lasts at least `voice duration + pause`, and can also
    honor a caller-provided minimum scene duration. The returned `voice_end`
    marks where narration finishes; `end` includes the post-voice hold.
    """

    timings: list[VoiceoverSegmentTiming] = []
    cursor = 0.0
    old_cursor = 0.0
    for segment in segments:
        voice_duration = max(0.0, float(segment.duration_seconds))
        pause_duration = max(0.0, float(segment.pause_seconds if segment.pause_seconds is not None else default_pause_seconds))
        minimum_scene_duration = max(0.0, float(segment.minimum_scene_seconds))
        scene_duration = max(voice_duration + pause_duration, minimum_scene_duration)

        old_start = max(0.0, float(segment.old_start))
        old_end = float(segment.old_end) if segment.old_end is not None else old_start + max(scene_duration, minimum_scene_duration)
        if old_end < old_start:
            old_end = old_start

        timing = VoiceoverSegmentTiming(
            id=segment.id,
            old_start=old_start,
            old_end=old_end,
            start=cursor,
            voice_end=cursor + voice_duration,
            end=cursor + scene_duration,
            voice_duration=voice_duration,
            pause_duration=scene_duration - voice_duration,
        )
        timings.append(timing)
        cursor = timing.end
        old_cursor = max(old_cursor, old_end)

    return timings


def sync_visual_project_to_voiceover(
    project: VisualProject,
    measured_segments: Sequence[VoiceoverSegmentDuration],
    *,
    default_pause_seconds: float = 1.0,
) -> tuple[VisualProject, list[VoiceoverSegmentTiming]]:
    """Return a VisualProject retimed to measured narration segments.

    The function expects `measured_segments.id` values to match
    `VisualAudioSegment.id`. Visual elements are remapped from the original
    audio segment windows into the measured scene windows, while each
    `audioSegment` ends at the measured narration end, leaving the scene hold
    silent.
    """

    if not measured_segments:
        return _copy_project(project), []

    project_copy = _copy_project(project)
    audio_segments = list(_iter_audio_segments(project_copy.elements))
    audio_by_id = {segment.id: segment for segment in audio_segments}

    timeline_inputs: list[VoiceoverSegmentDuration] = []
    for item in measured_segments:
        audio_segment = audio_by_id.get(item.id)
        if audio_segment is None:
            continue
        timeline_inputs.append(
            VoiceoverSegmentDuration(
                id=item.id,
                duration_seconds=item.duration_seconds,
                pause_seconds=item.pause_seconds,
                minimum_scene_seconds=max(float(item.minimum_scene_seconds), audio_segment.endTime - audio_segment.startTime),
                old_start=audio_segment.startTime,
                old_end=audio_segment.endTime,
            )
        )

    timings = build_voiceover_timeline(timeline_inputs, default_pause_seconds=default_pause_seconds)
    if not timings:
        return project_copy, []

    timing_by_id = {timing.id: timing for timing in timings}
    for element in project_copy.elements:
        element.startTime = _remap_time(element.startTime, timings)
        element.endTime = max(element.startTime, _remap_time(element.endTime, timings))
        for audio_segment in element.audioSegments:
            timing = timing_by_id.get(audio_segment.id)
            if timing is None:
                audio_segment.startTime = _remap_time(audio_segment.startTime, timings)
                audio_segment.endTime = max(audio_segment.startTime, _remap_time(audio_segment.endTime, timings))
                continue
            audio_segment.startTime = timing.start
            audio_segment.endTime = max(timing.start, timing.voice_end)

    project_copy.timelineDuration = max(project_copy.timelineDuration, _remap_time(project.timelineDuration, timings), timings[-1].end)
    return project_copy, timings


def _iter_audio_segments(elements: Iterable[VisualCanvasElement]) -> Iterable[VisualAudioSegment]:
    for element in elements:
        yield from element.audioSegments


def _copy_project(project: VisualProject) -> VisualProject:
    model_copy = getattr(project, "model_copy", None)
    if callable(model_copy):
        return model_copy(deep=True)
    return project.copy(deep=True)


def _remap_time(value: float, timings: Sequence[VoiceoverSegmentTiming]) -> float:
    if not timings:
        return value

    value = float(value)
    first = timings[0]
    if value <= first.old_start:
        return max(0.0, first.start + (value - first.old_start))

    previous: VoiceoverSegmentTiming | None = None
    for timing in timings:
        if timing.old_start <= value <= timing.old_end:
            old_span = max(0.000001, timing.old_end - timing.old_start)
            ratio = (value - timing.old_start) / old_span
            return timing.start + ratio * (timing.end - timing.start)
        if previous and previous.old_end < value < timing.old_start:
            return previous.end + (value - previous.old_end)
        previous = timing

    last = timings[-1]
    return last.end + (value - last.old_end)
