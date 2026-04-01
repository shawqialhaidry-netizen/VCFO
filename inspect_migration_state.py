from dotenv import load_dotenv
import os
import psycopg2

load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("select version_num from alembic_version")
print("ALEMBIC =", cur.fetchall())

cur.execute("select exists (select 1 from information_schema.tables where table_schema='public' and table_name='groups')")
print("groups =", cur.fetchone()[0])

cur.execute("select exists (select 1 from information_schema.tables where table_schema='public' and table_name='group_memberships')")
print("group_memberships =", cur.fetchone()[0])

cur.execute("select exists (select 1 from information_schema.columns where table_schema='public' and table_name='companies' and column_name='group_id')")
print("companies.group_id =", cur.fetchone()[0])

conn.close()
