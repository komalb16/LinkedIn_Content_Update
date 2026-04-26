"""
build_tracker.py - Scans the project for recent engineering milestones.
"""
import os
import time
from pathlib import Path

def get_recent_milestones(directory="src", days=7):
    """Scans for recently modified files as a proxy for 'work done'."""
    milestones = []
    root = Path(directory).resolve()
    current_time = time.time()
    
    # Check for file changes
    for path in root.rglob("*.py"):
        if path.is_file():
            stat = path.stat()
            age_days = (current_time - stat.st_mtime) / (24 * 3600)
            if age_days <= days:
                milestones.append(f"Modified {path.name} ({int(age_days)} days ago)")
                
    # Check for recent git commits if available
    try:
        import subprocess
        git_log = subprocess.check_output(
            ["git", "log", "--since=7.days.ago", "--pretty=format:%s"],
            cwd=str(root.parent),
            stderr=subprocess.DEVNULL
        ).decode("utf-8")
        if git_log:
            milestones.extend([f"Commit: {line}" for line in git_log.split("\n") if line])
    except:
        pass
        
    return sorted(list(set(milestones)))[:10]
