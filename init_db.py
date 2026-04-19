#!/usr/bin/env python
"""Initialize database by first loading .env variables"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env file
load_dotenv()

# Now initialize database
from backend.database import init_db

try:
    init_db()
    print("✅ Database initialized successfully!")
    
    # Verify tables
    import sqlite3
    conn = sqlite3.connect('linkedin_generator.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"\n✅ Created {len(tables)} tables:")
    for table in tables:
        print(f"  ✓ {table[0]}")
    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
