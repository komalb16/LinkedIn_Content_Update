"""
Diagram Generator — Saves and manages SVG diagram files.
© Komal Batra
"""

import os
from datetime import datetime
from pathlib import Path
from logger import get_logger

log = get_logger("diagrams")

OUTPUT_DIR = "diagrams"


class DiagramGenerator:
    def __init__(self):
        Path(OUTPUT_DIR).mkdir(exist_ok=True)
        log.info(f"Diagram output directory: {OUTPUT_DIR}/")

    def save_svg(self, svg_content: str, topic_id: str) -> str:
        """Save SVG content to a file and return the path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{OUTPUT_DIR}/{topic_id}_{timestamp}.svg"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(svg_content)
        
        size_kb = os.path.getsize(filename) / 1024
        log.info(f"Diagram saved: {filename} ({size_kb:.1f} KB)")
        return filename

    def list_diagrams(self) -> list:
        """List all saved diagrams."""
        files = sorted(Path(OUTPUT_DIR).glob("*.svg"), reverse=True)
        return [str(f) for f in files]
