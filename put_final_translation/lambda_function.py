import pymysql
import logging
import traceback
from os import environ
import hashlib
import boto3
import json

port = environ.get('PORT')
database = environ.get('DATABASE')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_database_credentials():
    secret = get_secret()
    secret_dict = json.loads(secret)
    return secret_dict.get('username'), secret_dict.get('password'), secret_dict.get('host')


def get_secret():
    secret_name = "HighTimesDB"
    region_name = "us-west-1"
    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        return get_secret_value_response['SecretString']
    except Exception as e:
        raise e

def make_connection():
    dbuser, password, endpoint = get_database_credentials()
    return pymysql.connect(
        host=endpoint,
        user=dbuser,
        passwd=password,
        port=int(port),
        db=database,  
        autocommit=True
    )


def log_err(errmsg):
    logger.error(errmsg)
    return {"body": errmsg, "headers": {}, "statusCode": 400, "isBase64Encoded": "false"}

def compute_checksum(data):
    return hashlib.sha256(str(data).encode('utf-8')).digest()

def handler(event, context):
    try:
        # Extract the data you want to insert from the event or any other source
        translated_data = {"title": event.get("title"), "text": event.get("text"), "id": event.get("id"), "comments": event.get("comments", None)}
        checksum = compute_checksum(translated_data)
        cnx = make_connection()
        cursor = cnx.cursor()

        try:
            # Check if the article already exists based on id and checksum
            select_statement = """
                SELECT COUNT(*) FROM HighTimes.final_translation
                WHERE id = %s AND checksum = %s
            """
            cursor.execute(select_statement, (translated_data["id"], checksum))
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
            INSERT INTO final_translation (id, title, BodyText, comments, checksum) 
            VALUES (%s, %s, %s, %s, %s)
            """
            
            # Execute the INSERT statement with the data
            cursor.execute(insert_statement, (event.get("id"), event.get("title"), event.get("text"), event.get("comments", None), checksum))

        except Exception as e:
            return log_err("ERROR: Cannot execute INSERT statement.\n{}".format(traceback.format_exc()))

        return {"body": "Data inserted successfully", "headers": {}, "statusCode": 200, "isBase64Encoded": "false"}

    except Exception as e:
        return log_err("ERROR: Cannot connect to the database from the handler.\n{}".format(traceback.format_exc()))

    finally:
        try:
            cnx.close()
        except:
            pass

if __name__ == "__main__":
    handler(None, None)

