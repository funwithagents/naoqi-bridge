# The simulator: naoqi-sim

The `sim` backend runs [naoqi-sim](https://github.com/funwithagents/naoqi-sim): Aldebaran's own NAOqi, the software every one of their robots runs, in a local Docker container, with the robot's devices replaced by your machine's (the loudspeaker, the microphone, a camera rendered from a 3D scene or your webcam) and a window showing the robot. Today the simulated robot is a Nao; a Pepper could follow, since NAOqi is the same software. The bridge reaches it over `qi` exactly as it reaches a robot, so everything on this side runs unchanged: the verbs, the catalog, the streams, both servers. What the backend adds is **starting and stopping the sim with the bridge**, from the config, and knowing the sim is the NAOqi version asked for. The design is in [specs/sim.md](../../specs/sim.md).

Two NAOqi versions are available: **2.1** (2.1.4.13, the version a Nao v5 runs) and **2.8** (2.8.7.4, a Nao v6's and a Pepper's, shown with the Nao v6 model in the window). Both run in the bridge's CI on every change.

## Install

The `[sim]` extra, Docker (Docker Desktop on macOS and Windows), and once per machine the images, built from Aldebaran's public downloads:

```
uv add "naoqi-bridge[sim] @ git+https://github.com/funwithagents/naoqi-bridge"   # or uv sync --dev in a checkout
uv run naoqi-sim fetch-and-build-images        # both versions; or: … 2.1 / … 2.8
uv run naoqi-viewer fetch-meshes               # optional: Aldebaran's meshes in the window, after a license prompt
```

The build fetches the Choregraphe suite of each version and the `animations` package, hash-checked, and keeps them in the user data folder (about 1.8 GB for both versions, plus the Docker images; the 2.8 image is by far the larger). The bridge never builds images itself: a missing or outdated one fails `start()` with naoqi-sim's message, which names the command. The extra exists where `qi` does (macOS arm64, Linux x86_64, Windows x64).

## Start it with the bridge, or borrow it

```json
{
  "backend": "sim",
  "sim": {
    "spawn": "auto",
    "config": { "naoqi": { "version": "2.1" } }
  }
}
```

`sim.config` is a naoqi-sim config as it is: paste one in, copy it back out to `naoqi-sim run --config`, unchanged. `naoqi.version` picks `"2.1"` or `"2.8"`; the rest sets the sim's devices and window ([naoqi-sim's config](https://github.com/funwithagents/naoqi-sim)):

| Block | Sets | For example |
|---|---|---|
| `viewer` | The sim's window, or none | `{"headless": true}` for a server or a test |
| `audio_output` | Where the robot's voice goes | `{"mode": "silent"}`; a recording to a WAV file |
| `audio_input` | What the robot hears | `{"source": "mic"}`, your microphone; `"fake"`, silence plus what a test plays into it |
| `video_input` | What the cameras see | the rendered scene (the default for the top camera); `{"top": {"source": "webcam", "device": 0}}` |
| `speech` | The speech engine | its voice and rate |

`spawn` says who owns the sim:

| `spawn` | A sim already runs on this machine | None runs |
|---|---|---|
| `auto` (default) | borrow it, leave it running on exit | start one, stop it on exit |
| `always` | `RobotConnectionError` | start one, stop it on exit |
| `never` | borrow it | `RobotConnectionError`, naming `naoqi-sim run` |

A borrowed sim must be the version `naoqi.version` asks for, or `start()` fails naming both; the bridge never drives another version than the config says. The device settings of `sim.config` apply only to a sim the bridge starts: a borrowed one runs as whoever started it set it up. One sim runs per machine (it publishes port 9559).

Starting a sim takes the container's boot: about 5 s on 2.1, 15 s on 2.8, after Docker has the images. Stopping the bridge then takes the few seconds of `docker compose down`; the package store volumes stay, so a package installed into the sim survives.

**Run it by hand**, to be borrowed across several bridge sessions, or to watch it while a server runs:

```
uv run naoqi-sim run                                           # NAOqi 2.1, the window, speech on the loudspeaker; Ctrl-C stops it
uv run naoqi-sim run --config examples/configs/2.8.json        # in a naoqi-sim checkout: NAOqi 2.8
uv run naoqi-sim status                                        # the containers and the robot's state
uv run naoqi-sim logs --follow
uv run naoqi-sim cleanup                                       # after a run that died without stopping
```

The servers take the same `sim` block: `examples/configs/mcp-sim.json` and `websocket-sim.json` run the 2.1 sim with naoqi-sim's defaults, `spawn: "auto"`.

## What a sim offers

A sim is a desktop NAOqi with naoqi-sim's replacements for the devices it lacks, driving a simulated Nao. From the bridge's side ([../reference/backends.md](../reference/backends.md) has the full matrix):

- **Speech, language, postures, motors, breathing, eyes, basic awareness**: as on a robot, the voice through naoqi-sim's engine.
- **Joints and posture**: NAOqi's own model of the body, reported as on a robot. The posture families differ by version: Crouch is `Standing` on 2.1 and `Crouching` on 2.8.
- **Audio**: the configured source, every chunk; `audio_input.source: "fake"` lets a test play a WAV file into the robot's ears through naoqi-sim's API ([testing.md](testing.md)).
- **Cameras**: the top camera, rendered from the scene the window shows, or your webcam.
- **Touch**: not yet. naoqi-sim's touch input isn't built, so `on_touch` stays silent on a sim.
- **The catalog**: the `animations` package only, so the expressive reactions (`Happy`, `Proud`, `Laugh`, `Sad`) and nothing else: no dances, no apps, no body actions, no `HeadTouched`. Aldebaran's packages are a robot owner's own.
- **Sit on 2.8**: the 2.8 desktop suite has no inertial sensor, and its posture manager won't go from Stand to Sit; the bridge sits a 2.8 sim through Crouch, which works and takes 15 to 25 s. A 2.8 robot has the sensor and is expected to sit directly.

## When it doesn't start

`start()` raises `RobotConnectionError` with naoqi-sim's message, which says what to do; the servers' CLIs exit 1 on it.

| Message says | Do |
|---|---|
| Docker isn't running or isn't installed | start Docker Desktop, or install Docker |
| images missing or outdated | `uv run naoqi-sim fetch-and-build-images` (again, after naoqi-sim moved) |
| port 9559 in use, not a naoqi-sim | stop what listens there (a Choregraphe virtual robot, say); `uv run naoqi-sim cleanup` for a dead sim |
| a sim already runs, `spawn: "always"` | use `auto` to borrow it, or stop it |
| no sim to borrow, `spawn: "never"` | `uv run naoqi-sim run`, or `auto` |
| the running sim is NAOqi 2.8, the config asks for 2.1 | change `naoqi.version`, or stop the sim |
| `backend: "sim"` needs `naoqi-bridge[sim]` (a `ConfigError`, at load) | install the extra, on a platform with `qi` |
