# Gesture Mapping Quick Reference

## Quick Start

The gesture mapping system automatically analyzes LLM responses and selects appropriate robot gestures. **No configuration needed** - it works out of the box!

## How It Works (Simple)

1. LLM generates a response (e.g., "That's a great idea!")
2. System analyzes the text for keywords, emotions, and structure
3. System matches to a category (e.g., "positive_enthusiastic")
4. Robot performs a gesture from that category (e.g., `excited` or `happy`)

## Common LLM Responses → Gestures

| LLM Response Example | Gesture |
|---------------------|---------|
| "That's great!" | `excited`, `happy` |
| "Yes, exactly!" | `agreeing`, `emphatic` |
| "What is that?" | `curious`, `thinking` |
| "Wow, really?" | `surprised` |
| "Maybe we could..." | `confused`, `thinking` |
| "Hello!" | `greeting`, `nod` |
| "Sorry about that" | `nod`, `listening` |
| Long explanations | `listening`, `thinking` |

## Testing the Mapping

Test how different responses map to gestures:

```bash
# Run interactive test tool
python -m reachy_demo.tools.test_gesture_mapping --interactive

# Test a specific response
python -m reachy_demo.tools.test_gesture_mapping --text "That's amazing!"

# See all categories
python -m reachy_demo.tools.test_gesture_mapping --categories

# Run example tests
python -m reachy_demo.tools.test_gesture_mapping --examples
```

## Customization

Edit `src/reachy_demo/orchestrator/gesture_mapping.py`:

### Add Keywords to Existing Category

```python
GESTURE_MAPPING["positive_enthusiastic"]["keywords"].append("fantastic")
```

### Change Gestures for a Category

```python
GESTURE_MAPPING["agreement"]["gestures"] = ["agreeing", "nod", "emphatic"]
```

### Add New Category

```python
GESTURE_MAPPING["celebration"] = {
    "description": "Celebratory responses",
    "keywords": ["congratulations", "celebrate", "success"],
    "gestures": ["excited", "happy"],
    "priority": 1,
}
```

## Configuration File Location

- **Main Configuration**: `src/reachy_demo/orchestrator/gesture_mapping.py`
- **Documentation**: `docs/gesture-mapping.md`
- **Test Tool**: `src/reachy_demo/tools/test_gesture_mapping.py`

## Key Concepts

- **Categories**: Group related keywords and gestures together
- **Priority**: Lower number = checked first (1 = highest priority)
- **Keywords**: Words/phrases that trigger the category
- **Gestures**: List of possible gestures (randomly selected)
- **Constraints**: Optional limits (min_words, max_words, requires)

## Tips

1. **Use common LLM phrases**: LLMs often use phrases like "That's a great question" or "I'd be happy to help"
2. **Add variations**: Include different forms (e.g., "great", "greatly", "greatest")
3. **Test with real responses**: Use the test tool with actual LLM outputs
4. **Priority matters**: More specific categories should have lower priority numbers

## Example: Adding Support for "Thank You"

```python
# In gesture_mapping.py, modify the "greeting" category:
GESTURE_MAPPING["greeting"]["keywords"].extend([
    "thank you", "thanks", "appreciate", "grateful"
])
```

That's it! The system will now recognize "thank you" responses and use greeting gestures.

