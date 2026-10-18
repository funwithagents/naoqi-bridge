# API reference: `NaoqiBridge`

The public surface of the bridge: what you import, construction and lifecycle, every verb, the behavior catalog, the streams and their values, the errors, and the cancellation contract. This page is the consumer's home for those contracts; the normative design, with its rationale, is in [specs/bridge.md](../../specs/bridge.md) and the specs it links.

On this page: [Imports](#imports) · [Construction](#construction) · [Lifecycle](#lifecycle) · [Verbs](#verbs) · [The behavior catalog](#the-behavior-catalog) · [Streams](#streams) · [Errors](#errors) · [Cancellation](#cancellation) · [The escape hatch](#the-escape-hatch).

## Imports

From `naoqi_bridge`:

| Name | What it is |
|---|---|
| `NaoqiBridge` | The bridge: a session with verbs and streams |
| `NaoqiBridgeConfig`, `RobotSettings`, `StreamSettings`, `JointsStream`, `AudioStream`, `CameraStreams`, `CameraStream`, `SimSettings`, `ViewerSettings` | The config and its blocks, for a config assembled in code ([configuration.md](configuration.md)) |
| `Backend`, `SimSpawn`, `CameraResolution`, `Camera`, `TouchPart` | The literal types of the config's words and the streams' keys |
| `BehaviorInfos`, `LocalizedString` | A catalog entry and its names |
| `TouchEvent`, `PostureState`, `JointsState`, `MicChunk`, `CameraFrame` | The stream values |
| `Event`, `Observable` | The types of `on_touch`, and of `posture` and `joints` |
| `BridgeError`, `NotRunningError`, `NotPlayingError`, `MotorsOffError`, `CommandFailedError`, `ViewerError`, `ConfigError`, `RobotConnectionError` | The errors a caller catches |

From `naoqi_bridge.fake_robot`: `FakeNaoqiRobot`, to narrow `bridge.robot` in a test. From `naoqi_bridge.testing`: the live-test harness ([../guides/testing.md](../guides/testing.md)).

## Construction

```python
NaoqiBridge(config: NaoqiBridgeConfig | Backend | None = None)   # None: the fake; "fake" | "sim": shorthand
NaoqiBridge.from_dict(data)
NaoqiBridge.from_json(text)
NaoqiBridge.from_json_file(path)
```

A bare backend string is shorthand for a config with everything else at its default (`NaoqiBridge("real")` alone is a `ConfigError`: no address). The `from_*` constructors validate the config as they load it and raise `ConfigError` there, before the bridge exists. Construction connects nothing and starts no task; `bridge.config` and `bridge.backend` are read-only.

## Lifecycle

```python
async with NaoqiBridge.from_json_file("robot.json") as bridge:   # start() … stop()
    ...

bridge = NaoqiBridge.from_json_file("robot.json")                 # a host with lifecycle hooks
await bridge.start()
...
await bridge.stop()
```

**`start()`** brings everything up in order: on `sim`, the sim is started or borrowed first; then the robot is connected (one attempt, bounded by `robot.connect_timeout_s`), the posture is read and its changes subscribed, touch is subscribed, the streams the config enables are opened, the catalog is loaded, and last the viewer, when enabled. If a step fails, what already started is torn down and the error propagates: `RobotConnectionError` for a robot that can't be reached or a sim that can't be started or borrowed, `ViewerError` for a viewer that can't launch. `start()` on a running bridge raises `BridgeError`.

**`stop()`** tears down in reverse: the viewer, the joints task (`joints` and `posture` publish `None`), the camera and microphone feeds (every `frames()` and `audio_input()` iterator ends), the touch and posture subscriptions, the robot, the running-item tracking, and last the sim when the bridge started it (the seconds of a `docker compose down`). It runs every step even when one fails, is a no-op on a stopped bridge, and `start()` may follow it.

- **`async with` is the recommended form**: it stops the session on every way out, a cancel included.
- **One event loop owns a session.** Touch handlers run on it, the observables publish on it, the verbs are awaited on it.
- **A cancelled `start()` leaks nothing**: a connection in flight is given up within 50 ms, what was started is torn down, the cancel propagates. **A cancelled `stop()` completes**: the teardown is owned once begun.
- **`bridge.running`** says whether the session is up. The verbs, `bridge.robot`, `audio_input()` and a camera feed's `frames()` raise `NotRunningError` otherwise; `posture`, `joints`, `mic` and `cameras` read at any time (`None` outside a session).
- **Your tasks are yours.** A task draining `audio_input()` or following `frames()` finishes on its own when the session stops; one following `posture.changes()` or `joints.changes()` does not, because the observables belong to the bridge object and outlive its sessions: cancel and await it yourself.

## Verbs

Every verb is `async`, returns `None` when it succeeded, and raises to say why it didn't ([Errors](#errors)). Each blocking Naoqi call runs off the event loop.

| Area | Verb | Needs motors | Spans |
|---|---|---|---|
| Speech | `set_tts_language(language)`: `"English"`, `"French"`, whatever the robot has installed | no | instant |
| | `say(text)`: animated speech; returns once spoken | no | the utterance |
| | `stop_say()`: cut the speech in flight | no | instant |
| Motors | `wake_up()`: motors on; `rest()`: a safe posture, then motors off | no | instant (a few seconds on a robot) |
| Postures | `stand_up()`, `sit_down()`: go to `Stand` / `Sit`; `CommandFailedError` when the robot didn't reach it | yes | the move |
| Expression | `change_eyes_color(color)`: `white`, `red`, `green`, `blue`, `yellow`, `magenta`, `cyan` | no | instant |
| | `set_breathing_enabled(enabled, chain_name)`: Naoqi's breathing on a chain, `"Body"` for all | to enable | instant |
| | `set_basic_awareness_state(enabled, engagement_mode, tracking_mode)`: Naoqi's `ALBasicAwareness`, which turns the head to people | no | instant |
| Behaviors | `run_behavior(behavior_name)`: any installed behavior by its Naoqi name; returns when it ends. `stop_behavior(behavior_name)` | yes | the behavior |
| Catalog | `dance(dance_id)`, `expressive_reaction(reaction_type)`, `body_action(body_action_id)`, `run_app(app_id)`: a catalog entry's behavior; return when it ends. `stop_dance`, `stop_expressive_reaction`, `stop_body_action`, `stop_app` | yes | the behavior |

**Needs motors.** A verb that moves the body asks the robot whether the motors are on, every time (the robot can go to rest without the bridge: the fall manager, the chest button, another client), and raises `MotorsOffError` before sending anything when they are off. Call `wake_up()` first. The fake starts with the motors off, like a robot at rest.

**Spans.** A spanning verb lasts as long as its effect on the robot and is where cancellation does real work ([Cancellation](#cancellation)). An instant verb hands Naoqi one command and returns; `wake_up` and `rest` take a few seconds but are instant all the same: a half-applied rest would leave the motors in an unknown state, so the call completes and `wake_up` undoes it.

**Speech.** `say` returns once the sentence has been spoken, gestures included. Two `say` calls queue on Naoqi: the second waits for the first. `stop_say`, or cancelling either, silences both.

**Postures.** `stand_up` and `sit_down` ask Naoqi for the posture at speed 0.8 with three tries, and return when the robot is in it. On a 2.8 sim, `sit_down` goes through Crouch and takes 15 to 25 s ([backends.md](backends.md)). `rest` relaxes where Naoqi chooses: a crouch from Stand; from Sit, a Nao stays seated.

## The behavior catalog

At `start()` the bridge reads the robot's installed packages and classifies them into four catalogs. The getters are synchronous and return `[]` before the first `start()`:

| Getter | Returns | What qualifies |
|---|---|---|
| `get_dance_behaviors()` | `list[BehaviorInfos]` | a behavior whose description mentions a dance |
| `get_expressive_reaction_types()` | `list[str]`: `Happy`, `Proud`, `Laugh`, `Sad`, `HeadTouched` | the `animations` package's standing emotions, by tag; `HeadTouched` from the `dialog_touch` package |
| `get_body_action_behaviors()` | `list[BehaviorInfos]`: `UpLArm`, `StretchBothArms`, … | the `dialog_move_arms` package |
| `get_app_behaviors()` | `list[BehaviorInfos]` | the root behavior of a package that isn't a system or dialog package, nor a dance |

```python
@dataclass
class BehaviorInfos:
    id: str                          # what the catalog verbs take
    behavior_name: str               # Naoqi's name, what run_behavior takes
    localized_name: LocalizedString  # en_US, fr_FR
    description: str
```

`dance(id)`, `body_action(id)` and `run_app(id)` run the entry's behavior; `expressive_reaction(type)` picks a **random** behavior of that type. An unknown id or type raises `ValueError` naming the known ones, so an agent corrects itself without another lookup.

**What's running.** While a catalog verb runs, its item shows in `current_dances`, `current_body_actions`, `current_apps` (tuples of ids) and `current_expressive_reactions` (type → the behavior playing); `current_behaviors` lists every behavior `run_behavior` is running, the catalog verbs' included. They are snapshots, cleared when the run ends, fails, or has been stopped.

**Stopping.** The stop verbs are meant to be called concurrently with the verb they stop, from another task. `stop_dance(id)` and its siblings raise `NotPlayingError` for an item that isn't playing; they return once the behavior has stopped, re-sending the stop if Naoqi hadn't started the behavior yet when the first one arrived.

## Streams

The robot's data comes back out through five streams, each in the shape its data calls for: an **event** for occurrences where every one matters (touch), an **observable** for a state where only the latest matters (posture, joints, camera frames), a **subscriber ring** for a continuous signal every consumer needs whole (audio). Each has any number of consumers; none is a callback into Naoqi's threads. Touch and posture are always on; joints, audio and the cameras are subscribed on the robot only when the config enables them, and their API raises `BridgeError` otherwise ([configuration.md](configuration.md#streams-what-the-bridge-subscribes-to-on-the-robot)).

| Stream | Property | Type |
|---|---|---|
| touch | `on_touch` | `Event[TouchEvent]` |
| posture | `posture` | `Observable[PostureState \| None]` |
| joints | `joints` | `Observable[JointsState \| None]` |
| audio | `audio_input(*, preroll_s=0.0)`, `mic` | an `AsyncIterator[bytes]` per call; the `MicFeed` behind them |
| cameras | `cameras["top"]`, `cameras["bottom"]` | `CameraFeed` |

**Event.** `on_touch.subscribe(handler)` / `unsubscribe(handler)`; handlers are plain functions called on the event loop, in subscription order, each isolated from the others' exceptions.

**Observable.** `.value` reads now; `await .wait_for(predicate)` returns the current value when the predicate holds for it, else the first published value that does; `async for v in .changes()` yields each value published from the moment the iterator is first driven (not the current one), latest-wins: a slow consumer skips to the newest.

**Audio.** Every `audio_input()` call is a subscriber of its own over the one microphone feed: any number at once, a recognizer, a wake-word detector, a recorder, each receiving every chunk in order at its own pace, as `bytes` of int16 little-endian mono PCM at `mic.sample_rate` (16000). The feed keeps the last 200 chunks (about 17 s on a robot): `preroll_s` starts a subscriber up to that far in the past, so a recognizer started by a wake word hears the sentence that woke it; a subscriber that falls further behind loses the chunks it missed, logged as a warning, without slowing the others. `mic.latest()` is the newest `MicChunk` for a level meter; the iterator ends when the session stops.

**Cameras.** Both feeds exist from construction, enabled or not. `latest()` is the newest `CameraFrame`, or `None` before the first one, outside a session or for a disabled camera; `async for frame in .frames()` follows each new frame, latest-wins, so a slow consumer skips frames rather than lagging, and ends with the session; `await .wait_for(predicate)` returns the first frame that matches. Frames are pulled at the configured `fps`, so a frame is at most one period old.

### The values

```python
@dataclass(frozen=True)
class TouchEvent:
    part: TouchPart        # "FrontTactilTouched" | "MiddleTactilTouched" | "RearTactilTouched"
    touched: bool

@dataclass(frozen=True)
class PostureState:
    posture: str           # Naoqi's: "Stand", "Sit", "Crouch", "StandInit", "LyingBack", …, "Unknown"
    family: str            # Naoqi's: "Standing", "Sitting", "Crouching" (2.8; "Standing" on 2.1), …
    moving: bool           # a bridge verb (stand_up, sit_down, rest) is moving the robot
    moving_to: str | None  # that move's target ("Stand", "Sit"), None for rest
    ts: float              # monotonic clock

@dataclass(frozen=True)
class JointsState:
    names: tuple[str, ...]    # Naoqi's "Body" joint names, 26 on a Nao
    angles: tuple[float, ...] # radians, same order
    ts: float

@dataclass(frozen=True)
class MicChunk:
    seq: int                  # 0, 1, 2, … per feed
    ts: float                 # arrival, monotonic clock
    data: bytes               # int16 LE PCM as Naoqi pushed it
    channels: int
    samples_per_channel: int

@dataclass(frozen=True)
class CameraFrame:
    frame_id: int
    ts: float                          # arrival, monotonic clock
    camera: Camera                     # "top" | "bottom"
    width: int
    height: int
    data: bytes                        # BGR, 3 bytes per pixel, row-major
    naoqi_ts: float                    # Naoqi's capture time, on the robot's clock
    camera_transform: tuple[float, ...]  # row-major 4x4, camera -> FRAME_ROBOT, at the pull
    fov: tuple[float, float]           # horizontal, vertical, radians
    image: np.ndarray                  # property: (height, width, 3) BGR, a read-only view of data
```

**Posture is Naoqi's, movement is the bridge's.** `posture` and `family` are what Naoqi's posture manager reports, whatever moved the robot: a verb, a dance, a fall. `moving` is set while `stand_up`, `sit_down` or `rest` run and cleared with a fresh read when they return. While `moving`, `posture` is Naoqi's nearest-posture guess and can name anything; wait for `not moving` for a settled one. `None` outside a session, or when the posture couldn't be read at `start()`.

## Errors

| Error | Raised for |
|---|---|
| `ConfigError(ValueError)` | A config that doesn't load: the message names the key path |
| `RobotConnectionError` | `start()`: the robot can't be reached within `connect_timeout_s`, no `qi` on this platform, a sim that can't be started or borrowed (naoqi-sim's message, saying what to do, chained) |
| `BridgeError(RuntimeError)` | The base of the bridge's own errors; raised as such for a double `start()` and for a disabled stream's API |
| `NotRunningError(BridgeError)` | A verb, `robot`, `audio_input()` or `frames()` on a bridge that isn't running |
| `MotorsOffError(BridgeError)` | A verb that moves the body while the motors are off: call `wake_up()` first |
| `NotPlayingError(BridgeError)` | A catalog stop verb for an item that isn't playing |
| `CommandFailedError(BridgeError)` | The robot failed the command: Naoqi's exception, chained as `__cause__`; or a posture not reached |
| `ViewerError(BridgeError)` | `start()` couldn't launch the viewer: no display, no meshes, a timeout (naoqi-viewer's message chained) |
| `ValueError` | A catalog id or reaction type the catalog doesn't hold, or a reaction type with no behavior installed; the message lists the known ones |

So `except (BridgeError, ValueError)` catches every expected verb failure, and that is what both servers do to turn a failure into a readable reason for their client.

## Cancellation

Cancelling the task that awaits a verb is the one way to interrupt it, whether the cancel comes from `task.cancel()`, an `asyncio.timeout`, a `TaskGroup` unwinding or a server dropping a client. Every verb honors it, and a cancelled verb guarantees three things:

1. **The effect stops with the verb.** What it started on the robot has stopped before the `CancelledError` reaches you: the robot is silent, the move has stopped, the behavior has ended.
2. **The cancel returns in bounded time.** The stop is normally one short Naoqi call; the bridge re-sends it every 0.5 s if the behavior hadn't started yet when the first stop arrived, up to 4 s in all, then gives up with a warning. Measured on a Nao v5: a `say` stops in about 0.5 s, a dance in 1 to 3 s, a stand-up in about 3 s.
3. **The session stays usable.** Only that verb's effect is undone: the motors, the eyes, breathing and the streams stay as they were, and the next verb works at once.

It is not a rewind: what was already spoken was heard, and a move or a dance stops where the cancel caught it. The instant verbs return at once on a cancel and their command still completes; what lasts beyond them is a mode its counterpart verb switches back. The stream iterators end when their task is cancelled.

```python
async with asyncio.timeout(10):
    await bridge.dance("eagle-dance")   # stopped after 10 s, then TimeoutError
```

## The escape hatch

`bridge.robot` is the robot the bridge drives, while running: on `real` and `sim` a `RealNaoqiRobot` holding the `qi` session, on `fake` the `FakeNaoqiRobot` whose recorded commands a test asserts on ([../guides/testing.md](../guides/testing.md)). Its methods are the blocking slice of Naoqi the bridge consumes ([specs/robot.md](../../specs/robot.md)), in Naoqi's units and names; call them off the event loop.
