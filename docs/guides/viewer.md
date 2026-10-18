# The viewer

The bridge can open a [naoqi-viewer](https://github.com/funwithagents/naoqi-viewer) window that mirrors the robot it drives: the NAO model, posed live from the robot's joint angles and torso pose, read over `qi`. It only reads; it never commands the robot. It lets you watch what an agent makes a Nao do, on a robot across the room or a headless sim, and, with the ghost on, see the commanded pose next to the measured one. The design is in [specs/viewer.md](../../specs/viewer.md).

## Install

The `[viewer]` extra (`naoqi-bridge[viewer]`; the `[sim]` extra brings it too; `uv sync --dev` in a checkout installs both) and a display. On macOS a window needs `mjpython`, which comes with `mujoco`. Aldebaran's meshes, instead of the placeholder model:

```
uv run naoqi-viewer fetch-meshes     # once per machine, after its license prompt
```

## Open it with the session

```json
{
  "backend": "real",
  "robot": { "ip": "192.168.1.42" },
  "viewer": { "enabled": true, "config": { "ghost": true } }
}
```

The window opens last in `start()`, on the robot the bridge just connected to, and closes first in `stop()`. `viewer.config` is a naoqi-viewer config (`ghost`, `world.scene`, `world.variant`: `placeholder`, `aldebaran` or `auto`, `naoqi.rate_hz`, `launch_timeout_s`); the bridge sets the mode, the headless flag and the robot's address itself, and refuses them in the config ([../reference/configuration.md](../reference/configuration.md#viewer-a-window-on-the-robot)).

Where it opens, and where it doesn't:

| Backend | The viewer |
|---|---|
| `real` | mirrors the robot |
| `sim`, borrowed or started headless | mirrors the sim: a borrowed sim may have no window of its own |
| `sim`, started by the bridge with its own window (naoqi-sim's default) | **not opened**, with a warning: the sim's window already shows this robot. Set `sim.config.viewer.headless` to `true` to use the bridge's window instead |
| `fake` | **not opened**, with a warning: there is no Naoqi to mirror |

The two skips are warnings, not errors: the session is fine without the window. A viewer that can't launch (no display, no `mjpython`, the `aldebaran` variant without the meshes, a timeout) is a `ViewerError` from `start()`, with naoqi-viewer's message; the servers' CLIs exit 1 on it. The `real` example configs carry a disabled `viewer` block with the ghost on, ready to switch on.

The viewer has run on 2.1 sims and a 2.1 robot. CI never opens it: GitHub's runners have no display; the live tier's viewer test runs locally with `NAOQI_E2E_VIEWER=1` ([testing.md](testing.md)).
