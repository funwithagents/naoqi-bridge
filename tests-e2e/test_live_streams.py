"""Live: the robot's streams, on the target. Joints on any target, audio where Naoqi
pushes it (`audio_in`), a tone played into the sim's microphone (`audio_inject`), the
top camera's frames, pose and colours (`camera`), and
a head touch where a person can press the sensors (`touch_sensors`, `person_present`:
NAOQI_E2E_INTERACTIVE=1, with `-s` to see the prompt).
"""

from __future__ import annotations

import asyncio
import math
import time

import numpy as np
import pytest
from support import MEASUREMENTS, naoqi

from naoqi_bridge import (
    AudioStream,
    CameraFrame,
    CameraStream,
    CameraStreams,
    JointsState,
    JointsStream,
    PostureState,
    StreamSettings,
    TouchEvent,
)
from naoqi_bridge.testing import LiveTarget, live_config, live_session


def test_joints_are_sampled_from_the_robot():
    config = live_config(
        StreamSettings(joints=JointsStream(enabled=True, period_s=0.1))
    )

    async def run() -> tuple[JointsState, JointsState]:
        async with live_session(config) as bridge:
            async with asyncio.timeout(5.0):
                first = await bridge.joints.wait_for(lambda s: s is not None)
                assert first is not None
                later = await bridge.joints.wait_for(
                    lambda s: s is not None and s.ts > first.ts
                )
                assert later is not None
            return first, later

    first, later = asyncio.run(run())
    assert "HeadYaw" in first.names
    assert len(first.angles) == len(first.names)
    assert all(abs(angle) <= math.pi for angle in first.angles)  # radians
    assert later.names == first.names


def test_the_posture_is_read_from_the_robot_at_start():
    async def run() -> PostureState | None:
        async with live_session(live_config()) as bridge:
            return bridge.posture.value

    state = asyncio.run(run())
    assert state is not None
    assert state.posture and state.family  # Naoqi's names, whatever the robot is in
    assert state.moving_to is None


@pytest.mark.requires("audio_in")
def test_audio_arrives_at_16_khz_mono():
    config = live_config(
        StreamSettings(audio=AudioStream(enabled=True, channel="front"))
    )

    async def run() -> tuple[int, float, int, int]:
        async with live_session(config) as bridge:
            received = 0
            started = 0.0
            async with asyncio.timeout(5.0):
                async for chunk in bridge.audio_input():
                    if not started:
                        started = time.monotonic()  # count from the first chunk
                        continue
                    received += len(chunk)
                    if time.monotonic() - started >= 2.0:
                        break
            elapsed = time.monotonic() - started
            latest = bridge.mic.latest()
            assert latest is not None
            return received // 2, elapsed, latest.channels, latest.samples_per_channel

    samples, elapsed, channels, chunk_samples = asyncio.run(run())
    rate = samples / elapsed
    # Recorded for specs/microphone.md's open question (the real chunk size).
    MEASUREMENTS.append(("audio chunk at 16 kHz", f"{chunk_samples} samples"))
    assert channels == 1
    assert 12000 < rate < 20000  # about 16 kHz, give or take a chunk at the edges


@pytest.mark.requires("audio_inject")
def test_a_sound_played_into_the_sims_microphone_reaches_audio_input(
    live_target: LiveTarget,
):
    # Drives the sim itself: a 440 Hz tone into naoqi-sim's fake microphone must come
    # out of the bridge's audio stream (specs/testing.md "Live tier: the harness").
    sim = live_target.sim
    assert sim is not None  # audio_inject: the session owns the sim
    rate = 16000
    tone = (8000 * np.sin(2 * np.pi * 440 * np.arange(rate) / rate)).astype(np.int16)
    config = live_config(
        StreamSettings(audio=AudioStream(enabled=True, channel="front"))
    )

    async def run() -> np.ndarray:
        async with live_session(config) as bridge:
            chunks: list[bytes] = []
            played = 0.0
            async with asyncio.timeout(10.0):
                async for chunk in bridge.audio_input():
                    if not played:  # the stream runs: play into it
                        sim.fake_audio.play(tone, rate)
                        played = time.monotonic()
                    chunks.append(chunk)
                    if time.monotonic() - played >= 2.0:
                        break
            return np.frombuffer(b"".join(chunks), "<i2")

    samples = asyncio.run(run())
    assert np.abs(samples).max() > 1000  # heard, not the quiet room
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
    peak = float(np.fft.rfftfreq(len(samples), 1 / rate)[np.argmax(spectrum)])
    assert abs(peak - 440) < 20


