# naoqi-bridge

A Python library that sits between a robot running [Naoqi](https://www.aldebaran.com/en), Aldebaran's robot OS, and whatever drives it: a script, a service, or an LLM agent. It hides Naoqi's `qi` session and services behind one async, intent-level API, `NaoqiBridge`, whose verbs speak in human terms (*say this, stand up, dance, react, run that app*) and whose streams bring the robot's touch, posture, joints, microphone and cameras back out. Two thin servers expose that one object to other clients, an **MCP server** for LLM agents and a **JSON WebSocket server** for custom applications. The same code runs unchanged on a real robot, on a simulated one the bridge starts itself (Aldebaran's NAOqi in Docker), or on an offline fake. It has been built and verified on a Nao; in principle it drives any Naoqi robot, a Pepper included.

**Start here:** [docs/getting-started.md](docs/getting-started.md), your first application on the offline fake, then on a simulated or a real robot; [docs/index.md](docs/index.md), the documentation by task. The [quick start](#quick-start) below is the shortest program; [what the bridge gives you](#what-the-bridge-gives-you) is the feature list.

## Project status

> [!WARNING]
> - **Under development: the API may change.** The bridge is at version 0.1 and is shaped as it is used. Methods, config fields and module layout can change between commits, without a deprecation period. If you depend on it, pin a commit (`naoqi-bridge @ git+https://github.com/funwithagents/naoqi-bridge@<sha>`).
> - **Verified on a Nao v5 running NAOqi 2.1.4.13, and on simulated Naoqi robots running NAOqi 2.1 and 2.8.** Every live test has run on that robot, and the live tier runs on both simulated versions in CI on every change. A **Nao v6** (NAOqi 2.8) or a **Pepper** has never been tried: the code paths are the 2.1 ones plus what the 2.8 simulator needed, and nothing more is guaranteed. If you have one, a report of what works and what doesn't is the most useful thing you can send.

> [!TIP]
> **Feedback is welcome: open an issue.** Bug reports, questions, and what you would want the API or the config to do differently all go to [the issue tracker](https://github.com/funwithagents/naoqi-bridge/issues). The project is developed by one person and is not taking pull requests yet; [CONTRIBUTING.md](CONTRIBUTING.md) says why and how to help anyway.

## Install

Python 3.12 or 3.13. The package is not on PyPI yet; add it from its git URL, or from a local checkout:

```
uv add "naoqi-bridge @ git+https://github.com/funwithagents/naoqi-bridge"
uv add "naoqi-bridge[sim,test] @ git+https://github.com/funwithagents/naoqi-bridge"
uv add "naoqi-bridge[sim,test] @ ../naoqi-bridge"   # a checkout next door
```

| Extra | Adds | You need it for |
|---|---|---|
| *(none)* | `qi` (where a wheel exists), `mcp`, `websockets`, `numpy`, `Pillow` | The `real` backend, the offline `fake`, both servers |
| `sim` | `naoqi-sim[viewer]`, from its git pin | The `sim` backend: a simulated Naoqi robot, NAOqi 2.1 or 2.8, in Docker ([docs/guides/simulator.md](docs/guides/simulator.md)). Brings the viewer too |
| `viewer` | `naoqi-viewer`, from its git pin | A window mirroring the robot the bridge drives ([docs/guides/viewer.md](docs/guides/viewer.md)) |
| `test` | `pytest` | The shipped `naoqi_bridge.testing` harness for your live tests ([docs/guides/testing.md](docs/guides/testing.md)) |

`uv` resolves the bridge's sources for you: `qi` comes from the [funwithagents/libqi-python](https://github.com/funwithagents/libqi-python) fork's package index (PyPI's `qi` is Aldebaran's older 3.1.5, which this project does not use), naoqi-sim and naoqi-viewer from GitHub. With pip, add `--extra-index-url https://funwithagents.github.io/libqi-python/simple/` for `qi`; the `sim` and `viewer` extras are uv-only, since pip ignores git sources.

**Platforms.** `qi` is a compiled wheel, available for macOS arm64, Linux x86_64 and Windows x64. There, `uv add` installs it and all three backends run. On macOS Intel, Linux arm64 and Windows arm64 there is no wheel: the package installs, the `fake` backend runs, and `real` or `sim` fail with an explicit error, never a silent fallback. The sim needs Docker as well. Developed on macOS; CI runs the fast tests on Linux, macOS and Windows and the live tests on Linux against a headless simulator of each NAOqi version. The one table of what each backend needs and gives is [docs/reference/backends.md](docs/reference/backends.md).

In a checkout, `uv sync --dev` installs everything, extras included, and the `naoqi-mcp-server` and `naoqi-websocket-server` commands.

## Quick start

Everything goes through `NaoqiBridge`, used as an async context manager. Nothing connects until you enter it; leaving it tears everything down. The `fake` backend needs no robot, no Docker and no extra:

```python
import asyncio

from naoqi_bridge import NaoqiBridge


async def main() -> None:
    async with NaoqiBridge("fake") as bridge:  # "fake": the offline stand-in
        await bridge.wake_up()  # motors on: the verbs that move the body need it
        await bridge.say("Hello, I am Nao.")  # returns once spoken
        dances = bridge.get_dance_behaviors()  # what this robot has installed
        print([dance.id for dance in dances])
        await bridge.dance(dances[0].id)  # returns when the dance ends; cancel the task to stop it
        await bridge.rest()


asyncio.run(main())
```

To drive a Naoqi, build the bridge from a config instead ([docs/reference/configuration.md](docs/reference/configuration.md)): `"backend": "real"` with the robot's address, or `"backend": "sim"` for a simulated robot the bridge starts for you.

```python
async with NaoqiBridge.from_dict({"backend": "real", "robot": {"ip": "192.168.1.42"}}) as bridge:
    await bridge.say("Hello")  # the same program, on the robot
```

`from_json(...)` and `from_json_file(...)` take the same config as a JSON string or file. The complete first application, with the streams, the lifecycle and an agent's tools, continues in [docs/getting-started.md](docs/getting-started.md).

## What the bridge gives you

`qi` gives full, low-level access to Naoqi's services, and the bridge keeps it: `bridge.robot` is the connected robot. On top of it, the bridge adds what an interactive application otherwise builds itself, one feature per row.

| Feature | What you get |
|---|---|
| **One async API in human terms** | A small set of `async` verbs: speech (`say`, `set_tts_language`), motors and postures (`wake_up`, `rest`, `stand_up`, `sit_down`), the eyes, breathing, basic awareness, any installed behavior by name; the same code on a robot, a simulator and an offline fake |
| **A catalog of what's installed** | The robot's packages classified into dances, expressive reactions (`Happy`, `Proud`, `Laugh`, `Sad`, `HeadTouched`), body actions and apps, each with an id, its names and description; `dance(id)`, `expressive_reaction(type)`, `body_action(id)`, `run_app(id)` play them and `current_*` says what is playing |
| **Failures that say why** | A verb returns `None` or raises a typed error with a message an agent can act on: `MotorsOffError` (call `wake_up`), `ValueError` naming the known ids, `CommandFailedError` with Naoqi's error chained. Never a `bool` |
| **Everything is cancellable** | Cancel the task awaiting `say`, a posture move, a dance or any behavior and the robot has stopped by the time the `CancelledError` reaches you, in bounded time, with the session ready for the next verb |
| **Touch** | `on_touch` fires a `TouchEvent` for each of the head's tactile sensors, pressed or released, on your event loop. Always on, no config needed |
| **Posture** | `posture` holds what Naoqi says the robot's posture is (`Stand`, `Sit`, `Crouch`, …) and whether a bridge verb is moving it and where to, so a program waits for a settled posture instead of guessing. Always on, no config needed |
| **Joints** | `joints` holds the latest joint angles, sampled at the configured period: read it, wait for a condition, or follow its changes |
| **Microphone** | `audio_input()` yields the microphone as int16 mono PCM at 16 kHz, to as many listeners as you start, each receiving the whole stream, with a pre-roll into the recent past for a recognizer woken by a wake word |
| **Cameras** | `cameras["top"]` and `["bottom"]` hold the newest frame of each camera: BGR pixels (a numpy view), Naoqi's timestamp, the camera's pose in the robot frame and its field of view; sample it or follow it, latest-wins |
| **One JSON configuration** | Backend, robot address, streams, simulator and viewer in one file, checked when it loads with the offending key named; changing `backend` moves it between the robot, the simulator and the fake |
| **A simulated robot** | `"backend": "sim"` runs Aldebaran's own NAOqi, 2.1 or 2.8, in a local Docker container through [naoqi-sim](https://github.com/funwithagents/naoqi-sim), with your loudspeaker, microphone and a rendered camera; the bridge starts it and stops it, or borrows the one you run |
| **A window on the robot** | `"viewer": {"enabled": true}` opens a [naoqi-viewer](https://github.com/funwithagents/naoqi-viewer) window mirroring the robot the bridge drives, the commanded pose as a ghost if you ask |
| **An MCP server** | `naoqi-mcp-server`: the verbs as tools for an LLM agent, behaviors that return once started so the agent can still stop them, failures as readable answers ([docs/servers/mcp-server.md](docs/servers/mcp-server.md)) |
| **A WebSocket server** | `naoqi-websocket-server`: a JSON protocol for a game engine, a web app or another language: commands in, results and touch, joints, audio and JPEG camera frames out ([docs/servers/websocket-server.md](docs/servers/websocket-server.md)) |
| **Testing, unit and live** | The `fake` backend records every command and keeps real timing, for unit tests with no robot. A shipped pytest harness runs live tests against the simulator or a robot, probes what the target can do and skips instead of failing |

## The servers

Both servers run from one config file with the bridge's config under `bridge` and theirs under `server`; ready-made files for the fake, the simulator and a robot are in [examples/configs/](examples/configs/).

**MCP server** ([docs/servers/mcp-server.md](docs/servers/mcp-server.md)). An LLM agent drives the robot by calling tools: `say`, `wake_up`, `stand_up`, `get_dance_list` then `dance`, `expressive_reaction`, `run_app`, `get_running`, each `stop_*`. Plug it into any MCP client as a stdio server launched through `uv`; the page has the generic recipe and a Claude Desktop example.

```
uv run naoqi-mcp-server --config examples/configs/mcp-sim.json
```

**WebSocket server** ([docs/servers/websocket-server.md](docs/servers/websocket-server.md)). A client sends `{"id": "Command", "data": {"commandUuid", "commandId": "Say", "commandData": {"text": "Hello"}}}` and receives a `CommandEnded` with the result or the reason it failed, while `Touch`, `Joints`, `Audio` and `Frame` messages stream the robot's data. One client at a time.

```
uv run naoqi-websocket-server --config examples/configs/websocket-fake.json
```

## Documentation

Start at [docs/index.md](docs/index.md), the documentation by task. The pages a consumer uses most:

| | |
|---|---|
| [docs/getting-started.md](docs/getting-started.md) | Your first application, on the fake, then on a sim or a robot; the lifecycle; the streams; driving it from an agent |
| [docs/reference/api.md](docs/reference/api.md) | Every verb, value and error; the catalog; the streams; cancellation |
| [docs/reference/configuration.md](docs/reference/configuration.md) | Every config field and its default; the server configs; the CLIs |
| [docs/reference/backends.md](docs/reference/backends.md) | The fake, the sim on 2.1 and 2.8, a Nao v5 and a Nao v6: what each offers, how far each is validated |
| [docs/servers/](docs/servers/) | The MCP server and the WebSocket server |
| [docs/guides/](docs/index.md#by-task) | The simulator, the viewer, testing your project |
| [examples/configs/](examples/configs/) | A server config per setup |

## How it is developed

The bridge is a spec-driven project: every feature is designed before it is coded, pinned by tests at two levels, and checked by CI on every change.

- **Specs first.** Each concept has one spec under [specs/](specs/_index.md), the normative design with its rationale and open questions; [specs/_overview.md](specs/_overview.md) is the architecture. Each spec names the code and test files it governs, and a test keeps that map and the statuses honest.
- **Fast tests on the fake.** `tests/` covers the bridge and both servers against the offline `fake`, and the robot layer against a stub `qi`: no robot, no Docker, no network, deterministic.
- **Live tests on a Naoqi.** `tests-e2e/` runs the verbs, the streams, cancellation and both servers against a simulated Naoqi robot, headless or in its window, or a real one, through the shipped harness; each test declares the capabilities it needs and skips where the target lacks them.
- **CI on every change.** Lint, format and types; the fast tier on Linux, macOS and Windows, each with its own `qi` wheel; and the live tier on a headless simulator of each NAOqi version, 2.1 and 2.8, whose images the runner builds and caches itself ([specs/ci.md](specs/ci.md)).
- **[AGENTS.md](AGENTS.md) is the operating manual** for anyone, or any coding agent, working in the repo: the project map, the verification gate, how the specs and plans are kept in step with the code.

The same gate, locally:

```
uv sync --dev
uv run ruff check .
uv run ruff format .
uv run pyright
uv run pytest                 # the fast tier, offline
uv run pytest tests-e2e -rs   # the live tier, on a simulator the harness starts (Docker, the images built once)
```

## License

MIT, see [LICENSE](LICENSE).
