import psycopg2
import os

conn = psycopg2.connect(
    host="team18-phase2-database.cuvgicoyg2el.us-east-1.rds.amazonaws.com",
    port=5432,
    database="Team18_Model_Registry",
    user="Team18",
    password="ElwaAsteroidFoob18"
)

cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS artifacts (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT,
    source_url TEXT NOT NULL,
    download_url TEXT,
    net_score FLOAT,
    ratings JSONB,
    status TEXT DEFAULT 'upload_pending',
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
""")
conn.commit()
cur.close()
conn.close()
print("✅ Table created successfully!")
