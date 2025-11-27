import json
from rds_connection import run_query


def lambda_handler(event, context):
    """
    Retrieve the lineage graph for a model artifact.
    Builds nodes and edges ONLY from DB relationships.
    """
    try:
        # -------------------------------
        # Extract & validate artifact ID
        # -------------------------------
        path_params = event.get("pathParameters", {})
        artifact_id = path_params.get("id")

        if not artifact_id:
            print("artifact_id missing")
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing artifact_id"})
            }

        try:
            artifact_id = int(artifact_id)
        except ValueError:
            print("invalid artifact_id")
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Invalid artifact_id"})
            }

        # Validate the artifact exists
        artifact = run_query(
            "SELECT id, name, type, metadata FROM artifacts WHERE id = %s;",
            (artifact_id,),
            fetch=True
        )

        if not artifact:
            print("artifact not found")
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Artifact does not exist"})
            }

        artifact = artifact[0]

        # Only models have lineage (per spec)
        if artifact["type"] != "model":
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Lineage is only supported for model artifacts"})
            }

        # -------------------------------
        # BFS over artifact_relationships
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

            # Load artifact info
            result = run_query(
                "SELECT id, name, type, metadata FROM artifacts WHERE id = %s;",
                (current_id,),
                fetch=True
            )
            if not result:
                continue

            curr = result[0]
            metadata = curr.get("metadata")
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except:
                    metadata = {}

            # -------------------------------
            # Add node
            # -------------------------------
            if current_id not in nodes:
                node = {
                    "artifact_id": str(curr["id"]),
                    "name": curr["name"],
                    "source": "database"
                }
                nodes[current_id] = node

            # -------------------------------
            # Add placeholder parent (auto_lineage)
            # e.g., {"parent": "bert-base-uncased", "source": "config_json"}
            # -------------------------------
            auto = metadata.get("auto_lineage")
            if auto:
                parent_name = auto.get("parent")
                origin = auto.get("source", "config_json")

                # Add the parent as a synthetic node (string ID)
                parent_node_id = f"external:{parent_name}"

                if parent_node_id not in nodes:
                    nodes[parent_node_id] = {
                        "artifact_id": parent_node_id,
                        "name": parent_name,
                        "source": origin
                    }

                # Edge from parent → current model
                edge = {
                    "from_node_artifact_id": parent_node_id,
                    "to_node_artifact_id": current_id,
                    "relationship": "base_model"
                }
                if edge not in edges:
                    edges.append(edge)

            # -------------------------------
            # Load explicit DB relationships
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
                relationship = rel["relationship_type"]

                edge = {
                    "from_node_artifact_id": from_id,
                    "to_node_artifact_id": to_id,
                    "relationship": relationship
                }

                if edge not in edges:
                    edges.append(edge)

                # enqueue both directions
                if from_id not in visited:
                    queue.append(from_id)
                if to_id not in visited:
                    queue.append(to_id)

        # -------------------------------
        # Build final lineage response
        # -------------------------------
        response_graph = {
            "nodes": list(nodes.values()),
            "edges": edges
        }

        print("returning lineage graph:", response_graph)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response_graph)
        }

    except Exception as e:
        print("Lineage error:", str(e))
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }
