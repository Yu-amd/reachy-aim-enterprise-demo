"""
Gesture Mapping Configuration for LLM Response Analysis

This module provides an intuitive, configurable mapping system that analyzes
LLM response text and selects appropriate robot gestures.

The mapping is organized by emotional/intent categories, making it easy to
understand and modify which gestures correspond to which types of responses.
"""

from __future__ import annotations
from typing import Dict, List, Tuple
import re


# ============================================================================
# GESTURE MAPPING CONFIGURATION
# ============================================================================
# This dictionary maps emotional/intent categories to gesture options.
# Each category can have multiple gesture options for variety.
# ============================================================================

GESTURE_MAPPING: Dict[str, Dict] = {
    # Positive/Enthusiastic Responses
    "positive_enthusiastic": {
        "description": "Strong positive emotions, excitement, praise",
        "keywords": [
            "great", "excellent", "awesome", "wonderful", "amazing", "fantastic",
            "perfect", "brilliant", "incredible", "outstanding", "superb", "marvelous",
            "terrific", "fabulous", "spectacular", "phenomenal", "exceptional"
        ],
        "gestures": ["excited", "happy", "emphatic"],
        "priority": 1,  # High priority - check early
    },
    
    # Agreement/Confirmation
    "agreement": {
        "description": "Agreement, confirmation, validation",
        "keywords": [
            "yes", "correct", "right", "exactly", "absolutely", "indeed",
            "that's right", "you're right", "agreed", "precisely", "certainly",
            "definitely", "sure", "of course", "indeed", "affirmative"
        ],
        "gestures": ["agreeing", "emphatic", "nod"],
        "priority": 1,
    },
    
    # Questions/Inquiry
    "question": {
        "description": "Questions, inquiries, seeking information",
        "keywords": ["what", "how", "why", "when", "where", "who", "which"],
        "gestures": ["curious", "thinking"],
        "priority": 1,
        "requires": "?",  # Must contain question mark
    },
    
    # Surprise/Astonishment
    "surprise": {
        "description": "Surprise, astonishment, unexpected information",
        "keywords": [
            "wow", "oh", "really", "surprising", "unexpected", "didn't expect",
            "astonishing", "remarkable", "impressive", "incredible", "unbelievable"
        ],
        "gestures": ["surprised"],
        "priority": 2,
    },
    
    # Uncertainty/Hesitation
    "uncertainty": {
        "description": "Uncertainty, hesitation, doubt",
        "keywords": [
            "maybe", "perhaps", "might", "could", "uncertain", "not sure",
            "don't know", "unclear", "possibly", "probably", "might be",
            "not certain", "unsure", "doubtful"
        ],
        "gestures": ["confused", "thinking"],
        "priority": 2,
    },
    
    # Explanation/Informative
    "explanation": {
        "description": "Long explanations, informative responses",
        "keywords": [
            "because", "due to", "as a result", "in other words", "for example",
            "specifically", "in detail", "explanation", "means", "refers to"
        ],
        "gestures": ["listening", "thinking", "curious"],
        "priority": 3,
        "min_words": 20,  # Only trigger for longer responses
    },
    
    # Greeting/Polite
    "greeting": {
        "description": "Greetings, polite acknowledgments",
        "keywords": [
            "hello", "hi", "hey", "greetings", "nice to meet", "pleasure",
            "welcome", "good to see", "thanks", "thank you", "appreciate"
        ],
        "gestures": ["greeting", "nod"],
        "priority": 3,
        "max_words": 10,  # Only for short responses
    },
    
    # Apology/Regret
    "apology": {
        "description": "Apologies, regret, acknowledgment of mistakes",
        "keywords": [
            "sorry", "apologize", "regret", "my mistake", "my fault",
            "forgive", "pardon", "excuse me"
        ],
        "gestures": ["nod", "listening"],
        "priority": 2,
    },
    
    # Negative/Concern
    "negative": {
        "description": "Negative emotions, concerns, problems",
        "keywords": [
            "unfortunately", "however", "problem", "issue", "concern",
            "difficult", "challenging", "trouble", "error", "wrong"
        ],
        "gestures": ["thinking", "confused"],
        "priority": 2,
    },
}


# ============================================================================
# GESTURE SELECTION LOGIC
# ============================================================================

