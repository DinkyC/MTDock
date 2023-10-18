import pymysql
import logging
import traceback
import os
import hashlib
import boto3
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)
class HTDatabase:
    def get_database_credentials(self):
        secret = self.get_secret()
        secret_dict = json.loads(secret)
        return secret_dict.get('username'), secret_dict.get('port'), secret_dict.get('database'), secret_dict.get('host')


    def get_secret(self):
        secret_name = "HighTimesDB"
        region_name = os.environ['AWS_REGION'] 
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager', region_name=region_name)
        try:
            get_secret_value_response = client.get_secret_value(SecretId=secret_name)
            return get_secret_value_response['SecretString']
        except Exception as e:
            raise e

    def make_connection(self):
        rds_client = boto3.client('rds')

        username, port, database, endpoint = self.get_database_credentials()

        database_token = rds_client.generate_db_auth_token(
            DBHostname=endpoint,
            Port=port,
            DBUsername=username,
            Region=os.environ['AWS_REGION']
            )

        return pymysql.connect(
            host=endpoint,
            user=username,
            passwd=database_token,
            port=int(port),
            db=database,  
            autocommit=True,
            ssl={'ssl': True}
        )


    def log_err(self, errmsg):
        logger.error(errmsg)
        return {"body": errmsg, "headers": {}, "statusCode": 400, "isBase64Encoded": "false"}

    def compute_checksum(self, data):
        return hashlib.sha256(str(data).encode('utf-8')).digest()

def handler(event, context):
    body = event.get('body', '{}')
    data = json.loads(body)
    db = HTDatabase()

    try:
        # Extract the data you want to insert from the event or any other source
        translated_data = {"title": data.get("title"), "text": data.get("text"), "id": data.get("id")}
        
        checksum = db.compute_checksum(translated_data)
        cnx = db.make_connection()
        cursor = cnx.cursor()
        
        if checksum.hex() != data.get('checksum'):
            return {
                    "statusCode": 500,
                    "body": "Data corruption",
                    "isBase64Encoded": "false"

                    } 

        try:
            # Check if the article already exists based on id and checksum
            select_statement = """
                SELECT COUNT(*) FROM HighTimes.final_translation
                WHERE id = %s AND checksum = %s
            """
            cursor.execute(select_statement, (data.get('id'), checksum))
            result = cursor.fetchone()

            # If a row with the same id and checksum is found, it means the article already exists
            if result and result[0] > 0:
                return {
                    "statusCode": 200,
                    "body": "Article already exists.",
                    "isBase64Encoded": "false"
                }


            # Create an INSERT statement
            insert_statement = """
            INSERT INTO final_translation (id, title, BodyText, comments, rating, checksum) 
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            try:
                # Execute the INSERT statement with the data
                cursor.execute(insert_statement, (data.get("id"), data.get("title"), data.get("text"), data.get("comments", None), data.get('rating'), checksum))

                # Update status in first_translation table after successful insert
                update_status_statement = """
                UPDATE first_translation
                SET status = 'done'
                WHERE id = %s;
                """
                cursor.execute(update_status_statement, (data.get("id"),))
            except Exception as e:
                return {
                    "statusCode": 500,
                    "body": "Element not passed in",
                    "isBase64Encoded": "false"
                }

        except Exception as e:
            return db.log_err("ERROR: Cannot execute INSERT statement.\n{}".format(traceback.format_exc()))

        return {"body": "Data inserted successfully", "headers": {}, "statusCode": 200, "isBase64Encoded": "false"}

    except Exception as e:
        return db.log_err("ERROR: Cannot connect to the database from the handler.\n{}".format(traceback.format_exc()))

    finally:
        try:
            cnx.close()
        except:
            pass
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
#         "param1": "value1",
#         "param2": "value2"
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
#       "body": "{\"title\": \"value1\", \"text\": \"value2\", \"id\": 57, \"checksum\": \"c0c4208611a66297644373675e64c20e81d43b1760ab40a42605b6bd7908912c\", \"rating\": 4}",
#       "isBase64Encoded": "false"
#     }
#
#     handler(event, None) 
