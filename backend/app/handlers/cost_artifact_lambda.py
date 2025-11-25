import json
import sys
import os
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rds_connection import run_query

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Handler for GET /artifact/{artifact_type}/{id}/cost
    Returns cost information for an artifact and optionally its dependencies.
    
    Query parameter:
    - dependency (boolean, default=false): Whether to include dependency costs
    
    Response format:
    {
        "artifact_id": {
            "standalone_cost": float (MB, only if dependency=true),
            "total_cost": float (MB)
        },
        ... (additional entries if dependency=true)
    }
    """
    try:
        logger.info(f"[COST DEBUG] Event: {json.dumps(event)}")
        
        # Extract path parameters
        path_params = event.get('pathParameters', {})
        artifact_type = path_params.get('artifact_type')
        artifact_id = path_params.get('id')
        
        # Extract query parameters
        query_params = event.get('queryStringParameters') or {}
        dependency = query_params.get('dependency', 'false').lower() == 'true'
        
        logger.info(f"[COST DEBUG] artifact_type={artifact_type}, id={artifact_id}, dependency={dependency}")
        
        if not artifact_id or not artifact_type:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing artifact_type or id'})
            }
        
        # Convert artifact_id to integer
        try:
            artifact_id = int(artifact_id)
        except ValueError:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Invalid artifact_id. Must be an integer'})
            }
        
        # Validate artifact_type
        valid_types = ['model', 'dataset', 'code']
        if artifact_type not in valid_types:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': f'Invalid artifact_type. Must be one of: {valid_types}'})
            }
        
        # Query the artifact
        query = """
            SELECT id, name, type, metadata
            FROM artifacts
            WHERE id = %s AND type = %s
        """
        
        logger.info(f"[COST DEBUG] Executing query with params: artifact_id={artifact_id} (type={type(artifact_id)}), artifact_type={artifact_type}")
        result = run_query(query, (artifact_id, artifact_type), fetch=True)
        logger.info(f"[COST DEBUG] Query result: {result}")
        logger.info(f"[COST DEBUG] Query result type: {type(result)}")
        
        if not result:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Artifact does not exist'})
            }
        
        artifact = result[0]
        metadata = artifact[3]
        
        # Parse metadata if it's a string
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}
        elif not isinstance(metadata, dict):
            metadata = {}
        
        # Calculate standalone cost from metadata
        # Size is typically in metadata, defaulting to 0 if not present
        standalone_cost = float(metadata.get('size', 0))
        
        logger.info(f"[COST DEBUG] Artifact {artifact_id} standalone_cost: {standalone_cost}")
        
        if not dependency:
            # Return just the total cost (same as standalone when no dependencies)
            response_body = {
                artifact_id: {
                    "total_cost": standalone_cost
                }
            }
        else:
            # Query dependencies from metadata
            dependencies = metadata.get('dependencies', [])
            logger.info(f"[COST DEBUG] Dependencies: {dependencies}")
            
            # Calculate costs for dependencies
            dependency_costs = {}
            total_cost = standalone_cost
            
            if dependencies:
                # Query all dependencies
                dep_ids = [dep.get('id') for dep in dependencies if dep.get('id')]
                
                if dep_ids:
                    placeholders = ','.join(['%s'] * len(dep_ids))
                    dep_query = f"""
                        SELECT id, metadata
                        FROM artifacts
                        WHERE id IN ({placeholders})
                    """
                    
                    dep_results = run_query(dep_query, tuple(dep_ids), fetch=True)
                    
                    for dep in dep_results:
                        dep_id = dep[0]
                        dep_metadata = dep[1]
                        
                        # Parse dependency metadata
                        if isinstance(dep_metadata, str):
                            try:
                                dep_metadata = json.loads(dep_metadata)
                            except:
                                dep_metadata = {}
                        elif not isinstance(dep_metadata, dict):
                            dep_metadata = {}
                        
                        dep_cost = float(dep_metadata.get('size', 0))
                        dependency_costs[dep_id] = {
                            "standalone_cost": dep_cost,
                            "total_cost": dep_cost
                        }
                        total_cost += dep_cost
            
            # Build response with main artifact and dependencies
            response_body = {
                artifact_id: {
                    "standalone_cost": standalone_cost,
                    "total_cost": total_cost
                }
            }
            
            # Add dependency entries
            response_body.update(dependency_costs)
        
        logger.info(f"[COST DEBUG] Response: {json.dumps(response_body)}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(response_body)
        }
        
    except Exception as e:
        logger.error(f"[COST DEBUG] Error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'The artifact cost calculator encountered an error'})
        }
