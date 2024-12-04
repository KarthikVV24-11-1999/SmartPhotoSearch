import boto3
import json
import os
from datetime import datetime
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Define OpenSearch FGAC credentials and endpoint
OPENSEARCH_ENDPOINT = os.environ['OPENSEARCH_ENDPOINT']
AWS_REGION = os.environ['REGION']
MASTER_USER = os.environ['MASTER_USERNAME']
MASTER_PASSWORD = os.environ['MASTER_PASSWORD']

# Initialize Rekognition and S3 clients
rekognition = boto3.client('rekognition', region_name=AWS_REGION)
s3 = boto3.client('s3')

# Get AWS credentials from environment variables or IAM role
aws_credentials = boto3.Session().get_credentials()
auth = AWS4Auth(aws_credentials.access_key, aws_credentials.secret_key, AWS_REGION, 'es', session_token=aws_credentials.token)

# Initialize OpenSearch client with AWS authentication
es = OpenSearch(
    hosts=[OPENSEARCH_ENDPOINT],
    http_auth=(MASTER_USER, MASTER_PASSWORD),  # Using Basic Authentication (if needed)
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    aws_auth=auth
)

def lambda_handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        print(f"Processing file {key} from bucket {bucket}")

        try:
            # Detect labels using Rekognition
            response = rekognition.detect_labels(
                Image={'S3Object': {'Bucket': bucket, 'Name': key}},
                MaxLabels=10,
                MinConfidence=75
            )
            labels = [label['Name'] for label in response['Labels']]
            print(f"Detected labels: {labels}")

            # Extract custom labels from S3 object metadata
            metadata = s3.head_object(Bucket=bucket, Key=key)['Metadata']
            custom_labels = metadata.get('x-amz-meta-customlabels', '')
            custom_labels = custom_labels.split(',') if custom_labels else []
            all_labels = labels + custom_labels

            # Prepare document to index
            doc = {
                'objectKey': key,
                'bucket': bucket,
                'createdTimestamp': datetime.now().isoformat(),
                'labels': all_labels
            }
            print(f"Document to index: {json.dumps(doc)}")

            # Index document into OpenSearch
            es.index(index='photos', body=doc)
            print("Document indexed successfully.")

        except Exception as e:
            print(f"Error processing file {key}: {str(e)}")
            raise e

    return {
        'statusCode': 200,
        'body': json.dumps('Photo indexed successfully')
    }
