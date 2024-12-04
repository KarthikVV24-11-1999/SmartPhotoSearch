import json
import boto3
import requests
import os
from requests.auth import HTTPBasicAuth

# Initialize Lex V2 client
lex_client = boto3.client('lexv2-runtime')

# OpenSearch details from environment variables
ES_ENDPOINT = os.environ['OPENSEARCH_ENDPOINT']
MASTER_USER = os.environ['MASTER_USERNAME']
MASTER_PASSWORD = os.environ['MASTER_PASSWORD']

def lambda_handler(event, context):
    query = event.get("query", "").strip()
    if not query:
        return format_response([])

    # Step 1: Disambiguate query using Lex
    lex_response = call_lex(query)
    keywords = extract_keywords_from_lex(lex_response)
    
    if not keywords:
        return format_response([])

    # Step 2: Search OpenSearch using keywords
    search_results = search_opensearch(keywords)
    return format_response(search_results)

def call_lex(query):
    """Call Amazon Lex to process the query and extract intent/keywords."""
    bot_id = os.environ['LEX_BOT_ID']
    bot_alias_id = os.environ['LEX_BOT_ALIAS_ID']
    locale_id = "en_US"  # Adjust as needed
    
    response = lex_client.recognize_text(
        botId=bot_id,
        botAliasId=bot_alias_id,
        localeId=locale_id,
        sessionId="search-session",
        text=query
    )
    return response

def extract_keywords_from_lex(lex_response):
    """Extract keywords from Lex response slots."""
    try:
        slots = lex_response.get("sessionState", {}).get("intent", {}).get("slots", {})
        keywords = [slot["value"]["interpretedValue"] for slot in slots.values() if slot]
        return keywords
    except KeyError:
        return []

def search_opensearch(keywords):
    """Search OpenSearch for photos with the given keywords using basic authentication."""
    search_body = {
        "query": {
            "bool": {
                "should": [{"match": {"labels": keyword}} for keyword in keywords],
                "minimum_should_match": 1
            }
        }
    }
    headers = {"Content-Type": "application/json"}
    
    # Perform the search using basic authentication
    response = requests.post(
        f'{ES_ENDPOINT}/photos/_search',
        headers=headers,
        json=search_body,
        auth=HTTPBasicAuth(MASTER_USER, MASTER_PASSWORD)
    )
    
    if response.status_code == 200:
        hits = response.json().get("hits", {}).get("hits", [])
        return [format_es_result(hit) for hit in hits]
    else:
        return []

def format_es_result(hit):
    """Format OpenSearch results to include presigned URL."""
    source = hit["_source"]
    bucket_name = source.get("bucket")
    object_key = source.get("objectKey")

    presigned_url = generate_presigned_url(bucket_name, object_key)

    return {
        "objectKey": object_key,
        "bucket": bucket_name,
        "createdTimestamp": source.get("createdTimestamp"),
        "labels": source.get("labels"),
        "url": presigned_url  # Include the presigned URL
    }

s3 = boto3.client('s3')
def generate_presigned_url(bucket_name, object_key, expiration=3600):
    """Generate a presigned URL for S3 object access."""
    try:
        return s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=expiration
        )
    except Exception as e:
        print(f"Error generating presigned URL: {e}")
        return None


def format_response(results):
    """Format the response as expected by the API spec."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": results
    }
