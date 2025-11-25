import json
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rds_connection import run_query


def lambda_handler(event, context):
    """
    Handler for GET /artifact/{artifact_type}/{id}/cost
    Returns cost in MB based on artifact storage size.
    
    Cost is calculated from metadata.used_storage (bytes) / (1024 * 1024) = MB
    
    Response format:
    - Without dependency: {"artifact_id": {"total_cost": float}}
    - With dependency: {"artifact_id": {"standalone_cost": float, "total_cost": float}, ...}
    """
    try:
        print(f"[COST] Event: {json.dumps(event)}")
        
        # Extract path parameters
        path_params = event.get('pathParameters', {})
        artifact_id = path_params.get('id')
        artifact_type = path_params.get('artifact_type')
        
        print(f"[COST] artifact_type={artifact_type}, artifact_id={artifact_id}")
        
        if not artifact_id or not artifact_type:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing artifact_id or artifact_type'})
            }
        
        # Convert artifact_id to integer
        try:
            artifact_id_int = int(artifact_id)
        except (ValueError, TypeError):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Invalid artifact ID format'})
            }
        
        # Extract query parameters
        query_params = event.get('queryStringParameters') or {}
        dependency = query_params.get('dependency', 'false').lower() == 'true'
        
        print(f"[COST] dependency={dependency}, querying artifact {artifact_id_int}")
        
        # Query artifact to check if it exists and get its storage
        sql = """
        SELECT id, type, metadata
        FROM artifacts
        WHERE id = %s AND type = %s;
        """
        
        results = run_query(sql, params=(artifact_id_int, artifact_type), fetch=True)
        
        if not results or len(results) == 0:
            print(f"[COST] Artifact {artifact_id_int} not found")
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Artifact does not exist'})
            }
        
        artifact = results[0]
        metadata = artifact.get('metadata', {})
        
        # Parse metadata if it's a string
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        
        # Get storage in bytes and convert to MB
        used_storage_bytes = metadata.get('used_storage', 0)
        storage_mb = float(used_storage_bytes) / (1024 * 1024) if used_storage_bytes else 0.0
        
        if dependency:
            # Query dependencies from metadata
            dependencies_list = metadata.get('dependencies', [])
            
            cost_response = {
                str(artifact_id): {
                    "standalone_cost": round(storage_mb, 2),
                    "total_cost": round(storage_mb, 2)
                }
            }
            
            # Calculate total cost including dependencies
            total_cost = storage_mb
            
            if dependencies_list:
                # Query all dependencies
                dep_ids = [int(dep) for dep in dependencies_list if isinstance(dep, (int, str))]
                
                if dep_ids:
                    placeholders = ','.join(['%s'] * len(dep_ids))
                    dep_sql = f"""
                    SELECT id, metadata
                    FROM artifacts
                    WHERE id IN ({placeholders});
                    """
                    
                    dep_results = run_query(dep_sql, params=tuple(dep_ids), fetch=True)
                    
                    for dep in dep_results:
                        dep_metadata = dep.get('metadata', {})
                        if isinstance(dep_metadata, str):
                            try:
                                dep_metadata = json.loads(dep_metadata)
                            except json.JSONDecodeError:
                                dep_metadata = {}
                        
                        dep_storage_bytes = dep_metadata.get('used_storage', 0)
                        dep_storage_mb = float(dep_storage_bytes) / (1024 * 1024) if dep_storage_bytes else 0.0
                        
                        total_cost += dep_storage_mb
                        
                        cost_response[str(dep['id'])] = {
                            "standalone_cost": round(dep_storage_mb, 2),
                            "total_cost": round(dep_storage_mb, 2)
                        }
            
            # Update main artifact's total cost
            cost_response[str(artifact_id)]["total_cost"] = round(total_cost, 2)
        else:
            # When dependency=false, return both standalone_cost and total_cost (they're equal)
            cost_response = {
                str(artifact_id): {
                    "standalone_cost": round(storage_mb, 2),
                    "total_cost": round(storage_mb, 2)
                }
            }
        
        print(f"[COST] Returning response: {json.dumps(cost_response)}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,GET',
                'Access-Control-Allow-Headers': 'Content-Type,X-Authorization'
            },
            'body': json.dumps(cost_response)
        }
        
    except Exception as e:
        print(f"[COST] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }
