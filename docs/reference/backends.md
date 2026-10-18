# Backends

What each way of running the bridge needs, what it gives you, and how far it has been validated. One matrix; the other pages link here rather than repeating it.

## The three backends

| Backend | What it drives | Needs |
|---|---|---|
| `fake` (default) | A first-party, in-process stand-in: it records every command, serves a fixed catalog, keeps the real timing of speech, moves and behaviors, and answers the streams with synthetic data | Nothing: no robot, no `qi`, no Docker. It runs on every platform and powers the bridge's fast tests and yours |
| `sim` | [naoqi-sim](https://github.com/funwithagents/naoqi-sim): Aldebaran's own NAOqi, 2.1 or 2.8, in a local Docker container, with the robot's devices replaced by the machine's (loudspeaker, microphone, a rendered camera), reached over `qi` like a robot | The `[sim]` extra, Docker, the images built once (`uv run naoqi-sim fetch-and-build-images`), a platform with a `qi` wheel. [The simulator](../guides/simulator.md) |
| `real` | A Nao on the network, over a `qi` session | `robot.ip`, a platform with a `qi` wheel |

The same code runs on all three; `backend` in the config is the whole switch ([configuration.md](configuration.md#backend)). A `real` backend that can't reach the robot, or a platform without `qi`, fails loudly with `RobotConnectionError`: the bridge never falls back to the fake on its own.

## Platforms

`qi`, the Naoqi client library, is a compiled wheel from the [funwithagents/libqi-python](https://github.com/funwithagents/libqi-python) fork's package index. It exists for CPython 3.12 and 3.13 on:

| Platform | `qi` | Backends |
|---|---|---|
| macOS arm64, Linux x86_64, Windows x64 | installed with the package | `fake`, `sim`, `real` |
| macOS Intel, Linux arm64, Windows arm64 | no wheel | `fake` only |

The sim also needs Docker (Docker Desktop on macOS and Windows). The viewer and the sim's window need a display, and on macOS `mjpython`, which comes with `mujoco`. CI runs the fast tier on Linux, macOS and Windows and the live tier on Linux, on a headless sim of each version ([../../specs/ci.md](../../specs/ci.md)).

## The matrix

What each target offers the bridge. The sim columns are a headless sim with naoqi-sim's `fake` audio input and a rendered top camera, which is what the bridge's live tier runs on; a sim you start yourself holds what its config gives it ([../guides/simulator.md](../guides/simulator.md)). The robot columns are a stock Nao with Aldebaran's packages installed.

| | `fake` | sim, NAOqi 2.1 | sim, NAOqi 2.8 | Nao v5, NAOqi 2.1.4.13 | Nao v6, NAOqi 2.8 |
|---|---|---|---|---|---|
| Speech, language, eyes, breathing, basic awareness | recorded | as on a robot; speech through naoqi-sim's engine | same | ✅ | expected |
| Motors, stand, sit, rest | recorded; a posture move takes 2 s | ✅ | ✅; **Sit goes through Crouch**, 15 to 25 s, because the 2.8 desktop suite has no inertial sensor | ✅; `rest` from Sit stays seated | expected |
| Dances, apps, body actions | a fixed catalog | ❌ the sim has the `animations` package only | ❌ | ✅ the robot's packages (9 dances, 8 apps, 6 body actions on the tested robot) | the robot's packages |
| Expressive reactions | `Happy`, `Proud`, `Laugh`, `Sad`, `HeadTouched` | from `animations`: no `HeadTouched` | same | ✅ | expected |
| Touch | simulated in tests (`bridge.robot.touch(...)`) | ❌ not built in naoqi-sim yet | ❌ | ✅ | expected |
| Posture | the posture it is in | ✅ Naoqi's; Crouch is in the `Standing` family | ✅; Crouch is in `Crouching` | ✅ | expected |
| Joints | all 26, at the angles of its posture | ✅ NAOqi's own body model | ✅ | ✅ | expected |
| Microphone | silence, 1360-sample chunks | ✅ naoqi-sim's `fake` source, or your microphone (`audio_input.source: "mic"`) | ✅ | ✅ 1365-sample chunks (85 ms) on every channel | expected |
| Cameras | a test pattern, both cameras | the top camera, rendered from the sim's scene (or your webcam) | same | ✅ both, with the Nao v5 field of view | expected |
| Viewer | ❌ nothing to mirror (skipped with a warning) | ✅ | ✅ | ✅ | expected |
| Validated | CI, the fast tier on Linux, macOS and Windows | CI, the live tier | CI, the live tier | every live test, run by the author on 2026-10-16 ([analysis](../../analysis/202610161840_not-yet-tested-on-a-robot.md)) | **untested**: the author has no Nao v6. The code paths are the 2.1 ones plus what the 2.8 sim needed; a report of what works and what doesn't is the most useful thing you can send |

Read a ❌ as "the live tests that need it skip": a test gates on the capability it needs, never on the target ([../guides/testing.md](../guides/testing.md)).

## What the robot taught us

Measured on the Nao v5, through the bridge:

- **The camera needs a wired link for 10 fps.** Over Wi-Fi, a QVGA frame takes about 200 ms to pull and the bridge gets 1 to 3 fps; over Ethernet it holds 10 fps on both cameras at once. VGA is 4 to 5 fps wired. Ask for `qvga` unless the link is wired.
- **Cancels are quick.** A cancelled `say` is silent within about 0.5 s, a dance stops within 1 to 3 s, a posture move within about 3 s, all under the bridge's 4 s bound. Stopping an *app* can take longer: Naoqi's `stopBehavior` blocks until the app ends, about 10 s for `presentation`.
- **Two `say` calls queue.** The second waits for the first and speaks after it; one stop silences both.
- **`rest` depends on where the robot is.** From Stand it crouches; from Sit it relaxes in place and the posture stays `Sit`. A 2.1 sim crouches from both, and so does the fake.
- **Posture mid-move is a guess.** During a stand-up Naoqi reports whatever posture is nearest, `SitOnChair`, `LyingBack`, `StandInit`; wait for `bridge.posture.value.moving` to be false for a settled one.

## NAOqi versions

The bridge runs the same code on NAOqi 2.1 and 2.8, with two version-specific points inside the robot layer: speech is stopped through a method both versions have but 2.8 needs (its `say` would otherwise wait for the current gesture), and a 2.8 *sim* sits through Crouch (above). Both are exercised by the live tier on both sims in CI. A 2.8 robot has the inertial sensor the desktop suite lacks, so it is expected to sit directly; nobody has checked. Pepper runs NAOqi too and is in principle a target; nothing has been tried on one.
