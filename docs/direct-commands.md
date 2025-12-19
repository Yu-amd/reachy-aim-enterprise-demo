# Direct Robot Commands

## Overview

The demo application supports direct robot control commands that bypass the LLM. Use the `cmd:` prefix to execute commands directly without sending them to the language model.

## Usage

All commands start with `cmd:` followed by the command name and optional arguments.

## Available Commands

### `cmd:gesture <name>`

Execute a robot gesture directly.

**Example:**
```
You> cmd:gesture nod
```

**Available gestures:**
- **Latency-aware gestures:**
  - `ack` - Quick acknowledgment nod (immediate feedback)
  - `nod_fast` - Fast nod for quick responses
  - `nod_tilt` - Nod with head tilt for normal responses
  - `thinking_done` - Thinking gesture for slow responses
  - `error` - Error gesture (shake/no)

- **Expressive gestures:**
  - `nod` - Simple head nod
  - `excited` - Antennas wiggle with head bobs
  - `thinking` - Head tilts side to side
  - `greeting` - Friendly nod with antennas raised
  - `happy` - Bouncy antennas with head bob
  - `confused` - Head shakes side to side
  - `listening` - Leans forward with antennas perked
  - `agreeing` - Multiple quick nods
  - `surprised` - Head jerks back with antennas spread
  - `curious` - Head tilts with slight body turn
  - `emphatic` - Strong nod with body movement
  - `no` - Clear head shake
  - `random` - Randomly selects from available gestures
  - `wake_up` - Wake up animation
  - `goto_sleep` - Sleep animation

### `cmd:reset`

Reset the robot to its home/neutral position.

**Example:**
```
You> cmd:reset
```

This uses the calibrated home position if available, otherwise resets to explicit zeros (0.0, 0.0, 0.0).

### `cmd:calibrate`

Calibrate the robot's current position as the home position.

**Example:**
```
You> cmd:calibrate
```

**Important:** Make sure the robot is in the desired neutral position before calibrating. After calibration, `reset()` will return the robot to this position.

### `cmd:state`

Display the current robot state (head pose, antennas, body yaw).

**Example:**
```
You> cmd:state
```

**Output:**
```
Robot State
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Axis         ┃ Value      ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Head Pitch   │ 0.0000     │
│ Head Yaw     │ 0.0000     │
│ Head Roll    │ 0.0000     │
│ Antenna Left │ 0.0000     │
│ Antenna Right│ 0.0000     │
│ Body Yaw     │ 0.0000     │
└──────────────┴────────────┘
```

### `cmd:help`

Show available commands and gestures.

**Example:**
```
You> cmd:help
```

## Use Cases

### Testing Gestures

Quickly test different gestures without waiting for LLM responses:

```
You> cmd:gesture excited
You> cmd:gesture confused
You> cmd:gesture happy
```

### Calibrating Home Position

1. Manually position the robot in the desired neutral position
2. Run calibration:
   ```
   You> cmd:calibrate
   ```
3. Verify with state:
   ```
   You> cmd:state
   ```

### Debugging

Check robot state at any time:
```
You> cmd:state
```

Reset robot manually:
```
You> cmd:reset
```

## Notes

- Commands are case-insensitive (e.g., `cmd:GESTURE nod` works)
- Commands bypass the LLM completely - no inference call is made
- Commands don't affect conversation history
- Commands don't trigger metrics collection (no E2E latency, etc.)
- Commands are executed immediately without pre/post gestures

## Examples

### Complete Workflow

```
You> cmd:gesture greeting
✓ Gesture 'greeting' executed

You> cmd:state
[Shows current robot state]

You> cmd:calibrate
✓ Home position calibrated

You> cmd:reset
✓ Robot reset complete

You> cmd:help
[Shows all available commands]
```

### Testing Multiple Gestures

```
You> cmd:gesture nod
You> cmd:gesture excited
You> cmd:gesture thinking
You> cmd:gesture happy
You> cmd:gesture random
```

