import boto3
import requests
import hashlib
import os
import json
import concurrent.futures
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class GCPTranslation:
    def __init__(self):
        self.MAX_CHAR = 5_000

    def translate(self, text: str, from_language: str, to_language: str, project_id: str) -> str:
        """Translating Text."""
        from google.cloud import translate
        client = translate.TranslationServiceClient()

        location = "global"

        parent = f"projects/{project_id}/locations/{location}"
        
        try:
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
        except Exception as e:
            if len(text) > self.MAX_CHAR:
                translated_text = self.handle_long_text_translation(text, parent, from_language, to_language)
                return translated_text
            else:
                return{"status": "[ERROR]", "message": str(e)}
            

    def split_text_into_chunks(self, text, max_char):
        return [text[i:i+max_char] for i in range(0, len(text), max_char)]

    def handle_long_text_translation(self, text, parent, from_language, to_language):
        # Split the text into chunks
        parts = self.split_text_into_chunks(text, self.MAX_CHAR - 500) 
        
        # Translate each chunk
        translated_parts = []
        for part in parts:
            try:
                response = client.translate_text(
                    request={
                        "parent": parent,
                        "contents": [part],
                        "mime_type": "text/plain",
                        "source_language_code": from_language,  # Set the source language
                        "target_language_code": to_language,    # Set the target language
                    }
                )

                # Extract and return the translated text
                translated_text = response.translations[0].translated_text

                translated_parts.append(translated_text)
            except Exception as e:
                return {"[ERROR]": f"Can't handle large text {e}"}

        # Join all the translated chunks together
        return "".join(map(str, translated_parts))

class AWSClient:
    def __init__(self):
        self.headers = {'Content-Type': 'application/json'}
        self.params = {'checksum_column':'gcp_checksum', 'title_column':'gcp_title', 'text_column':'gcp_text'}
        self.params_keys = ['put_first', 'project_id', 'bucket_name']
        self.ssm = boto3.client('ssm')
        self.s3 = boto3.client('s3')

    def download_creds_from_s3(self, bucket_name):
        self.s3.download_file(bucket_name, 'vigilant-router-393521-a6988b1023c5.json', '/tmp/gcp_creds.json')

    def get_parameters_from_store(self):
        response = self.ssm.get_parameters(Names=self.params_keys, WithDecryption=True)

        # Construct a dictionary to hold the parameter values
        params_dict = {}

        for param in response['Parameters']:
            params_dict[param['Name']] = param['Value']

        return params_dict

    def insert_translation(self, endpoint, translate_text):
        try:
            response = requests.post(endpoint, json=translate_text, headers=self.headers, params=self.params)
            if response.status_code == 200:
                return response.status_code
        except Exception as e:
            return {"[ERROR]" : f"Error processing messages {e}"}

    def compute_checksum(self, data):
        return hashlib.sha256(str(data).encode('utf-8')).digest()

def lambda_handler(event, context):
    aws = AWSClient()

    params_dict = aws.get_parameters_from_store()

    aws.download_creds_from_s3(params_dict.get('bucket_name'))

    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/tmp/gcp_creds.json'

    # from google.cloud import translate
    translator = GCPTranslation()
    
    for message in event.get('Records'):
        message_body = message.get('body')
        parsed_message = json.loads(message_body)
        
        from_lang = parsed_message.get('from_lang')
        to_lang = parsed_message.get('to_lang')

        translated_title = translator.translate(parsed_message.get('title'), from_lang, to_lang, params_dict.get('project_id'))
        translated_text = translator.translate(parsed_message.get('BodyText'), from_lang, to_lang, params_dict.get('project_id'))

        translated_data = {
            "title": translated_title,
            "text": translated_text,
            "id": parsed_message.get('id'),
        }

        checksum = aws.compute_checksum(translated_data)
        translated_data['checksum'] = checksum.hex() 
        # Sending translated data to RDS
        try:
            send_to_rds_response = aws.insert_translation(params_dict["put_first"], translated_data)
            if send_to_rds_response != 200:
                raise e
        except Exception as e:
            return {"status": f"Failure {e}"}

    return {
        "status": "success",
        "message_count": len(event.get('Records'))
    }
# if __name__ == "__main__":
#     event={"from_lang": "en", "to_lang": "es"}
#     lambda_handler(event, None)
