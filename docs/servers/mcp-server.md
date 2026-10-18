# The MCP server

`naoqi-mcp-server` exposes `NaoqiBridge` as [MCP](https://modelcontextprotocol.io) tools, so an LLM agent drives the robot by calling them: say this, stand up, dance, react, run an app. It is a thin adapter: each tool delegates to one bridge verb and returns a short status string the model can read, `"Nao said Hello"` or `"Nao failed to dance the dance with id 'macarena': unknown dance 'macarena' (known: …)"`. The design is in [specs/naoqi-mcp-server.md](../../specs/naoqi-mcp-server.md).

## Run it

The server takes one option, `--config`, a JSON file with the bridge's config under `bridge` and the server's under `server` ([../reference/configuration.md](../reference/configuration.md#server-configs-bridge--server)). Without it, it runs on the fake over stdio.

```
uv run naoqi-mcp-server                                              # the fake: every tool answers, nothing moves
uv run naoqi-mcp-server --config examples/configs/mcp-sim.json       # the simulator, started for you (Docker, the [sim] extra)
uv run naoqi-mcp-server --config path/to/mcp-real.json               # your Nao: a copy of mcp-real.json with its address in bridge.robot.ip
```

```json
{
  "bridge": {
    "backend": "real",
    "robot": { "ip": "192.168.1.42" }
  },
  "server": { "transport": "stdio" }
}
```

The bridge connects when the server starts and disconnects when the client leaves. A config that doesn't load exits 2 with the reason; a robot that can't be reached, or a sim that can't start, exits 1. Logs go to stderr: over `stdio`, standard output is the protocol's channel, and the server keeps it clean of everything else, libqi's own console log included. `"transport": "sse"` serves over HTTP instead, at FastMCP's default address, for a client that connects rather than launches.

## Plug it into an MCP client

Any MCP client that launches a stdio server needs the command and its arguments. Run it through `uv` from the checkout, so the right environment is used whatever the client's own:

| | |
|---|---|
| command | `uv` |
| args | `--directory`, `<path to the naoqi-bridge checkout>`, `run`, `naoqi-mcp-server`, `--config`, `<path to your config>` |

Leave out the last two arguments for the fake. In a project that installed the bridge, `uv run --project <your project> naoqi-mcp-server --config …` does the same.

**Claude Desktop**, as an example: add this to its `claude_desktop_config.json` and restart it.

```json
{
  "mcpServers": {
    "naoqi": {
      "command": "uv",
      "args": [
        "--directory", "/path/to/naoqi-bridge", "run", "naoqi-mcp-server",
        "--config", "/path/to/mcp-real.json"
      ]
    }
  }
}
```

Then start a conversation with a prompt that puts the model in the robot:

```
You are Nao, a fun and witty robot from Aldebaran. You can only answer through the naoqi tools, never in text: when you speak, use the say tool, and keep it short. Call wake_up before moving, and get_dance_list before dancing.
```

Models tend to answer in text instead of calling `say` when asked to *be* the robot; asking explicitly for actions ("make Nao dance") works every time. The prompt above helps, and a stricter one helps more.

## The tools

| Tool | Does |
|---|---|
| `set_tts_language(language)` | Set the text-to-speech language (`English`, `French`) |
| `say(text)` | Speak; returns once spoken |
| `wake_up()`, `rest()` | Motors on, for anything that moves; motors off, at the end of an interaction |
| `stand_up()`, `sit_down()` | Postures |
| `get_dance_list()` | The installed dances, as JSON (`id`, `behavior_name`, `localized_name`, `description`); call before `dance` |
| `dance(dance_id)`, `stop_dance(dance_id)` | Start a dance; stop it |
| `get_expressive_reaction_types()` | `["Happy", "Proud", "Laugh", "Sad", "HeadTouched"]`, as installed |
| `expressive_reaction(reaction_type)`, `stop_expressive_reaction(reaction_type)` | Play a random animation of that type; stop it |
| `get_body_actions_list()` | The installed body actions (raise or stretch an arm), as JSON |
| `body_action(body_action_id)`, `stop_body_action(body_action_id)` | Start one; stop it |
| `get_app_list()` | The installed apps, as JSON |
| `run_app(app_id)`, `stop_app(app_id)` | Start one; stop it |
| `get_running()` | What is playing now: `{"dances": [...], "expressive_reactions": [...], "body_actions": [...], "apps": [...]}` |

Each tool's description is its docstring, which the model reads, and which says the order things go in: `wake_up` before a move, a `get_*` list before its verb. Deliberately not exposed: `stop_say`, the eyes, breathing, basic awareness and raw `run_behavior`, which belong to a program, not a conversation.

**Behaviors return once started.** A dance or an app can last minutes, and most MCP clients issue one tool call at a time, so `dance`, `expressive_reaction`, `body_action` and `run_app` return `"Nao started …"` as soon as the behavior is playing, and it goes on while the agent calls other tools. `get_running` says whether it is still playing and the matching `stop_*` tool ends it. A behavior that fails after it started is logged by the server and is simply gone from `get_running`.

**Failures are answers.** A verb that fails for an expected reason (the motors are off, an unknown id, Naoqi refused) comes back as the tool's result, `"Nao failed to …: <reason>"`, so the model can act on it: call `wake_up`, pick another id. Anything else is a bug and surfaces as a tool error.

## What the agent gets on each backend

On the fake, every tool answers and the catalog is a fixed one (four dances, four apps, six body actions, the five reaction types), so an agent can be developed with no robot. On a sim, the catalog holds the reactions only: no dances, apps or body actions ([../reference/backends.md](../reference/backends.md)). On a robot, it is what the robot has installed.
