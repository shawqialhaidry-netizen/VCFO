from dotenv import load_dotenv
import os
import psycopg2

load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()

cur.execute("""
ALTER TABLE alembic_version
ALTER COLUMN version_num TYPE VARCHAR(255)
""")

print("ALEMBIC VERSION COLUMN RESIZED OK")

conn.close()