@pytest.mark.requires("camera")
def test_the_top_camera_streams_frames_with_its_pose():
    config = live_config(
        StreamSettings(
            cameras=CameraStreams(
                top=CameraStream(enabled=True, resolution="qvga", fps=10)
            )
        )
    )

    async def run() -> tuple[CameraFrame, int, float]:
        async with live_session(config) as bridge:
            feed = bridge.cameras["top"]
            async with asyncio.timeout(3.0):
                frame = await feed.wait_for(lambda _: True)
            first = feed.published_count
            started = time.monotonic()
            await asyncio.sleep(1.0)
            return frame, feed.published_count - first, time.monotonic() - started

    frame, frames, elapsed = asyncio.run(run())
    # Recorded for specs/camera.md: the rate the top feed achieves at 10 fps asked.
    MEASUREMENTS.append(("top camera at 10 fps", f"{frames / elapsed:.1f} fps"))
    assert (frame.width, frame.height) == (320, 240)
    assert len(frame.data) == 320 * 240 * 3
    assert frame.image.shape == (240, 320, 3)
    transform = frame.camera_transform
    assert len(transform) == 16
    assert transform[12:] == pytest.approx((0.0, 0.0, 0.0, 1.0))
    assert 0.3 < transform[11] < 0.6  # the camera's height: sitting or standing
    assert all(0.5 < angle < 1.5 for angle in frame.fov)
    assert frames >= 5


@pytest.mark.requires("camera")
def test_the_top_cameras_colours_are_naoqis_own():
    """The feed's BGR, which the bridge converts from YUV422, against the BGR Naoqi
    converts itself for a subscription of its own: within a level on the same capture (a
    sim serves both subscriptions the same one) on average, within a few levels per channel when
    the two captures differ (a robot's), which a swapped channel or a wrong range misses."""
    config = live_config(
        StreamSettings(
            cameras=CameraStreams(
                top=CameraStream(enabled=True, resolution="qvga", fps=10)
            )
        )
    )

    async def run() -> tuple[CameraFrame, np.ndarray, float]:
        async with live_session(config) as bridge:
            video = naoqi(bridge, "ALVideoDevice")
            handle = video.subscribeCamera("NaoqiBridgeLiveBgr", 0, 1, 13, 10)  # type: ignore[attr-defined]
            try:
                await asyncio.sleep(0.5)
                image = await asyncio.to_thread(video.getImageRemote, handle)  # type: ignore[attr-defined]
            finally:
                video.unsubscribe(handle)  # type: ignore[attr-defined]
            width, height = int(image[0]), int(image[1])
            reference = np.frombuffer(bytes(image[6]), np.uint8).reshape(
                height, width, 3
            )
            ts = image[4] + image[5] / 1e6
            async with asyncio.timeout(3.0):
                frame = await bridge.cameras["top"].wait_for(lambda f: f.naoqi_ts >= ts)
            return frame, reference, ts

    frame, reference, ts = asyncio.run(run())
    ours = frame.image.astype(int)
    theirs = reference.astype(int)
    assert ours.shape == theirs.shape
    channel_gap = np.abs(ours.mean(axis=(0, 1)) - theirs.mean(axis=(0, 1)))
    if frame.naoqi_ts == ts:
        error = np.abs(ours - theirs)
        MEASUREMENTS.append(
            (
                "top camera YUV422 vs Naoqi's BGR",
                f"mean {error.mean():.2f}, p99 {np.percentile(error, 99):.0f} levels",
            )
        )
        # Within a level on average. Not pixel for pixel: Naoqi scales the QVGA image
        # differently by colorspace, which moves sharp edges by tens of levels; a wrong
        # range or a swapped channel moves the mean by several.
        assert error.mean() < 1.0
    else:
        MEASUREMENTS.append(
            (
                "top camera YUV422 vs Naoqi's BGR, other capture",
                f"channel means {channel_gap.round(1).tolist()}",
            )
        )
    assert channel_gap.max() < 6


@pytest.mark.requires("touch_sensors", "person_present")
def test_a_head_touch_reaches_on_touch(capsys: pytest.CaptureFixture[str]):
    config = live_config()  # touch is always on

    async def run() -> TouchEvent:
        async with live_session(config) as bridge:
            touched: asyncio.Queue[TouchEvent] = asyncio.Queue()
            bridge.on_touch.subscribe(touched.put_nowait)
            await bridge.change_eyes_color("green")  # the cue, with the prompt
            with capsys.disabled():
                print("\n>>> Touch the FRONT of Nao's head within 20 s")
            async with asyncio.timeout(20.0):
                while True:
                    event = await touched.get()
                    if event.part == "FrontTactilTouched" and event.touched:
                        return event

    event = asyncio.run(run())
    assert (event.part, event.touched) == ("FrontTactilTouched", True)
