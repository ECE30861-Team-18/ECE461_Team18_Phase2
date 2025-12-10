import json
from rds_connection import run_query
from auth import require_auth


def lambda_handler(event, context):
    """
    Retrieve the lineage graph for a model artifact.
    Lineage includes ONLY models.
    """
    try:
        # Validate authentication
        valid, error_response = require_auth(event)
        if not valid:
            return error_response
        
        # -------------------------------
        # Extract & validate artifact ID
        # -------------------------------
        path_params = event.get("pathParameters", {})
        artifact_id = path_params.get("id")

        if not artifact_id:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing artifact_id"})
            }

        try:
            artifact_id = int(artifact_id)
        except ValueError:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Invalid artifact_id"})
            }

        # -------------------------------
        # Validate root artifact
        # -------------------------------
        root_result = run_query(
            "SELECT id, name, type FROM artifacts WHERE id = %s;",
            (artifact_id,),
            fetch=True
        )

        if not root_result:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Artifact does not exist"})
            }

        root = root_result[0]

        if root["type"] != "model":
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Lineage is only supported for model artifacts"})
            }

        # -------------------------------
        # BFS over model relationships
        # -------------------------------
        nodes = {}
        edges = []
        visited = set()
        queue = [str(artifact_id)]

        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            # Load artifact
            result = run_query(
                "SELECT id, name, type, metadata FROM artifacts WHERE id = %s;",
                (current_id,),
                fetch=True
            )
            if not result:
                continue

            curr = result[0]
            if curr["type"] != "model":
                continue

            # Parse metadata
            metadata = curr.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}

            # -------------------------------
            # Add node
            # -------------------------------
            if current_id not in nodes:
                nodes[current_id] = {
                    "artifact_id": current_id,
                    "name": curr["name"],
                    "source": "database"
                }

            # -------------------------------
            # Handle auto_lineage (config-derived)
            # -------------------------------
            auto_lineage = metadata.get("auto_lineage", [])
            for entry in auto_lineage:
                parent = entry.get("artifact_id")
                relationship = entry.get("relationship", "derived_from")
                is_placeholder = entry.get("placeholder", False)

                if not parent:
                    continue

                if is_placeholder:
                    parent_node_id = f"external:{parent}"
                    if parent_node_id not in nodes:
                        nodes[parent_node_id] = {
                            "artifact_id": parent_node_id,
                            "name": parent,
                            "source": "config_json"
                        }
                    from_id = parent_node_id
                else:
                    from_id = str(parent)
                    if from_id not in visited:
                        queue.append(from_id)

                edge = {
                    "from_node_artifact_id": from_id,
                    "to_node_artifact_id": current_id,
                    "relationship": relationship
                }
                if edge not in edges:
                    edges.append(edge)

            # -------------------------------
            # Handle DB relationships
            # -------------------------------
            rels = run_query(
                """
                SELECT from_artifact_id, to_artifact_id, relationship_type
                FROM artifact_relationships
                WHERE from_artifact_id = %s OR to_artifact_id = %s;
                """,
                (current_id, current_id),
                fetch=True
            )

            for rel in rels:
                from_id = str(rel["from_artifact_id"])
                to_id = str(rel["to_artifact_id"])

                # Only model→model edges
                if from_id == to_id:
                    continue

                edge = {
                    "from_node_artifact_id": from_id,
                    "to_node_artifact_id": to_id,
                    "relationship": rel["relationship_type"]
                }

                if edge not in edges:
                    edges.append(edge)

                if from_id not in visited:
                    queue.append(from_id)
                if to_id not in visited:
                    queue.append(to_id)

        # -------------------------------
        # Final response
        # -------------------------------
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "nodes": list(nodes.values()),
                "edges": edges
            })
        }

    except Exception as e:
        print("Lineage error:", str(e))
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
