import requests
import boto3
import json
import logging
import concurrent.futures
import pdb

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

    to_lang = queryStringParameters.get("to_lang")
    from_lang = queryStringParameters.get("from_lang")

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
    
    text = json.loads(text)
    text["to_lang"] = to_lang
    text["from_lang"] = from_lang

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
# if __name__ == "__main__":
#     event = {
#       "resource": "/your/resource/path",
#       "path": "/your/resource/path",
#       "httpMethod": "POST",
#       "headers": {
#         "Accept": "*/*",
#         "Content-Type": "application/json",
#         "Host": "your-api-id.execute-api.your-region.amazonaws.com",
#         "User-Agent": "curl/7.53.1"
#       },
#       "multiValueHeaders": {
#         "Accept": ["*/*"],
#         "Content-Type": ["application/json"]
#       },
#       "queryStringParameters": {
#         "id": 100,
#         "from_lang": "en",
#         "to_lang":"es"
#       },
#       "multiValueQueryStringParameters": {
#         "param1": ["value1"],
#         "param2": ["value2", "value2B"]
#       },
#       "pathParameters": {
#         "pathParam1": "value1"
#       },
#       "stageVariables": {
#         "stageVarName": "stageVarValue"
#       },
#       "requestContext": {
#         "requestId": "request-id",
#         "path": "/your/resource/path",
#         "httpMethod": "POST",
#         "stage": "prod"
#       },
#       "isBase64Encoded": "false"
#     }
#
#     lambda_handler(event, None) 
#
#      
#
#
#
#
#
