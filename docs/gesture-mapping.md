# Gesture Mapping System

## Overview

The gesture mapping system analyzes LLM response text and automatically selects appropriate robot gestures. This makes the robot's expressions intuitive and contextually relevant to what the LLM is saying.

## How It Works

The system uses a **category-based mapping** approach:

1. **Text Analysis**: The LLM response is analyzed for:
   - Keywords (emotional/intent indicators)
   - Punctuation (questions, exclamations)
   - Length (word count)
   - Sentence structure

2. **Category Matching**: The text is matched against predefined categories (e.g., "positive_enthusiastic", "agreement", "question")

3. **Gesture Selection**: A gesture is randomly selected from the matched category's gesture options

4. **Fallback Logic**: If no category matches, heuristics based on length and response speed are used

## Gesture Categories

### Positive/Enthusiastic
- **Keywords**: great, excellent, awesome, wonderful, amazing, fantastic, perfect, brilliant, incredible, outstanding, superb
- **Gestures**: `excited`, `happy`, `emphatic`
- **Example**: "That's a great idea!" → `excited` or `happy`

### Agreement/Confirmation
- **Keywords**: yes, correct, right, exactly, absolutely, indeed, that's right, you're right, agreed
- **Gestures**: `agreeing`, `emphatic`, `nod`
- **Example**: "Yes, exactly!" → `agreeing` or `emphatic`

### Questions/Inquiry
- **Keywords**: what, how, why, when, where, who, which
- **Requires**: Question mark (?)
- **Gestures**: `curious`, `thinking`
- **Example**: "What is machine learning?" → `curious` or `thinking`

### Surprise/Astonishment
- **Keywords**: wow, oh, really, surprising, unexpected, didn't expect, astonishing, remarkable
- **Gestures**: `surprised`
- **Example**: "Wow, that's impressive!" → `surprised`

### Uncertainty/Hesitation
- **Keywords**: maybe, perhaps, might, could, uncertain, not sure, don't know, unclear, possibly
- **Gestures**: `confused`, `thinking`
- **Example**: "Maybe we could try that" → `confused` or `thinking`

### Explanation/Informative
- **Keywords**: because, due to, as a result, in other words, for example, specifically, in detail
- **Gestures**: `listening`, `thinking`, `curious`
- **Min Words**: 20 (only triggers for longer responses)
- **Example**: Long explanation about a topic → `listening` or `thinking`

### Greeting/Polite
- **Keywords**: hello, hi, hey, greetings, nice to meet, pleasure, welcome, thanks, thank you
- **Gestures**: `greeting`, `nod`
- **Max Words**: 10 (only for short responses)
- **Example**: "Hello, nice to meet you!" → `greeting` or `nod`

### Apology/Regret
- **Keywords**: sorry, apologize, regret, my mistake, my fault, forgive, pardon
- **Gestures**: `nod`, `listening`
- **Example**: "Sorry about that" → `nod` or `listening`

### Negative/Concern
- **Keywords**: unfortunately, however, problem, issue, concern, difficult, challenging, trouble, error
- **Gestures**: `thinking`, `confused`
- **Example**: "Unfortunately, that's not possible" → `thinking` or `confused`

## Fallback Logic

If no category matches, the system uses heuristics:

- **Very short** (< 5 words): `nod`, `greeting`
- **Short** (5-10 words): `nod`, `listening`, `greeting`
- **Medium** (10-25 words):
  - Fast response (< 800ms): `happy`, `nod`, `emphatic`
  - Slow response: `thinking`, `listening`, `curious`
- **Long** (> 30 words): `listening`, `thinking`, `curious`
- **Very fast** (< 600ms): `happy`, `excited`, `nod`
- **Default**: `nod`, `listening`, `thinking`, `happy`, `curious`

## Customization

### Adding New Categories

Edit `src/reachy_demo/orchestrator/gesture_mapping.py`:

```python
GESTURE_MAPPING["your_category"] = {
    "description": "Description of when this category applies",
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "gestures": ["gesture1", "gesture2"],
    "priority": 2,  # Lower = checked first (1-3 recommended)
    "min_words": 0,  # Optional: minimum word count
    "max_words": 100,  # Optional: maximum word count
    "requires": "?",  # Optional: required punctuation or text
}
```

### Modifying Existing Categories

1. **Add keywords**: Add more words to the `keywords` list
2. **Change gestures**: Modify the `gestures` list to use different gesture names
3. **Adjust priority**: Change `priority` to make the category checked earlier (lower number) or later (higher number)
4. **Add constraints**: Add `min_words`, `max_words`, or `requires` to make matching more specific

### Example: Adding a "Celebration" Category

```python
GESTURE_MAPPING["celebration"] = {
    "description": "Celebratory responses, achievements, milestones",
    "keywords": ["congratulations", "celebrate", "achievement", "milestone", "success", "victory"],
    "gestures": ["excited", "happy", "emphatic"],
    "priority": 1,  # High priority
}
```

## Testing the Mapping

You can test how different LLM responses map to gestures:

```python
from reachy_demo.orchestrator.gesture_mapping import select_gesture, analyze_text

# Test a response
text = "That's a great idea! I'm excited to try it."
analysis = analyze_text(text)
print(f"Analysis: {analysis}")
print(f"Selected gesture: {select_gesture(text, 500)}")
```

## Available Gestures

- `nod` - Simple head nod
- `excited` - Antennas wiggle with head bobs
- `thinking` - Head tilts side to side
- `greeting` - Friendly nod with antennas raised
- `happy` - Bouncy antennas with head bob
- `confused` - Head shakes side to side
- `listening` - Leans forward with antennas perked
- `agreeing` - Multiple quick nods
- `surprised` - Head jerks back with antennas spread
- `curious` - Head tilts with body turn
- `emphatic` - Strong nod with body movement

## Priority System

Categories are checked in priority order (lower number = checked first):

1. **Priority 1**: High-confidence matches (positive, agreement, questions)
2. **Priority 2**: Medium-confidence matches (surprise, uncertainty, negative)
3. **Priority 3**: Lower-confidence matches (explanation, greeting)

If multiple categories match, the highest priority (lowest number) category is used.

## Tips for Best Results

1. **Keyword Selection**: Use common words/phrases that LLMs typically use in responses
2. **Gesture Variety**: Each category should have 2-3 gesture options for natural variation
3. **Priority Tuning**: Adjust priorities so more specific categories are checked before general ones
4. **Word Count Constraints**: Use `min_words`/`max_words` to avoid false matches (e.g., "greeting" only for short responses)

