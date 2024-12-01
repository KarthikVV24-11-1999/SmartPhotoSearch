import json
import boto3
import requests
import os

# Initialize Lex V2 client
lex_client = boto3.client('lexv2-runtime')

# ElasticSearch (OpenSearch) details from environment variables
ES_ENDPOINT = os.environ['OPENSEARCH_ENDPOINT']

def lambda_handler(event, context):
    query = event.get("queryStringParameters", {}).get("q", "").strip()
    if not query:
        return format_response([])

    # Step 1: Disambiguate query using Lex
    lex_response = call_lex(query)
    keywords = extract_keywords_from_lex(lex_response)
    
    if not keywords:
        return format_response([])

    # Step 2: Search ElasticSearch using keywords
    search_results = search_elasticsearch(keywords)
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


def search_elasticsearch(keywords):
    """Search ElasticSearch for photos with the given keywords."""
    search_body = {
        "query": {
            "bool": {
                "should": [{"match": {"labels": keyword}} for keyword in keywords],
                "minimum_should_match": 1
            }
        }
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(
        f'{ES_ENDPOINT}/photos/_search',
        headers=headers,
        json=search_body
    )
    if response.status_code == 200:
        hits = response.json().get("hits", {}).get("hits", [])
        return [format_es_result(hit) for hit in hits]
    else:
        return []


def format_es_result(hit):
    """Format ElasticSearch results to return relevant fields."""
    source = hit["_source"]
    return {
        "objectKey": source.get("objectKey"),
        "bucket": source.get("bucket"),
        "createdTimestamp": source.get("createdTimestamp"),
        "labels": source.get("labels")
    }


def format_response(results):
    """Format the response as expected by the API spec."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(results)
    }


