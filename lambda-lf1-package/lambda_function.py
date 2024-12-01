import boto3
import json
from datetime import datetime
from elasticsearch import Elasticsearch
from requests_aws4auth import AWS4Auth

region = 'us-east-1'
rekognition = boto3.client('rekognition', region_name=region)
s3 = boto3.client('s3')

credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, 'es')

es = Elasticsearch(
    ['https://search-photos-3jses4pfal2jcxmzrskhhsr6pa.aos.us-east-1.on.aws'],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True
)

def lambda_handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        print(f"Processing file {key} from bucket {bucket}")

        try:
            response = rekognition.detect_labels(
                Image={'S3Object': {'Bucket': bucket, 'Name': key}},
                MaxLabels=10,
                MinConfidence=75
            )
            
            labels = [label['Name'] for label in response['Labels']]
            print(f"Detected labels: {labels}")

            metadata = s3.head_object(Bucket=bucket, Key=key)['Metadata']
            custom_labels = metadata.get('x-amz-meta-customlabels', '')
            custom_labels = custom_labels.split(',') if custom_labels else []

            all_labels = labels + custom_labels

            doc = {
                'objectKey': key,
                'bucket': bucket,
                'createdTimestamp': datetime.now().isoformat(),
                'labels': all_labels
            }
            print(f"Document to index: {json.dumps(doc)}")

            es.index(index='photos', body=doc)
            print("Document indexed successfully.")

        except Exception as e:
            print(f"Error processing file {key}: {str(e)}")
            raise e

    return {
        'statusCode': 200,
        'body': json.dumps('Photo indexed successfully')
    }




