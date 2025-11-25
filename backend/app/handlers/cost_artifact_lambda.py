import json


def lambda_handler(event, context):
    """
    Handler for GET /artifact/{artifact_type}/{id}/cost
    Returns empty cost response.
    """
    try:
        # Extract path parameters
        path_params = event.get('pathParameters', {})
        artifact_id = path_params.get('id')
        
        if not artifact_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'Missing artifact ID'})
            }
        
        # Return empty cost object keyed by artifact ID
        cost_response = {
            str(artifact_id): {}
        }
        
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
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }
