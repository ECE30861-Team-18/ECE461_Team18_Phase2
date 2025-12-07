import psycopg2
import os

conn = psycopg2.connect(
    host="team18-phase2-database.cuvgicoyg2el.us-east-1.rds.amazonaws.com",
    port=5432,
    database="",
    user="",
    password=""
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

# Create artifact_relationships table for lineage tracking
cur.execute("""
CREATE TABLE IF NOT EXISTS artifact_relationships (
    id SERIAL PRIMARY KEY,
    from_artifact_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    to_artifact_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    source TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(from_artifact_id, to_artifact_id, relationship_type)
);
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_relationships_from ON artifact_relationships(from_artifact_id);
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_relationships_to ON artifact_relationships(to_artifact_id);
""")

# Create artifact_dependencies table for dataset/code relationships (separate from lineage)
cur.execute("""
CREATE TABLE IF NOT EXISTS artifact_dependencies (
    id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    artifact_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    model_name TEXT,
    dependency_name TEXT,
    dependency_type TEXT NOT NULL,
    source TEXT DEFAULT 'auto_discovered',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(model_id, artifact_id, dependency_type)
);
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_dependencies_model ON artifact_dependencies(model_id);
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_dependencies_artifact ON artifact_dependencies(artifact_id);
""")

conn.commit()
cur.close()
conn.close()
print("✅ Tables created successfully!")
