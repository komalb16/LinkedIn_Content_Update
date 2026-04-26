
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from diagram_generator import DiagramGenerator

# Mock Slide Config
slides = [
    {"title": "1. The Scaling Challenge", "type": "Architecture"},
    {"title": "2. AI Optimization Roadmap", "type": "Modern Cards"},
    {"title": "3. Final Architectural State", "type": "Architecture"}
]

print("Running Mock Visual Test for Carousels...")
from diagram_generator import DiagramGenerator
dg = DiagramGenerator()

try:
    paths = dg.generate_carousel_bundle("test-carousel", "AI Scale Test", slides)
    for p in paths:
        print(f"Slide Generated: {p}")
    print("\nVisual Engine Verification: SUCCESS")
except Exception as e:
    print(f"Visual Engine Failure: {e}")
