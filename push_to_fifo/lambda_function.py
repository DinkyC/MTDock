import requests
import boto3
import json
import logging
import concurrent.futures

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class AWSClient:
    def __init__(self):
        self.headers = {'Content-Type': 'application/json'}
        self.params_keys = ['sqs_aws', 'sqs_azure', 'sqs_gcp', 'get_article']
        self.ssm = boto3.client('ssm')  # Initialize this first
        self.parameter_dict = self.get_parameters_from_store()  # Now you can call this
        self.sqs = boto3.client('sqs', region_name='us-west-1')
        
    def get_parameters_from_store(self):
        response = self.ssm.get_parameters(Names=self.params_keys, WithDecryption=True)

        # Construct a dictionary to hold the parameter values
        params_dict = {}

        for param in response['Parameters']:
            params_dict[param['Name']] = param['Value']

        return params_dict
 
    def send_to_sqs(self, text, sqs_endpoint):
        self.sqs.send_message(
            QueueUrl=sqs_endpoint,
            MessageBody=json.dumps(text),
            MessageGroupId='translation'
        )

    def call_api(self, id=None, title=None):
        params = {'id': id, 'title': title}
        response = requests.get(self.parameter_dict['get_article'], params=params)
        # Check if the request was successful
        response.raise_for_status()
        return response.text

def lambda_handler(event, context):
    aws = AWSClient()
    queryStringParameters = event.get("queryStringParameters", {})
    
    # Extract values or set to None if not provided
    id = queryStringParameters.get("id")
    title = queryStringParameters.get("title")

    parameter_dict = aws.get_parameters_from_store()

    aws_sqs = parameter_dict.get("sqs_aws")
    azure_sqs = parameter_dict.get("sqs_azure")
    gcp_sqs = parameter_dict.get("sqs_gcp")

    if not id:
        logger.info("No id provided.")

    if not title:
        logger.info("No title provided.")
    try:
        text = aws.call_api(id=id, title=title)
    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"ERROR: Cannot call api.\n{str(e)}"
        }
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Submit tasks using lambda functions
            executor.submit(lambda: aws.send_to_sqs(text, aws_sqs))
            executor.submit(lambda: aws.send_to_sqs(text, azure_sqs))
            executor.submit(lambda: aws.send_to_sqs(text, gcp_sqs))
        return {
            "statusCode": 200,
            "body": "Successfully sent to SQS."
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"ERROR: Cannot call api.\n{str(e)}"
        }


     





