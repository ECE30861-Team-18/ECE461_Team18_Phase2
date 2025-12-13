from cors import CORS_HEADERS


def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json", **CORS_HEADERS},
        "body": '{"status":"OK"}'
    }