def analyze_text(text: str) -> Dict[str, any]:
    """
    Analyze LLM response text and extract features for gesture selection.
    
    Returns a dictionary with:
    - word_count: Number of words
    - has_question: Whether text contains a question mark
    - has_exclamation: Whether text contains exclamation mark
    - sentence_count: Number of sentences
    - detected_categories: List of matching emotion/intent categories
    - sentiment_score: Simple sentiment score (-1 to 1)
    """
    text_lower = text.lower()
    words = text.split()
    word_count = len(words)
    
    # Detect punctuation
    has_question = "?" in text
    has_exclamation = "!" in text
    
    # Count sentences
    sentence_count = len(re.split(r'[.!?]+', text.strip()))
    
    # Detect matching categories
    detected_categories = []
    for category, config in GESTURE_MAPPING.items():
        # Check if category requires specific conditions
        requires = config.get("requires")
        if requires and requires not in text:
            continue
        
        # Check word count constraints
        min_words = config.get("min_words", 0)
        max_words = config.get("max_words", float('inf'))
        if not (min_words <= word_count <= max_words):
            continue
        
        # Check keywords
        keywords = config.get("keywords", [])
        if any(keyword in text_lower for keyword in keywords):
            detected_categories.append((category, config))
    
    # Simple sentiment scoring
    positive_words = ["good", "great", "excellent", "wonderful", "amazing", "happy", "pleased"]
    negative_words = ["bad", "terrible", "awful", "horrible", "sad", "disappointed", "unfortunate"]
    
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    sentiment_score = 0.0
    if positive_count > negative_count:
        sentiment_score = min(1.0, positive_count / 5.0)
    elif negative_count > positive_count:
        sentiment_score = max(-1.0, -negative_count / 5.0)
    
    return {
        "word_count": word_count,
        "has_question": has_question,
        "has_exclamation": has_exclamation,
        "sentence_count": sentence_count,
        "detected_categories": detected_categories,
        "sentiment_score": sentiment_score,
    }


def select_gesture(text: str, response_time_ms: float) -> str:
    """
    Select the most appropriate gesture based on LLM response analysis.
    
    Uses a priority-based scoring system:
    1. High-priority categories (agreement, positive, questions) are checked first
    2. Multiple matches are resolved by priority
    3. Fallback to length/speed-based heuristics if no category matches
    4. Default to natural, varied gestures
    
    Args:
        text: The LLM response text
        response_time_ms: Response time in milliseconds (for speed-based heuristics)
    
    Returns:
        Gesture name string
    """
    import random
    
    analysis = analyze_text(text)
    detected_categories = analysis["detected_categories"]
    
    # If we have category matches, use priority-based selection
    if detected_categories:
        # Sort by priority (lower number = higher priority)
        detected_categories.sort(key=lambda x: x[1].get("priority", 99))
        
        # Get highest priority category
        top_category, config = detected_categories[0]
        
        # Select gesture from category options
        gestures = config.get("gestures", ["nod"])
        selected = random.choice(gestures)
        
        # Log selection for debugging (optional)
        # print(f"Selected '{selected}' for category '{top_category}'")
        
        return selected
    
    # Fallback heuristics based on text characteristics
    word_count = analysis["word_count"]
    
    # Very short responses (likely acknowledgments)
    if word_count < 5:
        return random.choice(["nod", "greeting"])
    
    # Short responses (quick confirmations)
    if word_count < 10:
        return random.choice(["nod", "listening", "greeting"])
    
    # Medium responses
    if 10 <= word_count <= 25:
        # Fast responses suggest confidence
        if response_time_ms < 800:
            return random.choice(["happy", "nod", "emphatic"])
        # Slower responses suggest thoughtfulness
        return random.choice(["thinking", "listening", "curious"])
    
    # Long responses (likely explanations)
    if word_count > 30:
        return random.choice(["listening", "thinking", "curious"])
    
    # Very fast responses (likely confident/cached)
    if response_time_ms < 600:
        return random.choice(["happy", "excited", "nod"])
    
    # Default: varied natural gestures
    return random.choice(["nod", "listening", "thinking", "happy", "curious"])


# ============================================================================
# CONFIGURATION HELPERS
# ============================================================================

def get_gesture_mapping_doc() -> str:
    """Return documentation string explaining the gesture mapping system."""
    doc = """
Gesture Mapping System Documentation
====================================

This system maps LLM response text to robot gestures using a configurable
category-based approach.

Categories:
-----------
"""
    for category, config in GESTURE_MAPPING.items():
        doc += f"\n{category}:\n"
        doc += f"  Description: {config.get('description', 'N/A')}\n"
        doc += f"  Keywords: {', '.join(config.get('keywords', [])[:5])}...\n"
        doc += f"  Gestures: {', '.join(config.get('gestures', []))}\n"
        doc += f"  Priority: {config.get('priority', 'N/A')}\n"
    
    doc += """
How It Works:
------------
1. Text is analyzed for keywords, punctuation, and structure
2. Matching categories are identified (sorted by priority)
3. A gesture is randomly selected from the top category's options
4. If no category matches, fallback heuristics are used (length, speed)

Customization:
-------------
To modify gesture mappings, edit the GESTURE_MAPPING dictionary:
- Add/remove keywords in each category
- Change gesture options for each category
- Adjust priority (lower = checked first)
- Add new categories as needed
"""
    return doc

