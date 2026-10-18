# Testing your project against the bridge

If your project depends on `naoqi-bridge`, test your robot code the way the bridge tests itself: **unit tests on the `fake` backend, live tests on a `sim` or a `real` target.** The bridge ships its live-test harness as importable code, `naoqi_bridge.testing`, so you get the sim's lifecycle, the probe of what the target can do and the gating of tests that move the robot for free. The design is in [specs/testing_support.md](../../specs/testing_support.md); the bridge's own practice in [specs/testing.md](../../specs/testing.md).

## Backends, tiers, extras

| Your tier | Backend | Install | Needs |
|---|---|---|---|
| Unit | `fake` | `naoqi-bridge` | nothing: offline, deterministic, every platform |
| Live | `sim` | `naoqi-bridge[sim,test]` | Docker and the images ([simulator.md](simulator.md)); the harness starts the sim |
| Live | `real` | `naoqi-bridge[test]` | your Nao on the network |

Keep the live tests in a directory your default `pytest` run doesn't collect (the bridge uses `tests-e2e/` and points `testpaths` at `tests/`), so the normal loop stays fast and robot-free.

## Unit tests: the `fake` backend

`NaoqiBridge("fake")` needs nothing. The fake records every command on `robot.commands`, a list of `(method, arguments)` pairs in Naoqi's terms (`say`, `run_behavior`, `fade_eyes`), serves a fixed catalog (four dances, four apps, six body actions, the five reaction types), keeps the real timing of what spans time (a dance 5 s, a sentence 1 s, a posture move 2 s; set `behavior_duration_s`, `speech_duration_s` and `posture_duration_s` on the fake to shorten them) and starts with the motors off. Assert through the `bridge.robot` escape hatch, narrowed to `FakeNaoqiRobot` for the type checker:

```python
import asyncio

from naoqi_bridge import NaoqiBridge
from naoqi_bridge.fake_robot import FakeNaoqiRobot


async def greet(bridge: NaoqiBridge) -> None:
    """Your code under test: wake the robot, greet, react."""
    await bridge.wake_up()
    await bridge.say("Hello!")
    await bridge.expressive_reaction("Happy")


def test_greet_speaks_then_reacts():
    async def run() -> list[str]:
        async with NaoqiBridge("fake") as bridge:
            robot = bridge.robot
            assert isinstance(robot, FakeNaoqiRobot)
            robot.speech_duration_s = 0.0  # no need to wait for the fake's real timing here
            robot.behavior_duration_s = 0.0
            await greet(bridge)
            return [method for method, _args in robot.commands]

    commands = asyncio.run(run())
    assert commands.index("say") < commands.index("run_behavior")  # it greets before it reacts
    assert "wake_up" in commands  # the reaction needs the motors on; without wake_up it raises
```

The fake also lets a test drive the streams from the robot's side: `robot.touch("FrontTactilTouched", 1.0)` fires a touch event as Naoqi would, `robot.posture_event("PostureChanged", "Stand")` a posture event, `robot.emit_audio(channels, samples, buffer)` a microphone buffer; with the streams enabled it pushes silent audio every 85 ms and a test pattern on the cameras at the configured rate, and reports the joints of the posture it is in. `robot.posture_succeeds = False` makes a posture move fail, so the `CommandFailedError` path is testable too.

The bridge's own fast tier drives coroutines with `asyncio.run` and needs no pytest-asyncio; use that plugin if you prefer `async def` tests.

## Live tests: `sim` or `real`

Opt into the shipped pytest plugin from your **rootdir** `conftest.py`:

```python
# conftest.py
pytest_plugins = ["naoqi_bridge.testing.plugin"]
```

A conftest below the rootdir (a `tests-e2e/conftest.py`) cannot declare `pytest_plugins`; register the plugin from its `pytest_configure` instead, as the bridge's own live tier does:

```python
# tests-e2e/conftest.py
def pytest_configure(config):
    config.pluginmanager.import_plugin("naoqi_bridge.testing.plugin")
```

The plugin owns the session's target: on `sim` it starts a headless naoqi-sim (silent, a rendered top camera, a `fake` audio input tests can play into) once per run and stops it at the end; on `real` it connects to your robot. Then it **probes what the target can do**, once, and every test declares what it needs with a marker. A test runs where its needs are met and **skips** elsewhere, so the same test runs on a sim, on a robot with dances, or on a robot someone is watching:

```python
import asyncio

import pytest

from naoqi_bridge.testing import live_config, live_session


def test_it_speaks():
    async def run() -> None:
        async with live_session(live_config()) as bridge:
            await bridge.say("Hello from a live test.")

    asyncio.run(run())


@pytest.mark.requires("dances", "room_to_move")
def test_it_dances():
    async def run() -> None:
        async with live_session(live_config(), motion=True) as bridge:  # motors woken, rested on exit
            dance = bridge.get_dance_behaviors()[0]
            await bridge.dance(dance.id)

    asyncio.run(run())
```

