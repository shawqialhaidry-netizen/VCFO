from dotenv import load_dotenv
import os
import psycopg2

load_dotenv()

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()

cur.execute("""
ALTER TABLE companies
ADD COLUMN IF NOT EXISTS group_id VARCHAR(36)
""")

cur.execute("""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_name = 'companies'
          AND constraint_name = 'fk_companies_group_id_groups'
    ) THEN
        ALTER TABLE companies
        ADD CONSTRAINT fk_companies_group_id_groups
        FOREIGN KEY (group_id) REFERENCES groups(id)
        ON DELETE SET NULL;
    END IF;
END$$;
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS ix_companies_group_id
ON companies(group_id)
""")

print("MANUAL DDL COMPLETION OK")

conn.close()
