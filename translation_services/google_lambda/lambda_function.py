import boto3
import requests
import hashlib
import os


class GCPTranslation:
    def __init__(self):
        self.MAX_CHAR = 5_000
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

    def split_text_into_chunks(self, text, max_char):
        return [text[i:i+max_char] for i in range(0, len(text), max_char)]

    def handle_long_text_translation(self, endpoint, body, headers, params):
        # Split the text into chunks
        parts = self.split_text_into_chunks(text, self.MAX_CHAR - 500) 
        
        # Translate each chunk
        translated_parts = []
        for part in parts:
            try:
                request = requests.post(endpoint, params=params, headers=headers, json=body)
                response = request.json()

                translated_text = response[0]['translations'][0]['text']

                translated_parts.append(translated_text)
            except Exception as e:
                return {"[ERROR]": f"Can't handle large text {e}"}

        # Join all the translated chunks together
        return "".join(map(str, translated_parts))

class AWSClient:
    def __init__(self):
        self.headers = {'Content-Type': 'application/json'}
        self.params = {'checksum_column':'gcp_checksum', 'title_column':'gcp_title', 'text_column':'gcp_text'}
        self.params_keys = ['sqs_gcp', 'put_first', 'gcp_creds_s3', 'gcp_creds_local']
        self.sqs = boto3.client('sqs', region_name='us-west-1')
        self.ssm = boto3.client('ssm')

    def download_creds_from_s3(self):
        pass

    def move_creds_to_tmp(self):
        pass

    def get_parameters_from_store(self):
        response = self.ssm.get_parameters(Names=self.params_keys, WithDecryption=True)

        # Construct a dictionary to hold the parameter values
        params_dict = {}

        for param in response['Parameters']:
            params_dict[param['Name']] = param['Value']

        return params_dict

    def get_fifo_sqs(self, queue_url):
        # Retrieve all messages from the queue
        messages = []
        while True:
            response = self.sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)
            if 'Messages' not in response:
                break
            messages += response['Messages']

        return messages

    def insert_translation(self, endpoint, fifo_endpoint, translate_text, message_receipt):
        try:
            response = requests.post(endpoint, json=translate_text, headers=self.headers, params=self.params)
            if response.status_code == 200:
                self.sqs.delete_message(QueueUrl=fifo_endpoint, ReceiptHandle=message_receipt)
                return response
        except Exception as e:
            return {"[ERROR]" : f"Error processing messages {e}"}

    def compute_checksum(self, data):
        return hashlib.sha256(str(data).encode('utf-8')).digest()

def lambda_handler(event, context):
    pass
