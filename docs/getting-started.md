# Getting started

Your first application on the bridge, then the config that takes the same code to a simulated or a real robot. The API's contracts in full are in [reference/api.md](reference/api.md), every config field in [reference/configuration.md](reference/configuration.md), what each backend needs and gives in [reference/backends.md](reference/backends.md).

## Install

Python 3.12 or 3.13, in a project of your own (`uv init my-nao-app && cd my-nao-app` creates one). The package is not on PyPI; add it from its git URL, with the extras you need:

```
uv add "naoqi-bridge @ git+https://github.com/funwithagents/naoqi-bridge"            # a robot, and the offline fake
uv add "naoqi-bridge[sim] @ git+https://github.com/funwithagents/naoqi-bridge"       # the same, plus the simulator
uv add "naoqi-bridge[sim,test] @ git+https://github.com/funwithagents/naoqi-bridge"  # plus the live-test harness
```

The bridge is at version 0.1 and its API changes without a deprecation period, so pin a commit (`@<sha>` after the URL) and move it deliberately. `uv` resolves the bridge's own sources through it: `qi` comes from the libqi package index, naoqi-sim and naoqi-viewer from their git pins, nothing to declare on your side. The extras, what each adds and which platforms have `qi` are in the [README](../README.md#install). On a platform without a `qi` wheel (an Intel Mac, a Linux arm64 box), `uv add` succeeds and the `fake` backend is the one that runs.

## Your first application

Everything goes through `NaoqiBridge`, used as an async context manager: nothing connects until you enter it, leaving it tears everything down. This program runs on the offline `fake`, which needs no robot, no Docker and no extra. It speaks, plays an animation, and reads each of the robot's streams once:

```python
import asyncio

from naoqi_bridge import NaoqiBridge, TouchEvent

CONFIG = {
    "backend": "fake",
    "streams": {
        "joints": {"enabled": True},
        "audio": {"enabled": True},
        "cameras": {"top": {"enabled": True}},
    },
}


def on_touch(event: TouchEvent) -> None:
    print("touched" if event.touched else "released", event.part)


async def main() -> None:
    async with NaoqiBridge.from_dict(CONFIG) as bridge:
        bridge.on_touch.subscribe(on_touch)  # the head's tactile sensors, whenever they fire
        await bridge.wake_up()  # the verbs that move the body need the motors on
        await bridge.set_tts_language("English")
        await bridge.say("Hello, I am Nao.")  # returns once spoken
        print(bridge.get_expressive_reaction_types())
        await bridge.expressive_reaction("Happy")  # returns when the animation ends
        posture = bridge.posture.value  # what Naoqi says the robot's posture is
        print(posture.posture if posture else "posture unknown")
        joints = await bridge.joints.wait_for(lambda state: state is not None)
        angles = dict(zip(joints.names, joints.angles))
        print(f"{len(joints.names)} joints, HeadYaw at {angles['HeadYaw']:.2f} rad")
        async for chunk in bridge.audio_input():  # the microphone: int16 mono PCM at 16 kHz
            print(f"{len(chunk)} bytes of microphone audio at {bridge.mic.sample_rate} Hz")
            break  # stop iterating to stop listening
        frame = await bridge.cameras["top"].wait_for(lambda frame: True)
        print(f"a {frame.width}x{frame.height} camera frame")
        await bridge.rest()  # motors off, in a safe posture


asyncio.run(main())
```

Save it as `first_app.py` and run it:

```
uv run python first_app.py
```

It prints:

```
['Happy', 'Proud', 'Laugh', 'Sad', 'HeadTouched']
Crouch
26 joints, HeadYaw at 0.00 rad
2720 bytes of microphone audio at 16000 Hz
a 320x240 camera frame
```

**Nothing is heard and nothing moves: this is the fake.** It records every command on `bridge.robot` instead of sending it anywhere, serves a fixed catalog of dances, reactions, body actions and apps, answers the microphone with silence and the cameras with a test pattern, and reports the joints of the posture it is in. It keeps the timing of what spans time, so the program runs as it would against a robot: `say` takes a second, the reaction five, a posture move two. The same file drives a sim or a robot once the dict names another backend (next section); there the voice comes out of the loudspeaker and the arms move.

