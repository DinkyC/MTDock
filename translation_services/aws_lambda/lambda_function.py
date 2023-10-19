# Redefining the structured classes and lambda handler
import boto3
import os
import requests
import json
import logging
from botocore.exceptions import ClientError
import hashlib
import concurrent.futures


class TranslationHandler:
    def __init__(self):
        self.translate_client = boto3.client("translate")
        self.MAX_BYTES = 10_000

    def translate(self, text, from_lang, to_lang):
        try:
            translated_response = self.translate_client.translate_text(
                Text=text, SourceLanguageCode=from_lang, TargetLanguageCode=to_lang
            )
            return translated_response["TranslatedText"]

        except Exception as e:
            if "TextSizeLimitExceededException" in str(e):
                translated_response = self.handle_long_text_translation(
                    text, from_lang, to_lang
                )
                return translated_response
            else:
                return {"Error": f"Error translating text {e}"}

    def split_text_into_chunks(self, text, max_bytes):
        # Convert the entire text to bytes
        text_bytes = text.encode("utf-8")

        # Split the text bytes into chunks
        chunks = []
        start_index = 0
        while start_index < len(text_bytes):
            end_index = start_index + max_bytes

            # Ensure we don't split in the middle of a multi-byte character
            while (
                end_index > start_index
                and text_bytes[end_index - 1 : end_index + 1].decode("utf-8", "ignore")
                == ""
            ):
                end_index -= 1

            chunk = text_bytes[start_index:end_index].decode("utf-8")
            chunks.append(chunk)

            start_index = end_index

        return chunks

    def handle_long_text_translation(self, text, from_lang, to_lang):
        # Split the text into chunks
        parts = self.split_text_into_chunks(text, self.MAX_BYTES - 500)

        # Translate each chunk
        translated_parts = []
        for part in parts:
            try:
                translated_response = self.translate_client.translate_text(
                    Text=part, SourceLanguageCode=from_lang, TargetLanguageCode=to_lang
                )
                translated_parts.append(translated_response["TranslatedText"])
            except Exception as e:
                return {"[ERROR]": f"Can't handle large text {e}"}

        # Join all the translated chunks together
        return "".join(map(str, translated_parts))


class AWSClient:
    def __init__(self):
        self.headers = {"Content-Type": "application/json"}
        self.params = {
            "checksum_column": "aws_checksum",
            "title_column": "aws_title",
            "text_column": "aws_text",
        }
        self.params_keys = ["put_first"]
        self.ssm = boto3.client("ssm")

    def get_parameters_from_store(self):
        response = self.ssm.get_parameters(Names=self.params_keys, WithDecryption=True)

        # Construct a dictionary to hold the parameter values
        params_dict = {}

        for param in response["Parameters"]:
            params_dict[param["Name"]] = param["Value"]

        return params_dict

    def insert_translation(self, endpoint, translate_text):
        try:
            response = requests.post(
                endpoint, json=translate_text, headers=self.headers, params=self.params
            )
            if response.status_code == 200:
                return response.status_code
        except Exception as e:
            return {"[ERROR]": f"Error processing messages {e}"}

    def compute_checksum(self, data):
        return hashlib.sha256(str(data).encode("utf-8")).digest()


# Main Lambda Handler
def lambda_handler(event, context):
    translator = TranslationHandler()
    aws = AWSClient()

    params_dict = aws.get_parameters_from_store()

    for message in event.get("Records"):
        message_body = message.get("body")
        parsed_message = json.loads(message_body)

        to_lang = parsed_message.get("to_lang")
        from_lang = parsed_message.get("from_lang")

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_title = executor.submit(
                translator.translate, parsed_message.get("title"), from_lang, to_lang
            )
            future_text = executor.submit(
                translator.translate, parsed_message.get("text"), from_lang, to_lang
            )

            # Capture translated results
            translated_title = future_title.result()
            translated_text = future_text.result()

        translated_data = {
            "title": translated_title,
            "text": translated_text,
            "id": parsed_message.get("id"),
        }

        checksum = aws.compute_checksum(translated_data)
        translated_data["checksum"] = checksum.hex()
        # Sending translated data to RDS
        try:
            send_to_rds_response = aws.insert_translation(
                params_dict["put_first"], translated_data
            )
            if send_to_rds_response != 200:
                raise e
        except Exception as e:
            return {"status": f"Failure {e}"}

    return {"status": "success", "message_count": len(event.get("Records"))}


#
# if __name__ == "__main__":
#     lambda_handler(None, None)
