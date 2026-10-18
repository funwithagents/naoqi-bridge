# Documentation

The bridge's documentation, by what you want to do. The [README](../README.md) is the landing page: what the bridge is, its status, how to install it and the first program; [getting-started.md](getting-started.md) continues from there.

## By task

| I want to… | Read |
|---|---|
| write my first application | [getting-started.md](getting-started.md): a complete program on the offline fake, then the config that moves it to a simulated or a real Nao |
| connect a robot, or run a simulated one | [reference/backends.md](reference/backends.md): what each backend needs and gives; [guides/simulator.md](guides/simulator.md): naoqi-sim, its two NAOqi versions, starting or borrowing it; [examples/configs/](../examples/configs/): a ready-made server config per setup |
| watch what the robot does | [guides/viewer.md](guides/viewer.md): a window mirroring the robot the bridge drives |
| drive the robot from an LLM agent | [servers/mcp-server.md](servers/mcp-server.md): the MCP server, its tools, and how to plug it into an MCP client |
| drive the robot from a game engine, a web app or another language | [servers/websocket-server.md](servers/websocket-server.md): the JSON WebSocket protocol, commands in and events out |
| react to touch, read the posture or the joints, hear the microphone, see the cameras | [getting-started.md](getting-started.md#the-streams) and [reference/api.md](reference/api.md#streams) |
| test my project against the bridge | [guides/testing.md](guides/testing.md): unit tests on the fake, live tests on a sim or a robot with the shipped pytest harness |
| look up a verb, a value, an error or a contract | [reference/api.md](reference/api.md) |
| look up a config field | [reference/configuration.md](reference/configuration.md) |

## The references

- [reference/api.md](reference/api.md): the public API, from `import` to the escape hatch: construction, lifecycle, every verb, the behavior catalog, the streams and their values, the errors, cancellation.
- [reference/configuration.md](reference/configuration.md): every field of `NaoqiBridgeConfig` with its default, the server configs and the CLIs.
- [reference/backends.md](reference/backends.md): the fake, the sim on NAOqi 2.1 and 2.8, a Nao v5 and a Nao v6: what each offers, and how far each is validated.

The design behind every page is in [specs/](../specs/_index.md), one spec per concept; [specs/_overview.md](../specs/_overview.md) is the architecture. The specs are the normative design, these pages are the consumer's view of it. One home per fact: a reference owns it, every other page links there.
