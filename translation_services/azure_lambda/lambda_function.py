import boto3
import os
import requests
import json
import logging
from botocore.exceptions import ClientError
import hashlib
import concurrent.futures
import uuid

# import pdb


class TranslationHander:
    def __init__(self):
        self.MAX_CHAR = 50_000

    def translate(self, endpoint, from_lang, to_lang, text, api_key):
        params = {"api-version": "3.0", "from": from_lang, "to": [to_lang]}

        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Ocp-Apim-Subscription-Region": "westus",
            "Content-type": "application/json",
            "X-ClientTraceId": str(uuid.uuid4()),
        }

        body = [{"text": text}]

        endpoint = endpoint + "/translate"

        try:
            request = requests.post(endpoint, params=params, headers=headers, json=body)
            response = request.json()

            translated_text = response[0]["translations"][0]["text"]

            return translated_text
        except Exception as e:
            if len(text) > self.MAX_CHAR:  # 5000 characters as the limit
                translated_text = self.handle_long_text_translation(
                    endpoint, body, headers, params
                )

                return translated_text
            else:
                return {"status": "failure", "message": str(e)}

    def split_text_into_chunks(self, text, max_char):
        return [text[i : i + max_char] for i in range(0, len(text), max_char)]

    def handle_long_text_translation(self, endpoint, body, headers, params):
        # Split the text into chunks
        parts = self.split_text_into_chunks(text, self.MAX_CHAR - 500)

        # Translate each chunk
        translated_parts = []
        for part in parts:
            try:
                request = requests.post(
                    endpoint, params=params, headers=headers, json=body
                )
                response = request.json()

                translated_text = response[0]["translations"][0]["text"]

                translated_parts.append(translated_text)
            except Exception as e:
                return {"[ERROR]": f"Can't handle large text {e}"}

        # Join all the translated chunks together
        return "".join(map(str, translated_parts))


class AWSClient:
    def __init__(self):
        self.headers = {"Content-Type": "application/json"}
        self.params_keys = ["put_first", "azure_key", "azure_endpoint"]
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
                endpoint, json=translate_text, headers=self.headers 
            )
            if response.status_code == 200:
                return response.status_code
        except Exception as e:
            return {"[ERROR]": f"Error processing messages {e}"}

    def compute_checksum(self, data):
        return hashlib.sha256(str(data).encode("utf-8")).digest()


def lambda_handler(event, context):
    translator = TranslationHander()
    aws = AWSClient()
    params_dict = aws.get_parameters_from_store()

    PROVIDERS_ID = 3

    for message in event.get("Records"):
        message_body = message.get("body")
        parsed_message = json.loads(message_body)

        from_lang = parsed_message.get("from_lang")
        to_lang = parsed_message.get("to_lang")

        with concurrent.futures.ThreadPoolExecutor() as executor:

            has_title = "title" in parsed_message

            future_title = None
            if has_title:
                future_title = executor.submit(
                    translator.translate,
                    params_dict.get("azure_endpoint"),
                    from_lang,
                    to_lang,
                    parsed_message.get("title"),
                    params_dict.get("azure_key"),
                )

            future_text = executor.submit(
                translator.translate,
                params_dict.get("azure_endpoint"),
                from_lang,
                to_lang,
                parsed_message.get("text"),
                params_dict.get("azure_key"),
            )

            translated_title = None
            if has_title:
                try:
                    # Capture translated results
                    translated_title = future_title.result()
                except Exception as e:
                    return aws.log_err(
                        "[ERROR]: Cannot translate title data.\n{}".format(
                            traceback.format_exc()
                        )
                    )

            try:
                translated_text = future_text.result()
            except Exception as e:
                return aws.log_err(
                    "[ERROR]: Cannot translate text data.\n{}".format(
                        traceback.format_exc()
                    )
                )


        translated_data = {
            "text": translated_text,
            "id": parsed_message.get("id"),
            "lang_to": parsed_message.get("to_lang"),
            "lang_from": parsed_message.get("from_lang"),
            "providers_id": PROVIDERS_ID
        }

        if translated_title:
            translated_data["title"] = translated_title

        checksum = aws.compute_checksum({"text": translated_data["text"], "id": translated_data["id"]})
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


# if __name__ == "__main__":
#     event= {
#    "Records":[
#       {
#          "messageId":"19dd0b57-b21e-4ac1-bd88-01bbb068cb78",
#          "receiptHandle":"MessageReceiptHandle",
#          "body": "{\"id\": 300, \"title\": \"Report: California Should Keep Pot Taxes Low\", \"text\": \"SAN FRANCISCO (AP) \u2014 A blue-ribbon panel says curtailing the illegal marijuana market in California should be the primary goal of legalizing the drug\u2019s recreational use in the state, and not developing another tax source. ...\", \"to_lang\": \"es\", \"from_lang\": \"en\"}",
#          "attributes":{
#             "ApproximateReceiveCount":"1",
#             "SentTimestamp":"1545084659183",
#             "SenderId":"AIDAIENQZJOLO23YVJ4VO",
#             "ApproximateFirstReceiveTimestamp":"1545084659187"
#          },
#          "messageAttributes":{},
#          "md5OfBody":"[MD5 hash]",
#          "eventSource":"aws:sqs",
#          "eventSourceARN":"arn:aws:sqs:us-east-1:123456789012:MyQueue",
#          "awsRegion":"us-east-1"
#       }
#    ]
# }
#
#     lambda_handler(event, None)
