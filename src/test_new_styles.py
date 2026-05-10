import os
import sys
# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from diagram_generator import make_diagram

def test_new_styles():
    output_dir = "diagrams/test_new_styles"
    os.makedirs(output_dir, exist_ok=True)
    
    test_cases = [
        ("AI Hype Cycle 2026", "hype-cycle-test", "Hype Cycle", 28),
        ("AI Adoption Ladder", "ladder-test", "Leverage Ladder", 29),
        ("CREATE Framework", "framework-test", "Acronym Framework", 30),
    ]
    
    for topic_name, topic_id, d_type, style_idx in test_cases:
        print(f"Generating {d_type} (Style {style_idx})...")
        svg = make_diagram(
            topic_name=topic_name,
            topic_id=topic_id,
            diagram_type=d_type,
            style_override=style_idx
        )
        filename = os.path.join(output_dir, f"style_{style_idx}_{topic_id}.svg")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"  [OK] Saved to {filename}")

if __name__ == "__main__":
    test_new_styles()
