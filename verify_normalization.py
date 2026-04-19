import sys
import os
import re
import io

# Force UTF-8 for output to handle emojis on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from agent import (
    _strip_placeholder_text,
    _strip_visual_artifacts,
    _normalize_poll_separators,
    _deduplicate_hashtags,
    _finalize_post_text
)

def test_placeholder_stripping():
    print("Testing placeholder stripping...")
    texts = [
        "This is a post [Step 1] with some text.",
        "[Option A] This is a line option.",
        "(Decision Point 2) some text (Part 1)",
        "Step\u00a01: Do something.", # Testing non-breaking space variant
    ]
    for t in texts:
        print(f"Original: {t}")
        print(f"Cleaned:  {_strip_placeholder_text(t)}")
        print("-" * 20)

def test_visual_artifact_stripping():
    print("\nTesting visual artifact stripping...")
    texts = [
        "Hook line\nv v v\nBody line",
        "Some text. ^^^ more text.",
        "Line 1\n------------------\nLine 2",
        "Wait for it... vvv",
    ]
    for t in texts:
        print(f"Original:\n{t}")
        print(f"Cleaned:\n{_strip_visual_artifacts(t)}")
        print("-" * 20)

def test_poll_normalization():
    print("\nTesting poll normalization...")
    texts = [
        "💬 Which do you prefer?\nOption 1 | Option 2 | Option 3",
        "💬 What's your take?\nA / B / C",
    ]
    for t in texts:
        print(f"Original:\n{t}")
        print(f"Cleaned:\n{_normalize_poll_separators(t)}")
        print("-" * 20)

def test_hashtag_deduplication():
    print("\nTesting hashtag deduplication...")
    texts = [
        "Post text\n\n#SystemDesign #Cloud #SystemDesign #Security",
        "Post text #Cloud #Cloud",
    ]
    for t in texts:
        print(f"Original: {t}")
        print(f"Cleaned:  {_deduplicate_hashtags(t)}")
        print("-" * 20)

if __name__ == "__main__":
    test_placeholder_stripping()
    test_visual_artifact_stripping()
    test_poll_normalization()
    test_hashtag_deduplication()