What happened, in order: the session started (on the fake, instantly; on a robot, the connection, the posture and touch subscriptions, the streams the config enables, the catalog); the motors were enabled, which the verbs that move the body need, and which the fake starts with off, like a robot at rest; `say` returned once the sentence was spoken; the reaction played a random `Happy` animation and returned when it ended; the posture, the joints, one microphone chunk and one camera frame were read; `rest` relaxed the robot and switched the motors off. Leaving the block closed everything.

**To interrupt what spans time, cancel the task that awaits it.** Cancel a `say`, a posture move, a dance or a reaction (`task.cancel()`, an `asyncio.timeout`, a `TaskGroup` unwinding) and the robot has stopped what the verb started by the time the `CancelledError` reaches you: silent, or the move or the animation stopped where the cancel caught it. The session stays usable for the next verb ([reference/api.md](reference/api.md#cancellation)).

**Every failure says why.** A verb returns `None` when it succeeded and raises otherwise: `MotorsOffError` for a move with the motors off, `ValueError` for a dance the robot doesn't have (the message lists the known ones), `CommandFailedError` when Naoqi refused the command, with Naoqi's error chained. `except (BridgeError, ValueError)` catches every expected failure ([reference/api.md](reference/api.md#errors)).

## Running it on a simulated or a real robot

Swap the dict for a config file and the same program drives a Naoqi. `NaoqiBridge.from_json_file("robot.json")` takes it; a config names the backend, how to reach the robot or which sim to run, the streams and whether to open the viewer ([reference/configuration.md](reference/configuration.md)):

| You have | `backend` | The config also needs | The bridge |
|---|---|---|---|
| nothing | `"fake"` (the default) | nothing | runs offline, as above |
| Docker and the `[sim]` extra | `"sim"` | a `sim` block: `{"spawn": "auto", "config": {"naoqi": {"version": "2.1"}}}` (or `"2.8"`) | starts [naoqi-sim](guides/simulator.md), NAOqi itself in a container, speaks through your loudspeaker, shows the robot in a window, and stops it on exit; or borrows one already running |
| a Nao on the network | `"real"` | a `robot` block: `{"ip": "192.168.1.42"}` (press the chest button to hear the address) | connects over `qi` within `connect_timeout_s` (5 s by default), or fails with `RobotConnectionError` |

```json
{
  "backend": "real",
  "robot": { "ip": "192.168.1.42" },
  "streams": {
    "joints": { "enabled": true },
    "audio": { "enabled": true },
    "cameras": { "top": { "enabled": true, "resolution": "qvga", "fps": 10 } }
  }
}
```

Changing `backend` is the whole move: the other blocks are checked on every backend and ignored where they don't apply (`robot` on the fake, `sim` on a robot), so one file serves the three. What each backend offers (a sim has no dances and no touch, a 2.8 sim sits slowly) and how far each has been validated is one table in [reference/backends.md](reference/backends.md). The ready-made files in [examples/configs/](../examples/configs/) are server configs: their `bridge` block is exactly this config, to copy out.

Two things a program notices when it moves off the fake. The catalog is the robot's: `get_dance_behaviors()` returns what is installed, which on a sim is nothing. And the robot really moves: give it room, and keep a hand near it the first time it stands.

## The lifecycle, in a host of your own

`async with` is the recommended form: the block stops the session on every way out, a cancel included. A host with lifecycle hooks of its own, a web framework's lifespan, a GUI, an agent runtime, uses the pair it is sugar over:

```python
bridge = NaoqiBridge.from_json_file("robot.json")
await bridge.start()    # connects; raises RobotConnectionError when it can't
...
await bridge.stop()     # idempotent; closes everything in order, the sim it started included
```

One event loop owns a session: start it, await its verbs and stop it on the same loop. The streams' consumers run on that loop too: touch handlers are called there, the observables publish there. Tasks you start around the bridge, a speech recognizer draining `audio_input()`, a watcher on `joints.changes()`, are yours to cancel and await before the session ends; the `audio_input()` and `frames()` iterators end on their own when the session stops.

## The streams

The robot's data comes back out through five streams, each with the shape its data calls for. Touch and posture are always on; joints, audio and the cameras are subscribed on the robot only when the config enables them, and their API raises `BridgeError` otherwise.

| Stream | API | Shape |
|---|---|---|
| touch | `bridge.on_touch.subscribe(handler)` | an **event**: every `TouchEvent(part, touched)` reaches every handler, on the event loop |
| posture | `bridge.posture` | an **observable** `PostureState`: Naoqi's posture and family, and whether a bridge verb is moving the robot and where to |
| joints | `bridge.joints` | an observable `JointsState(names, angles, ts)` in radians, sampled every `period_s` |
| audio | `bridge.audio_input()` | a **subscriber** over the one microphone feed: every chunk, in order, at its own pace, int16 LE mono at 16 kHz |
| cameras | `bridge.cameras["top"]`, `["bottom"]` | a feed per camera: `latest()` is the newest `CameraFrame`, `frames()` follows them, latest-wins |

An observable is read (`.value`), waited on (`await .wait_for(predicate)`) or followed (`async for state in .changes()`, which skips to the latest when the consumer is slow). The audio subscribers each receive the whole stream; `preroll_s=` starts one in the past, as far as the feed's ring reaches, so a recognizer started by a wake word hears the sentence that woke it. A camera frame carries its pixels (`data`, BGR; `image`, a numpy view), Naoqi's timestamp, the camera's pose in the robot frame and its field of view. The values in full: [reference/api.md](reference/api.md#streams).

```python
async def listen(bridge: NaoqiBridge) -> None:
    async for chunk in bridge.audio_input(preroll_s=1.0):
        ...  # feed your speech recognizer


async def watch_posture(bridge: NaoqiBridge) -> None:
    async for state in bridge.posture.changes():
        if state is not None and not state.moving:
            print("settled in", state.posture)
```

## Driving it from an agent

Two servers expose the same `NaoqiBridge` without a line of your own: the [MCP server](servers/mcp-server.md) turns its verbs into tools an LLM agent calls (Claude Desktop, or any MCP client), and the [WebSocket server](servers/websocket-server.md) speaks a JSON protocol for a game engine, a web app or another language. Both run from one config file and one command.

An agent runtime of your own, in Python, drives the bridge directly: each tool is a function calling one verb, and the verb's error is the tool's answer, so the model reads why and tries something else:

```python
from naoqi_bridge import BridgeError, NaoqiBridge


def make_tools(bridge: NaoqiBridge):
    async def say(text: str) -> str:
        """Speak the text out loud through the robot's loudspeaker."""
        await bridge.say(text)
        return "said"

    async def dance(dance_id: str) -> str:
        """Play an installed dance. Call list_dances for the ids."""
        try:
            await bridge.dance(dance_id)
        except (BridgeError, ValueError) as e:  # motors off, unknown dance, Naoqi refused
            return f"could not dance {dance_id}: {e}"
        return f"danced {dance_id}"

    def list_dances() -> list[str]:
        """The dances this robot has installed."""
        return [dance.id for dance in bridge.get_dance_behaviors()]

    return [say, dance, list_dances]
```

A dance can last minutes: a runtime that issues one tool call at a time starts it as a task and returns once it shows in `bridge.current_dances`, as the MCP server does, so the agent can still be asked to stop it.

## Where next

- [reference/api.md](reference/api.md): every verb, value, error and contract.
- [reference/configuration.md](reference/configuration.md): every config field.
- [guides/simulator.md](guides/simulator.md): the simulator, on NAOqi 2.1 or 2.8.
- [guides/viewer.md](guides/viewer.md): a window on the robot the bridge drives.
- [guides/testing.md](guides/testing.md): unit tests on the fake, live tests with the shipped harness.
