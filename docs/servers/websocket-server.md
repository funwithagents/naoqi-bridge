# The WebSocket server

`naoqi-websocket-server` gives a client that isn't Python, or isn't MCP, network access to `NaoqiBridge` over a JSON WebSocket protocol: commands in, their results and the robot's live events (touch, joints, audio, camera frames, logs) out. A game engine, a web app or a custom agent loop drives the robot through it. Like the MCP server it holds no robot logic of its own; the full protocol, which this page summarizes, is in [specs/naoqi-websocket-server.md](../../specs/naoqi-websocket-server.md).

## Run it

One option, `--config`: a JSON file with the bridge's config under `bridge` and the server's under `server` ([../reference/configuration.md](../reference/configuration.md#server-configs-bridge--server)). The server streams to its client every stream the `bridge` block enables, touch always, so enable there what the client should receive.

```
uv run naoqi-websocket-server --config examples/configs/websocket-fake.json   # the fake, every stream on
uv run naoqi-websocket-server --config examples/configs/websocket-sim.json    # the simulator, started for you
uv run naoqi-websocket-server --config path/to/websocket-real.json            # your Nao: a copy with its address in bridge.robot.ip
```

```json
{
  "bridge": {
    "backend": "real",
    "robot": { "ip": "192.168.1.42" },
    "streams": {
      "joints": { "enabled": true, "period_s": 0.2 },
      "audio": { "enabled": true, "channel": "front" },
      "cameras": { "top": { "enabled": true, "resolution": "qvga", "fps": 10 } }
    }
  },
  "server": { "host": "", "port": 8002 }
}
```

The bridge connects at start; the server then listens on `server.host` and `server.port`. An empty `host`, the default, means the machine's LAN IP, so a client on another device can connect; the log line at start names the address. `"0.0.0.0"` binds every interface, `"127.0.0.1"` local clients only, port `0` lets the OS pick. The CLI runs until Enter is pressed. A config that doesn't load exits 2; a robot that can't be reached, or a sim that can't start, exits 1.

On the fake with every stream on, the server sends silent audio, camera frames of a test pattern and joints for all 26 joints at the angles of the fake's posture, so a client can be developed end to end with no robot.

## One client at a time

The server serves exactly one client. A new connection ends the previous session before its own starts. Each session has a ritual:

- **On connect**: the eyes turn cyan, the motors wake up, breathing starts on `Body`; the server sends `NaoqiState` and starts the client's streams.
- **On disconnect**: the streams stop, the eyes turn white, breathing stops, the robot rests.

A step that fails is logged (and mirrored to the client as a `Log`) and the session goes on.

## The protocol

Every message, both ways, is `{"id": "<message id>", "data": {…}}`. Payload keys are **camelCase**.

**Client to server**: one message, `Command`, with `data = {"commandUuid", "commandId", "commandData"}`. The uuid is the client's, echoed in the result. Each command runs as its own task, so a long one (`Dance`) doesn't block a later one (`StopDance`).

| `commandId` | `commandData` | Result `data` |
|---|---|---|
| `SetTTSLanguage` | `{"language"}` | — |
| `Say` / `StopSay` | `{"text"}` / `{}` | — |
| `WakeUp` / `Rest` / `StandUp` / `SitDown` | `{}` | — |
| `ChangeEyesColor` | `{"color"}` | — |
| `SetBreathingEnabled` | `{"enabled", "chainName"}` | — |
| `SetBasicAwarenessState` | `{"enabled", "engagementMode", "trackingMode"}` | — |
| `GetDanceBehaviors` / `GetBodyActionBehaviors` / `GetAppBehaviors` | `{}` | a list of `{"id", "behaviorName", "localizedName": {"en_US", "fr_FR"}, "description"}` |
| `GetExpressiveReactionTypes` | `{}` | a list of strings |
| `Dance` / `StopDance` | `{"danceId"}` | — |
| `ExpressiveReaction` / `StopExpressiveReaction` | `{"reactionType"}` | — |
| `BodyAction` / `StopBodyAction` | `{"bodyActionId"}` | — |
| `RunApp` / `StopApp` | `{"appId"}` | — |
| `RunBehavior` / `StopBehavior` | `{"name"}` | — |
| `GenericNao` | `{"text"}` | — (logged only) |

**Server to client**:

| `id` | `data` | When |
|---|---|---|
| `NaoqiState` | `{"protocolVersion": 2, "connected": true, "fakeRobot": false}` | First message of every session |
| `CommandEnded` | `{"commandUuid", "resultType": "Success" \| "Error", "message", "data"}` | When a command ends. `message` is empty on success and the reason on error: the bridge's own message (the motors are off, an unknown dance and the known ones, Naoqi's error), or a note on a malformed command. `data` is the result above, or `null` |
| `Touch` | `{"part", "touched"}` | A head sensor changed; always on |
| `Joints` | `{"jointsNames", "jointsAngles"}` | Every `streams.joints.period_s`, radians |
| `Audio` | `{"rate", "channels", "nbSamplesPerChannel", "data"}` | One per microphone chunk; `data` is base64 int16 LE PCM |
| `Frame` | `{"camera", "frameId", "width", "height", "format": "jpeg", "data", "cameraTransform", "fov"}` | One per frame of each enabled camera; `data` is a base64 JPEG (quality 80, 10 to 20 KB at QVGA), `cameraTransform` 16 floats (row-major 4×4, camera to the robot frame), `fov` `[horizontal, vertical]` in radians |
| `Log` | `{"log", "logLevel"}` | The session's own log lines: the connection, each command's start and result, bad input |

Joints and frames are latest-wins: a slow connection skips samples and frames rather than lagging. Audio is every chunk. A message that isn't JSON, isn't the envelope or names an unknown command is answered with an `ERROR` `Log` and the session continues; only the connection closing ends it.

**The version.** `protocolVersion` is bumped on an incompatible change only (a message, command or field removed, renamed or changed in meaning); additions keep it, so a client ignores ids and fields it doesn't know and checks the version on `NaoqiState`. Version 2 renamed the first message from `NaoState` to `NaoqiState`; nothing else changed since 1.

## An exchange

A Python client with the `websockets` package, against the fake server above:

```python
import asyncio
import json

import websockets


async def main() -> None:
    async with websockets.connect("ws://127.0.0.1:8002") as ws:
        print(json.loads(await ws.recv()))  # NaoqiState: the protocol version, fakeRobot
        command = {"commandUuid": "1", "commandId": "Say", "commandData": {"text": "Hello"}}
        await ws.send(json.dumps({"id": "Command", "data": command}))
        async for raw in ws:  # Touch, Joints, Audio and Frame messages interleave
            message = json.loads(raw)
            if message["id"] == "CommandEnded":
                print(message["data"])
                break


asyncio.run(main())
```

```
{'protocolVersion': 2, 'connected': True, 'fakeRobot': True}
{'commandUuid': '1', 'resultType': 'Success', 'message': '', 'data': None}
```

A `Dance` on a robot at rest comes back as `{"resultType": "Error", "message": "dance: the motors are off; call wake_up() first", …}`; a `Dance` with a wrong id, as `"unknown dance 'macarena' (known: …)"`.
