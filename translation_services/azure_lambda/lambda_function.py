import boto3
import os
import requests
import json
import logging
from botocore.exceptions import ClientError 
import hashlib
import concurrent.futures
import uuid
import pdb

class TranslationHander:
    def __init__(self):
        self.MAX_CHAR = 50_000

    def translate(self, endpoint, from_lang, to_lang, text, api_key):
        params = {
            'api-version': '3.0',
            'from': from_lang,
            'to': [to_lang]
        }

        headers = {
            'Ocp-Apim-Subscription-Key': api_key, 
            'Ocp-Apim-Subscription-Region': "westus",
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }

        body = [{'text': text}]
        
        endpoint = endpoint + '/translate'

        try:
            request = requests.post(endpoint, params=params, headers=headers, json=body)
            response = request.json()

            translated_text = response[0]['translations'][0]['text']

            return translated_text
        except Exception as e:
            if len(text) > self.MAX_CHAR:  # 5000 characters as the limit
                translated_text = self.handle_long_text_translation(endpoint, body, headers, params)

                return translated_text
            else:
                return {"status": "failure", "message": str(e)}

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
        self.params = {'checksum_column':'azure_checksum', 'title_column':'azure_title', 'text_column':'azure_text'}
        self.params_keys = ['put_first', 'azure_key', 'azure_endpoint']
        self.ssm = boto3.client('ssm')

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
                return response
        except Exception as e:
            return {"[ERROR]" : f"Error processing messages {e}"}

    def compute_checksum(self, data):
        return hashlib.sha256(str(data).encode('utf-8')).digest()

def lambda_handler(event, context):
    translator = TranslationHander()
    aws = AWSClient()
    params_dict = aws.get_parameters_from_store()

    for message in event.get('Records'):
        message_body = message.get('body')
        parsed_message = json.loads(message_body)

        from_lang = parsed_message.get('from_lang')
        to_lang = parsed_message.get('to_lang')

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_title = executor.submit(translator.translate, params_dict.get('azure_endpoint'), from_lang, to_lang, 
                                                                                    parsed_message.get('title'), params_dict.get('azure_key'))
            future_text = executor.submit(translator.translate, params_dict.get('azure_endpoint'), from_lang, to_lang, 
                                                                                    parsed_message.get('BodyText'), params_dict.get('azure_key'))

            # Capture translated results
            translated_title = future_title.result()
            translated_text = future_text.result()
        
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
            if send_to_rds_response.status_code != 200:
                raise e
        except Exception as e:
            return {"status": f"Failure {e}"}

    return {
        "status": "success",
        "message_count": len(event.get('Records'))
    }
# if __name__ == "__main__":
#     lambda_handler(None, None)

