import sqlite3

conn = sqlite3.connect('linkedin_generator.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print('✅ SQLite Database Tables Created:')
for table in tables:
    print(f'  ✓ {table[0]}')

print(f'\n✅ Total tables created: {len(tables)}')
conn.close()
