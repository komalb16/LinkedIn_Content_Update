import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))

from diagram_generator import DiagramGenerator

gen = DiagramGenerator()

# Test Case 1: Pyramid Model with custom structure
print("Generating Pyramid Model with custom structure...")
structure = {
    "sections": [
        {"label": "Tier 1: Strategy", "desc": "High-level goal setting and alignment."},
        {"label": "Tier 2: Planning", "desc": "Resource allocation and roadmap design."},
        {"label": "Tier 3: Execution", "desc": "Day-to-day operations and sprint cycles."},
        {"label": "Tier 4: Monitoring", "desc": "KPI tracking and feedback loops."}
    ],
    "subtitle": "Management Workflow Hierarchy"
}

# Style 2 is _style_pyramid
# We use style_override=2 to force the pyramid style specifically
path = gen.save_svg(None, "test_pyramid_fix", "Workflow Hierarchy", "Pyramid", structure=structure)
# Wait, save_svg doesn't take style_override. I'll use make_diagram directly or check how save_svg calls it.
# Actually, I'll just check if it picked style 2 this time by changing the topic/type slightly.
# Or I can just manually invoke style 2 in a new script.


# Test Case 2: Timeline with custom structure
print("\nGenerating Timeline with custom structure...")
timeline_structure = {
    "sections": [
        {"label": "Q1 2024", "desc": "Foundation phase and initial setup."},
        {"label": "Q2 2024", "desc": "Beta testing and user feedback."},
        {"label": "Q3 2024", "desc": "Scale phase and global rollout."}
    ]
}
# Style 3 is _style_timeline
path2 = gen.save_svg(None, "test_timeline_fix", "Product Roadmap", "Timeline", structure=timeline_structure)
print(f"Generated diagram: {path2}")
