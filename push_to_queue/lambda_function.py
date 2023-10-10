import boto3

class AWSClient:
    def __init__(self):
        self.params_keys = ['sqs_endpoint_ht_fifo', 'sqs_endpoint_ht']
        self.sqs = boto3.client('sqs', region_name='us-west-1')
        self.ssm = boto3.client('ssm') 

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

    def push_to_sqs(self, fifo_queue_url, queue_url, messages):
        for message in messages:
            try:
                # Send message to a standard queue
                response = self.sqs.send_message(
                    QueueUrl=queue_url,
                    MessageBody=message['Body']
                )
                receipt_handle = message['ReceiptHandle']
                self.sqs.delete_message(QueueUrl=fifo_queue_url, ReceiptHandle=receipt_handle)
            except Exception as e:
                return {"[ERROR]" : f"Error processing messages {e}"}

def lambda_handler(event, context):
    aws = AWSClient()

    endpoint = aws.get_parameters_from_store()
    fifo_endpoint = endpoint.get("sqs_endpoint_ht_fifo")
    sqs_endpoint = endpoint.get("sqs_endpoint_ht")

    try:
        messages = aws.get_fifo_sqs(fifo_endpoint)
    except Exception as e:
        return {"[ERROR]" : f"error getting messages from fifo {e}: {fifo_endpoint}"}
    try:
        aws.push_to_sqs(fifo_endpoint, sqs_endpoint, messages)
        return {
            "statusCode": 200,
            "body": "Successfully sent to SQS."
        }
    except Exception as e:
        return {"[ERROR]" : f"error pushing to sqs {e}"}
