# Reachy Mini Gestures Summary

Based on review of the [Reachy Mini project](https://github.com/pollen-robotics/reachy_mini) and related libraries, here's a comprehensive summary of available gestures.

## Gesture Categories

### 1. Built-in Daemon Animations

The Reachy Mini daemon provides built-in animations accessible via the REST API:

- **`wake_up`** - Wake up animation
  - Endpoint: `/api/move/play/wake_up`
  - Purpose: Robot awakening sequence
  
- **`goto_sleep`** - Sleep animation
  - Endpoint: `/api/move/play/goto_sleep`
  - Purpose: Robot going to sleep sequence

### 2. Recorded Move Datasets

The daemon supports pre-recorded moves via:
- Endpoint: `/api/move/play/recorded-move-dataset/{dataset}/{move}`
- Format: `{dataset}` is the dataset name, `{move}` is the specific move name
- Note: Specific datasets and moves need to be checked in the daemon's available datasets

### 3. Reachy Mini Dances Library

The [Reachy Mini Dances Library](https://github.com/pollen-robotics/reachy_mini_dances_library) provides:
- **20 pre-built dance moves**
- Flexible choreography system
- BPM adjustments
- Custom choreography creation
- Beat synchronization

### 4. Custom Gestures (Programmatic)

Gestures can be created programmatically using the `/api/move/goto` endpoint, which allows control of:
- **Head pose**: `pitch`, `yaw`, `roll`
- **Antennas**: `[left, right]` positions
- **Body yaw**: Body rotation

## Gestures Implemented in This Project

Our demo application implements the following custom gestures:

### Latency-Aware Gestures (Enterprise-Responsive)
- **`ack`** - Quick acknowledgment nod (immediate feedback)
- **`nod_fast`** - Fast nod for quick responses (<800ms)
- **`nod_tilt`** - Nod with head tilt for normal responses (800-2500ms)
- **`thinking_done`** - Thinking gesture for slow responses (>2500ms)
- **`error`** - Error gesture (shake/no)

### Expressive Gestures (Content-Aware)
- **`nod`** - Simple head nod (pitch down then back up)
- **`excited`** - Antennas wiggle rapidly with head bobs (energetic response)
- **`thinking`** - Head tilts side to side (processing/thinking)
- **`greeting`** - Friendly nod with antennas raised (for short responses)
- **`happy`** - Bouncy antennas with head bob (positive response)
- **`confused`** - Head shakes side to side (uncertainty)
- **`listening`** - Leans forward slightly with antennas perked (attentive)
- **`agreeing`** - Multiple quick nods (emphatic agreement)
- **`surprised`** - Head jerks back with antennas spread (surprise)
- **`curious`** - Head tilts with slight body turn (inquisitive)
- **`emphatic`** - Strong nod with body movement (emphasis)
- **`no`** - Clear head shake for negative responses
- **`yes`** - Positive response (uses agreeing/happy/nod gestures)
- **`random`** - Randomly selects from available gestures

### Built-in Animations (Via Daemon)
- **`wake_up`** - Wake up animation (uses daemon's built-in animation)
- **`goto_sleep`** - Sleep animation (uses daemon's built-in animation)

## Gesture Implementation Details

### Control Method
All custom gestures use the `/api/move/goto` endpoint with:
- **Duration**: Typically 0.2-0.6 seconds per movement
- **Interpolation**: `minjerk` for smooth motion
- **Sequences**: Multi-step movements with pauses between steps

### Gesture Characteristics
- **Head movements**: Pitch (nod), yaw (turn), roll (tilt)
- **Antenna movements**: Independent left/right control
- **Body movements**: Yaw rotation for emphasis
- **Timing**: Varied durations and pauses for natural expression

## Related Projects

1. **Reachy Mini Dances Library**
   - 20 pre-built dance moves
   - Choreography system
   - Beat synchronization

2. **Reachy Mini Conversation App**
   - Conversational interactions
   - Gesture integration

3. **Reachy Mini Toolbox**
   - Tools for creating behaviors
   - Gesture development utilities

## API Endpoints

### Motion Control
- `POST /api/move/goto` - Move to specific pose (head, antennas, body)
- `POST /api/move/play/wake_up` - Play wake up animation
- `POST /api/move/play/goto_sleep` - Play sleep animation
- `POST /api/move/play/recorded-move-dataset/{dataset}/{move}` - Play recorded move

### State Queries
- `GET /api/state/full` - Get full robot state (head pose, antennas, body yaw)

## Notes

- The daemon's recorded move datasets are not fully documented in the public API
- Custom gestures can be created by combining head, antenna, and body movements
- Gesture timing and sequences can be adjusted for different expressions
- The dances library provides higher-level choreography capabilities

## References

- [Reachy Mini GitHub](https://github.com/pollen-robotics/reachy_mini)
- [Reachy Mini Dances Library](https://github.com/pollen-robotics/reachy_mini_dances_library)
- [Reachy Mini Conversation App](https://github.com/pollen-robotics/reachy_mini_conversation_app)
- [Reachy Mini Toolbox](https://github.com/pollen-robotics/reachy_mini_toolbox)

