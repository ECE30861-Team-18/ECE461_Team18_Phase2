import json
from rds_connection import run_query


def lambda_handler(event, context):
    """
    Retrieve the lineage graph for a model artifact.
    Returns nodes and edges representing dependencies and relationships.
    """
    try:
        # Extract path parameters
        path_params = event.get("pathParameters", {})
        artifact_id = path_params.get("id")
        
        if not artifact_id:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing artifact_id"})
            }
        
        # Verify artifact exists and is a model
        artifact_result = run_query(
            "SELECT id, name, type, metadata FROM artifacts WHERE id = %s;",
            (artifact_id,),
            fetch=True
        )
        
        if not artifact_result:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Artifact does not exist"})
            }
        
        artifact = artifact_result[0]
        if artifact["type"] != "model":
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Lineage is only supported for model artifacts"})
            }
        
        # Build lineage graph using BFS
        nodes = []
        edges = []
        visited = set()
        queue = [artifact_id]
        
        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)
            
            # Get artifact details
            current_artifact = run_query(
                "SELECT id, name, type, source_url, metadata FROM artifacts WHERE id = %s;",
                (current_id,),
                fetch=True
            )
            
            if not current_artifact:
                continue
                
            current = current_artifact[0]
            
            # Parse metadata to extract lineage info
            metadata = current.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}
            
            # Add node
            node = {
                "artifact_id": str(current["id"]),
                "name": current["name"],
                "source": "database"
            }
            
            # Check for config.json references in metadata
            if metadata.get("base_model_name"):
                node["source"] = "config_json"
                node["metadata"] = {
                    "repository_url": current.get("source_url"),
                    "base_model": metadata.get("base_model_name")
                }
            
            nodes.append(node)
            
            # Get all relationships where this artifact is involved
            relationships = run_query(
                """
                SELECT from_artifact_id, to_artifact_id, relationship_type, source
                FROM artifact_relationships
                WHERE from_artifact_id = %s OR to_artifact_id = %s;
                """,
                (current_id, current_id),
                fetch=True
            )
            
            for rel in relationships:
                edge = {
                    "from_node_artifact_id": str(rel["from_artifact_id"]),
                    "to_node_artifact_id": str(rel["to_artifact_id"]),
                    "relationship": rel["relationship_type"]
                }
                
                # Avoid duplicate edges
                if edge not in edges:
                    edges.append(edge)
                
                # Queue related artifacts for traversal
                if rel["from_artifact_id"] != int(current_id):
                    queue.append(str(rel["from_artifact_id"]))
                if rel["to_artifact_id"] != int(current_id):
                    queue.append(str(rel["to_artifact_id"]))
            
            # Also check metadata for related_artifacts
            if metadata.get("related_artifacts"):
                for related in metadata["related_artifacts"]:
                    related_id = str(related.get("artifact_id"))
                    relationship = related.get("relationship", "related_to")
                    
                    edge = {
                        "from_node_artifact_id": str(current_id) if related.get("direction") == "from" else related_id,
                        "to_node_artifact_id": related_id if related.get("direction") == "from" else str(current_id),
                        "relationship": relationship
                    }
                    
                    if edge not in edges:
                        edges.append(edge)
                    
                    if related_id not in visited:
                        queue.append(related_id)
        
        # Return lineage graph
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "nodes": nodes,
                "edges": edges
            })
        }
        
    except Exception as e:
        print(f"Error in lineage retrieval: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
