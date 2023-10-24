import requests
import uuid
import os
import boto3
from boto3 import ClientError
import hashlib
import logging

class AWSClient:
    def __init__(self):
        self.credentials = self.get_api_credentials(secret_name="HT_CREDS", keys=["SQS_ENDPOINT", "GET_API", 
                                                                                  "PUT_API", "BUCKET", "KEY_NAME", 
                                                                                  "LOCAL_PATH"])
        self.sqs = boto3.client('sqs', region_name='us-west-1')

    def get_api_credentials(self, secret_name, keys=[]):
        secret = self.get_secret(secret_name)
        secret_dict = json.loads(secret)
        return {key: secret_dict.get(key) for key in keys}

    def get_secret(self, secret_name,):
        secret_name = secret_name
        region_name = "us-west-1"
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager', region_name=region_name)
        try:
            get_secret_value_response = client.get_secret_value(SecretId=secret_name)
            return get_secret_value_response['SecretString']
        except ClientError as e:
            raise e

    def download_key_from_s3():
        s3 = boto3.client('s3')
        bucket_name = self.credentials["BUCKET"]
        key_name = self.credentials["KEY_NAME"]
        local_path = self.credentials["LOCAL_PATH"]

        s3.download_file(bucket_name, key_name, local_path)

    def get_article(self):
        try:
            response = requests.get(self.credentials["GET_API"])
            response.raise_for_status()
            response_data = json.loads(response.text)
            body_data = ast.literal_eval(response_data['body'])
            
            ID = body_data[0][0]
            title = body_data[0][1]
            text = body_data[0][2]

            return title, text, ID
        except requests.exceptions.RequestException as e:
            return {"Error" : f"Did not recieve articles {e}"}

    def send_to_rds(self, translation):
        try:
            requests.post(self.credentials["PUT_API"], json=translated_data, headers=headers)
            return {"status": "success", "message": "Data inserted successfully."}
        except Exception as e:
            return {"status": "failure", "message": str(e)}

    def send_to_sqs(self, translation):
        self.sqs.send_message(
            QueueUrl=self.credentials["SQS_ENDPOINT"],
            MessageBody=json.dumps(url_data),
            MessageGroupId='translation'
        )

class AWSTranslation:
    def __init__(self):
        self.translate_client = boto3.client('translate')
        self.MAX_BYTES = 10000

    def translation(self, to_lang, from_lang, text):
        try:
            translated_response = self.translate_client.translate_text(
                Text=text,
                SourceLanguageCode=from_lang,
                TargetLanguageCode=to_lang
            )
            return translated_response['TranslatedText']
        except Exception as e:
            logger.error("Error: status {e}")

        try:
            if len(text) > self.MAX_BYTES:
                parts = [text[i:i+self.MAX_BYTES] for i in range(0, len(text), self.MAX_BYTES)]
                translated_parts = [self.translation(part) for part in parts]
                return "".join(translated_parts)
        except Exception as e:
            return {"status": "failure", "message": str(e)}

class GCPTranslation:
    def __init__(self):
        self.project_id = self.AWSClient().get_api_credentials(secret_name="GCP_CREDS", keys=["PROJECT_ID"])

    def translate(text: str, from_language: str, to_language: str, project_id: str = proj_id) -> str:
        """Translating Text."""
        
        client = translate.TranslationServiceClient()

        location = "global"

        parent = f"projects/{project_id}/locations/{location}"

        # Translate text
        response = client.translate_text(
            request={
                "parent": parent,
                "contents": [text],
                "mime_type": "text/plain",
                "source_language_code": from_language,  # Set the source language
                "target_language_code": to_language,    # Set the target language
            }
        )

        # Extract and return the translated text
        return response.translations[0].translated_text
       
class AzureTranslate:
    def __init__(self):
        self.translate_endpoint, self.api_key = self.AWSClient().get_api_credentials(secret_name="AZURE_TRANSLATE", keys=["API_ENDPOINT", "API_KEY"])
        self.MAX_BYTES = 50000

    def translate(self, from_lang, to_lang, text):
        params = {
            'api-version': '3.0',
            'from': from_lang,
            'to': [to_lang]
        }

        headers = {
            'Ocp-Apim-Subscription-Key': self.credentials["API_KEY"],
            'Ocp-Apim-Subscription-Region': "West US",
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }

        body = [{'text': text}]

        try:
            request = requests.post(self.credentials["API_ENDPOINT"], params=params, headers=headers, json=body)
            response = request.json()

            translated_text = response[0]['translations'][0]['text']

            return translated_text
        except Exception as e:
            logger.error("Error: status {e}")
        
        try:
            if len(text) > self.MAX_BYTES:  # 5000 characters as the limit
                parts = [text[i:i+self.MAX_BYTES] for i in range(0, len(text), self.MAX_BYTES)]
                translated_parts = [self.translate(region, from_lang, to_lang, part) for part in parts]
                return "".join(translated_parts)
        except Exception as e:
            return {"status": "failure", "message": str(e)}

def lambda_handler(event, context):    
    aws = AWSClient()
    azure = AzureTranslate()
    awsTrans = AWSTranslation()

    aws.download_key_from_s3()

    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
    from google.cloud import translate
    gcp = GCPTranslation()

    from_lang = event["queryStringParameters"]["from_lang"]
    to_lang = event["queryStringParameters"]["to_lang"]

    title, text, ID = aws.get_article() 

    aws_text = awsTrans.translation(to_lang, from_lang, text)
    aws_title = awsTrans.translation(to_lang, from_lang, title)

    azure_text = azure.translate(from_lang, to_lang, text)
    azure_title = azure.translate(from_lang, to_lang, title)

    gcp_text = gcp.translate(text, from_language, to_language)
    gcp_title = gcp.translate(title, from_language, to_language)

    translated_text = {
            "aws_text" : aws_text,
            "aws_title" : aws_title,
            "azure_text" : azure_text,
            "azure_title" : azure_title,
            "gcp_text" : gcp_text,
            "gcp_title" : gcp_title,
            "id" : ID
            }

    aws.send_to_rds(translated_text)



    



