#!/usr/bin/env python3
"""
style_showcase.py — Generate samples of all 23 diagram styles for your posts

Use this to:
1. See all 23 styles in action
2. Decide which styles work best for your content
3. Choose styles for specific topics
4. Design better posts using style variety
"""

import os
import sys
from diagram_generator import STYLES, make_diagram, get_pal

def generate_showcase():
    """Generate one diagram in each of the 23 styles."""
    
    output_dir = "diagrams/style_showcase"
    os.makedirs(output_dir, exist_ok=True)
    
    topics = [
        ("Claude 3.5 Sonnet Released", "claude-sonnet-release"),
        ("Open Weights LLMs Beat GPT-4", "open-weights-llm"),
        ("RAG Patterns 2026", "rag-patterns"),
        ("Kubernetes 1.31 Features", "k8s-131"),
        ("Data Engineering Best Practices", "data-eng-practices"),
    ]
    
    print("=" * 70)
    print("DIAGRAM STYLE SHOWCASE - Generating all 23 styles")
    print("=" * 70)
    
    for idx, style_fn in enumerate(STYLES):
        style_name = style_fn.__name__.replace("_style_", "").replace("_", " ").title()
        print(f"\n[{idx}] {style_name}")
        print("-" * 70)
        
        # Generate 5 different topics in this style to show diversity
        for topic_name, topic_id in topics:
            try:
                svg = make_diagram(
                    topic_name=topic_name,
                    topic_id=f"showcase-{topic_id}-style{idx}",
                    diagram_type="overview",
                    structure={
                        "subtitle": "Showcase",
                        "sections": [
                            {"label": "Feature 1", "desc": "Core capability"},
                            {"label": "Feature 2", "desc": "Secondary capability"},
                            {"label": "Feature 3", "desc": "Additional benefit"},
                        ]
                    },
                    style_override=idx
                )
                
                filename = f"{output_dir}/style_{idx:02d}_{topic_id}.svg"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(svg)
                
                print(f"  ✓ {topic_name[:40]:<40} → {os.path.basename(filename)}")
                
            except Exception as e:
                print(f"  ✗ {topic_name[:40]:<40} → ERROR: {e}")
    
    print("\n" + "=" * 70)
    print(f"✓ Showcase complete! Generated files in: {output_dir}")
    print("=" * 70)
    print("\nNEXT STEPS:")
    print("1. Open HTML file to view all styles side-by-side")
    print("2. Choose your favorite styles")
    print("3. Use 'style_override' parameter in make_diagram() for specific topics")
    print("4. Or edit trending_topics.py to enable all 23 styles for trending posts")
    print("=" * 70)


def generate_html_showcase():
    """Generate HTML page showing all styles side-by-side."""
    
    output_dir = "diagrams/style_showcase"
    
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Diagram Style Showcase - 23 Styles</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f5f5f5; margin: 20px; }
        h1 { text-align: center; color: #333; }
        .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 30px; margin: 20px 0; }
        .style-section { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .style-section h2 { margin-top: 0; color: #2563EB; font-size: 18px; }
        .style-section svg { max-width: 100%; height: auto; border: 1px solid #eee; border-radius: 4px; }
        .style-number { font-size: 12px; color: #999; margin-top: 10px; }
    </style>
</head>
<body>
    <h1>📊 All 23 Diagram Styles for LinkedIn Posts</h1>
    <p style="text-align: center; color: #666;">
        Click any diagram to see its full SVG. Use these for variety in your posts!
    </p>
    <div class="grid">
"""
    
    # Scan directory for SVG files
    if os.path.exists(output_dir):
        for fname in sorted(os.listdir(output_dir)):
            if fname.endswith(".svg"):
                style_num = fname.split("_")[1]
                svg_path = os.path.join(output_dir, fname)
                
                try:
                    with open(svg_path, "r", encoding="utf-8") as f:
                        svg_content = f.read()
                    
                    html += f"""
    <div class="style-section">
        <h2>Style #{style_num}</h2>
        {svg_content}
        <div class="style-number">File: {fname}</div>
    </div>
"""
                except Exception as e:
                    print(f"Error reading {fname}: {e}")
    
    html += """
    </div>
</body>
</html>
"""
    
    output_file = f"{output_dir}/showcase.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"✓ HTML showcase generated: {output_file}")


if __name__ == "__main__":
    print("\nGenerating style showcase...")
    generate_showcase()
    print("\nGenerating HTML showcase...")
    generate_html_showcase()
    print("\n✅ Done! View diagrams/style_showcase/showcase.html in your browser")
