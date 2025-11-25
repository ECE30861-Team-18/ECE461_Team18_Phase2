import json
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rds_connection import run_query


def round_to_half(value):
    """Round a value to the nearest 0.5, return int if whole number"""
    rounded = round(value * 2) / 2
    return int(rounded) if rounded == int(rounded) else rounded


def lambda_handler(event, context):
    """
    Handler for GET /artifact/{artifact_type}/{id}/cost
    Returns cost in MB based on artifact storage size.
    
    Cost is calculated from metadata.used_storage (bytes) / (1024 * 1024) = MB
    Costs are calculated once and stored in database (metadata.standalone_cost, metadata.total_cost)
    
    Response format:
    - Without dependency: {"artifact_id": {"standalone_cost": float, "total_cost": float}} (equal values)
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
        
        # Check if costs are already calculated and stored
        if 'standalone_cost' in metadata and 'total_cost' in metadata:
            print(f"[COST] Using stored costs for artifact {artifact_id_int}")
            standalone_cost = metadata['standalone_cost']
            total_cost = metadata['total_cost']
            
            if not dependency:
                # Return only this artifact
                cost_response = {
                    str(artifact_id): {
                        "standalone_cost": standalone_cost,
                        "total_cost": total_cost
                    }
                }
            else:
                # Return this artifact and all its dependencies with their stored costs
                cost_response = {
                    str(artifact_id): {
                        "standalone_cost": standalone_cost,
                        "total_cost": total_cost
                    }
                }
                
                dependencies_list = metadata.get('dependencies', [])
                if dependencies_list:
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
                            
                            cost_response[str(dep['id'])] = {
                                "standalone_cost": dep_metadata.get('standalone_cost', 0),
                                "total_cost": dep_metadata.get('total_cost', 0)
                            }
        else:
            # Calculate costs for the first time
            print(f"[COST] Calculating costs for artifact {artifact_id_int}")
            
            # Get storage in bytes and convert to MB
            used_storage_bytes = metadata.get('used_storage', 0)
            storage_mb = float(used_storage_bytes) / (1024 * 1024) if used_storage_bytes else 0.0
            standalone_cost = round_to_half(storage_mb)
            
            # Get dependencies
            dependencies_list = metadata.get('dependencies', [])
            
            # Collect all artifacts to update (main + dependencies)
            artifacts_to_update = {
                artifact_id_int: {
                    'standalone_cost': standalone_cost,
                    'metadata': metadata
                }
            }
            
            if dependencies_list:
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
                        dep_standalone = round_to_half(dep_storage_mb)
                        
                        artifacts_to_update[dep['id']] = {
                            'standalone_cost': dep_standalone,
                            'metadata': dep_metadata
                        }
            
            # Calculate total cost (sum of all standalone costs)
            total_cost = sum(art['standalone_cost'] for art in artifacts_to_update.values())
            total_cost = round_to_half(total_cost)
            
            # Update all artifacts in the database with their costs
            for art_id, art_data in artifacts_to_update.items():
                art_metadata = art_data['metadata']
                art_metadata['standalone_cost'] = art_data['standalone_cost']
                art_metadata['total_cost'] = total_cost
                
                update_sql = """
                UPDATE artifacts
                SET metadata = %s
                WHERE id = %s;
                """
                run_query(update_sql, params=(json.dumps(art_metadata), art_id), fetch=False)
                print(f"[COST] Updated costs for artifact {art_id}: standalone={art_data['standalone_cost']}, total={total_cost}")
            
            # Build response
            if not dependency:
                cost_response = {
                    str(artifact_id): {
                        "standalone_cost": standalone_cost,
                        "total_cost": total_cost
                    }
                }
            else:
                cost_response = {}
                for art_id, art_data in artifacts_to_update.items():
                    cost_response[str(art_id)] = {
                        "standalone_cost": art_data['standalone_cost'],
                        "total_cost": total_cost
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
