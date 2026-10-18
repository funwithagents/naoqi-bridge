# Configuration reference: `NaoqiBridgeConfig`

Every field of the bridge's config, its default and what it does; then the two server configs that wrap it, and the CLIs. This is the consumer's home for the config; the design and the validation rules are in [specs/config.md](../../specs/config.md). The ready-made files in [examples/configs/](../../examples/configs/) are server configs, one per setup.

`NaoqiBridgeConfig` is one declarative object, built from a dict, a JSON string or a JSON file: `NaoqiBridge.from_dict(...)`, `.from_json(...)` and `.from_json_file(...)` take the same input and build the bridge; `NaoqiBridgeConfig.from_dict(...)` and friends build the config alone. `NaoqiBridge("fake")` is the shorthand for a config with everything at its default. **Every block is optional**: `NaoqiBridgeConfig()` is valid, and is the offline fake with no streams.

```json
{
  "backend": "real",
  "robot": { "ip": "192.168.1.42", "port": 9559, "connect_timeout_s": 5.0 },
  "streams": {
    "joints": { "enabled": false, "period_s": 0.2 },
    "audio": { "enabled": false, "channel": "front" },
    "cameras": {
      "top": { "enabled": false, "resolution": "qvga", "fps": 10 },
      "bottom": { "enabled": false, "resolution": "qvga", "fps": 10 }
    }
  },
  "sim": {
    "spawn": "auto",
    "config": { "naoqi": { "version": "2.1" } }
  },
  "viewer": { "enabled": false, "config": { "ghost": true } }
}
```

That is every field, at its default except `backend` and `robot.ip`. A malformed config fails when it loads with a `ConfigError` naming the key path (`streams.joints.period_s must be a positive, finite number`). Unknown keys are errors, so a typo never passes silently.

## `backend`

`"fake"` (default), `"real"` or `"sim"`; see [backends.md](backends.md). Changing this one string moves a config between the fake, a robot and the simulator: every other block is checked on every backend and applied only where it means something, so one file serves the three. `"real"` needs `robot.ip`; `"sim"` needs the `[sim]` extra installed, or the config fails to load naming it.

## `robot`: how to reach the robot

| Field | Default | What it does |
|---|---|---|
| `ip` | `""` | The robot's address. Required on `real`; the robot says it when you press its chest button |
| `port` | `9559` | Naoqi's port |
| `connect_timeout_s` | `5.0` | How long the one connection attempt may take. A wrong address or a robot that is off fails within this time with `RobotConnectionError`, instead of waiting for the OS's TCP timeout |

On `fake`, the block is checked and ignored. On `sim`, `ip` and `port` are ignored (the sim is at naoqi-sim's fixed address, `127.0.0.1:9559`) and `connect_timeout_s` applies to the connection to it.

## `streams`: what the bridge subscribes to on the robot

The streams that cost the robot something are off by default and subscribed at `start()` only when enabled here; using a disabled stream's API raises `BridgeError`. Touch and posture have no switch: they are a few event subscriptions that cost nothing, so they are always on ([api.md](api.md#streams)).

| Field | Default | What it does |
|---|---|---|
| `joints.enabled` | `false` | Sample the joint angles into `bridge.joints` |
| `joints.period_s` | `0.2` | The sampling period, a positive number of seconds |
| `audio.enabled` | `false` | Subscribe to the microphone, for `bridge.audio_input()` |
| `audio.channel` | `"front"` | Which microphone: `front`, `rear`, `left` or `right`; mono at 16 kHz either way |
| `cameras.top`, `cameras.bottom` | both off | One block per camera: `enabled`, `resolution` (`qqvga` 160×120, `qvga` 320×240, `vga` 640×480, `4vga` 1280×960), `fps` (1 to 30) |

A camera's `fps` is the rate the bridge pulls frames at, and a ceiling: over Wi-Fi a Nao v5 delivers QVGA at a few frames a second, over Ethernet at the asked 10 ([backends.md](backends.md)).

## `sim`: the simulator

Applies on `backend: "sim"` only; checked and ignored elsewhere ([../guides/simulator.md](../guides/simulator.md)).

| Field | Default | What it does |
|---|---|---|
| `spawn` | `"auto"` | `auto`: borrow the sim already running on this machine, else start one and stop it with the bridge. `never`: borrow only; none running is an error. `always`: start one; one already running is an error |
| `config` | naoqi-sim's defaults | A [naoqi-sim](https://github.com/funwithagents/naoqi-sim) config, as its own config file holds it: `naoqi.version` (`"2.1"` or `"2.8"`), `viewer` (the sim's window, `headless`), `audio_output` (the loudspeaker, `silent`, a recording), `audio_input` (your microphone, or a `fake` source tests play into), `video_input` (the cameras' sources), `speech`. Its keys and rules are naoqi-sim's; an error there is a `ConfigError` under `sim.config.` |

A borrowed sim must be the version `config.naoqi.version` asks for, or `start()` fails naming both. The device settings of `config` apply to a sim the bridge starts; a borrowed one runs as whoever started it set it up.

## `viewer`: a window on the robot

A [naoqi-viewer](https://github.com/funwithagents/naoqi-viewer) window mirroring the robot the bridge drives, opened at `start()` and closed at `stop()` ([../guides/viewer.md](../guides/viewer.md)). Needs the `[viewer]` extra (the `[sim]` extra brings it) and a display.

| Field | Default | What it does |
|---|---|---|
| `enabled` | `false` | Open the window with the session. On `fake` there is nothing to mirror, and a sim the bridge started with its own window is already on screen: both cases are skipped with a warning |
| `config` | naoqi-viewer's defaults | A naoqi-viewer config: `ghost` (the commanded pose drawn next to the measured one), `world.scene`, `world.variant` (`placeholder`, or `aldebaran` after `naoqi-viewer fetch-meshes`; `auto` picks the meshes when installed), `naoqi.rate_hz`, `launch_timeout_s`. `mode`, `headless` and `naoqi.url` are set by the bridge and refused here |

## Server configs: `{"bridge": …, "server": …}`

Each server wraps the bridge's config under `bridge`, next to its own settings under `server`. Both blocks are optional and follow the same loading and `ConfigError` rules; the `bridge` block is exactly a `NaoqiBridgeConfig`, so it copies between files.

**[MCP server](../servers/mcp-server.md)**, `NaoqiMcpServerConfig`:

| Field | Default | What it does |
|---|---|---|
| `server.transport` | `"stdio"` | `stdio` for a client that launches the server as a subprocess (the usual case), `sse` to serve over HTTP at FastMCP's default address |

MCP is request and response, so its bridge normally enables no stream.

**[WebSocket server](../servers/websocket-server.md)**, `NaoqiWebsocketServerConfig`:

| Field | Default | What it does |
|---|---|---|
| `server.host` | `""` | The address to bind. Empty means the machine's LAN IP, found at start (`127.0.0.1` when there is no route out); `"0.0.0.0"` every interface; `"127.0.0.1"` local clients only |
| `server.port` | `8002` | The port; `0` lets the OS pick one |

The server streams to its client every stream the `bridge` block enables, touch always: enable in `bridge.streams` what the client should receive.

## The CLIs

```
uv run naoqi-mcp-server --config path/to/mcp.json
uv run naoqi-websocket-server --config path/to/websocket.json
```

`--config` is the only option; without it each server runs on its default config, the fake (over stdio, or on port 8002). A config that fails to load exits 2 with the `ConfigError` message; a robot that can't be reached, a sim that can't be started or borrowed, or a viewer that can't launch exits 1. The modules run as scripts too: `python -m naoqi_bridge.naoqi_mcp_server`, `python -m naoqi_bridge.naoqi_websocket_server`.

## The example files

[examples/configs/](../../examples/configs/) holds six server configs, kept in sync with the spec: `mcp-fake.json`, `mcp-real.json`, `mcp-sim.json`, `websocket-fake.json`, `websocket-real.json`, `websocket-sim.json`. The `real` files need `robot.ip` edited and carry a disabled `viewer` block; the `websocket-*` files enable joints, audio and the top camera; the `sim` files run NAOqi 2.1 with naoqi-sim's defaults (the sim window, speech on the loudspeaker), `spawn: "auto"`. Change `"version"` to `"2.8"` for a Nao v6's NAOqi.
