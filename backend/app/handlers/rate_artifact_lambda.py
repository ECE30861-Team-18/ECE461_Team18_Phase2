import json
from rds_connection import run_query


def lambda_handler(event, context):
    """
    GET /artifact/model/{id}/rate
    Returns the rating/metrics for a model artifact.
    """
    print(f"[RATE] Incoming event: {json.dumps(event, indent=2)}")
    
    try:
        # Extract artifact ID from path parameters
        path_params = event.get("pathParameters", {})
        artifact_id = path_params.get("id")
        
        if not artifact_id:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing artifact ID"})
            }
        
        # Convert to integer for database query
        try:
            artifact_id = int(artifact_id)
        except (ValueError, TypeError):
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Invalid artifact ID format"})
            }
        
        print(f"[RATE] Fetching ratings for artifact ID: {artifact_id}")
        
        # Query artifact with ratings
        sql = """
        SELECT id, type, name, ratings, metadata
        FROM artifacts
        WHERE id = %s AND type = 'model';
        """
        
        results = run_query(sql, params=(artifact_id,), fetch=True)
        
        if not results or len(results) == 0:
            print(f"[RATE] Artifact {artifact_id} not found or not a model")
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Artifact does not exist"})
            }
        
        artifact = results[0]
        ratings_json = artifact.get("ratings")
        metadata_json = artifact.get("metadata")
        
        # Parse ratings JSON if it's a string
        if isinstance(ratings_json, str):
            try:
                ratings = json.loads(ratings_json)
            except json.JSONDecodeError:
                ratings = {}
        else:
            ratings = ratings_json or {}
        
        # Parse metadata JSON if it's a string
        if isinstance(metadata_json, str):
            try:
                metadata = json.loads(metadata_json)
            except json.JSONDecodeError:
                metadata = {}
        else:
            metadata = metadata_json or {}
        
        print(f"[RATE] Ratings data: {json.dumps(ratings, indent=2)}")
        
        # Build ModelRating response according to spec
        # Required fields with defaults
        model_rating = {
            "name": artifact.get("name", ""),
            "category": metadata.get("category", "model"),
            "net_score": ratings.get("net_score", 0.0),
            "net_score_latency": ratings.get("net_score_latency", 0.0),
            "ramp_up_time": ratings.get("ramp_up_time", 0.0),
            "ramp_up_time_latency": ratings.get("ramp_up_time_latency", 0.0),
            "bus_factor": ratings.get("bus_factor", 0.0),
            "bus_factor_latency": ratings.get("bus_factor_latency", 0.0),
            "performance_claims": ratings.get("performance_claims", 0.0),
            "performance_claims_latency": ratings.get("performance_claims_latency", 0.0),
            "license": ratings.get("license", 0.0),
            "license_latency": ratings.get("license_latency", 0.0),
            "dataset_and_code_score": ratings.get("dataset_and_code_score", 0.0),
            "dataset_and_code_score_latency": ratings.get("dataset_and_code_score_latency", 0.0),
            "dataset_quality": ratings.get("dataset_quality", 0.0),
            "dataset_quality_latency": ratings.get("dataset_quality_latency", 0.0),
            "code_quality": ratings.get("code_quality", 0.0),
            "code_quality_latency": ratings.get("code_quality_latency", 0.0),
            "reproducibility": ratings.get("reproducibility", 0.0),
            "reproducibility_latency": ratings.get("reproducibility_latency", 0.0),
            "reviewedness": ratings.get("reviewedness", 0.0),
            "reviewedness_latency": ratings.get("reviewedness_latency", 0.0),
            "tree_score": ratings.get("tree_score", 0.0),
            "tree_score_latency": ratings.get("tree_score_latency", 0.0),
            "size_score": ratings.get("size_score", {
                "raspberry_pi": 0.0,
                "jetson_nano": 0.0,
                "laptop": 0.0,
                "workstation": 0.0,
                "cloud_server": 0.0
            }),
            "size_score_latency": ratings.get("size_score_latency", 0.0)
        }
        
        print(f"[RATE] Returning model rating with net_score: {model_rating['net_score']}")
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "OPTIONS,GET",
                "Access-Control-Allow-Headers": "Content-Type,X-Authorization"
            },
            "body": json.dumps(model_rating, default=str)
        }
        
    except Exception as e:
        print(f"[RATE] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error", "details": str(e)})
        }