- **`live_config(streams=None)`** is the target's bridge config with the streams you ask for: the session's sim, borrowed (`spawn: "never"`, so a test never starts a second one), or the robot at `NAOQI_E2E_IP`. `live_bridge_dict()` is the same as a dict, for a server you run in a subprocess.
- **`live_session(config, *, motion=False)`** starts the bridge and leaves the robot as it found it on exit, the eyes white, even when the test failed. `motion=True` wakes the motors on entry and rests the robot on exit, and **requires the `room_to_move` capability**: a test that moves the robot without declaring it fails, as a test bug, rather than moving a robot nobody cleared the floor for.
- **`@pytest.mark.requires(...)`** goes on a test, a class or a module's `pytestmark`; marks add up. It is checked before the test's fixtures, so no bridge starts for a test that skips, and the skip says what was missing (`the target lacks dances`; `needs room_to_move: set NAOQI_E2E_ALLOW_MOTION=1 once …`). An unknown name fails the run at collection. `requires_caps(live_target, "dances")` is the same gate as a call, for a need known only at run time.
- The **`live_target`** fixture is the `LiveTarget`: its `kind`, `naoqi_version`, `caps`, and on an owned sim `sim`, the `NaoqiSim` object, whose `fake_audio.play("hello.wav")` plays a sound into the robot's microphone.

Run the live tier explicitly: `uv run pytest tests-e2e -rs`. The run ends with a `live target` section naming the target, its version and its capabilities, and `-rs` prints each skip's reason.

### Capabilities

| Capability | Meaning | sim | Nao |
|---|---|---|---|
| `sim` | the target is naoqi-sim | ✅ | ❌ |
| `audio_in` | Naoqi pushes microphone audio | ✅ | ✅ |
| `audio_inject` | a test can play a sound into the microphone (an owned sim with the `fake` source) | ✅ | ❌ |
| `camera` | Naoqi serves camera images | ✅ | ✅ |
| `touch_sensors` | head sensors a person can press | ❌ | ✅ |
| `dances`, `body_actions`, `apps` | the catalog holds at least one | ❌ | the robot's packages |
| `room_to_move` | the robot may move its limbs: the floor is clear and someone watches | always | `NAOQI_E2E_ALLOW_MOTION=1` |
| `person_present` | someone at the robot acts on prompts | | `NAOQI_E2E_INTERACTIVE=1` |
| `display` | the run may open windows (the viewer) | `NAOQI_E2E_VIEWER=1` | `NAOQI_E2E_VIEWER=1` |

The first eight are **probed** from the target; the last three are **declared** by whoever runs the tests, since no probe can see the room. A test never asks which target it is on, or which NAOqi version, only what the target can do.

A **profile** names what a kind of target is expected to offer, and a missing capability then **fails** the run instead of skipping tests: `sim` (the default on the sim target: `sim`, `audio_in`, `audio_inject`, `camera`, `room_to_move`), `nao` (`audio_in`, `camera`, `touch_sensors`, `body_actions`), `none`. `NAOQI_E2E_REQUIRED_CAPS` adds names on top.

### Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `NAOQI_E2E_TARGET` | `sim` | `sim` or `real`. Unset, a target that can't run (no Docker, no images, no `qi`) **skips** every test; set, it **fails** them |
| `NAOQI_E2E_SIM_VERSION` | `2.1` | `sim`: the NAOqi version of the session's sim, `2.1` or `2.8` |
| `NAOQI_E2E_SIM_VIEWER` | unset | `sim`: `1` opens the sim's window instead of running headless, to watch the run |
| `NAOQI_E2E_IP`, `NAOQI_E2E_PORT` | , `9559` | `real`: the robot |
| `NAOQI_E2E_ALLOW_MOTION` | unset | `real`: `1` declares `room_to_move` |
| `NAOQI_E2E_INTERACTIVE` | unset | `1` declares `person_present` |
| `NAOQI_E2E_VIEWER` | unset | `1` declares `display` |
| `NAOQI_E2E_DECLARED_CAPS` | unset | comma-separated declared capabilities, the generic form of the three flags |
| `NAOQI_E2E_PROFILE` | `sim` on sim, none on real | the expected capabilities; a missing one fails the run |
| `NAOQI_E2E_REQUIRED_CAPS` | unset | comma-separated capabilities required on top of the profile |

```
uv run pytest tests-e2e -rs                                                        # a headless 2.1 sim, started for the run
NAOQI_E2E_SIM_VERSION=2.8 uv run pytest tests-e2e -rs                              # the 2.8 sim
NAOQI_E2E_TARGET=real NAOQI_E2E_IP=192.168.1.42 NAOQI_E2E_PROFILE=nao uv run pytest tests-e2e -rs                             # a Nao; nothing moves the limbs
NAOQI_E2E_TARGET=real NAOQI_E2E_IP=192.168.1.42 NAOQI_E2E_PROFILE=nao NAOQI_E2E_ALLOW_MOTION=1 uv run pytest tests-e2e -rs    # clear the floor, stay next to it
```

Stop any sim you run by hand before the live tier: the harness starts its own and needs port 9559. The bridge's own `tests-e2e/` is a complete example of a live tier on this harness, with tests for the verbs, the streams, cancellation and both servers.
