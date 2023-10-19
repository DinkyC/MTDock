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
        return (
            secret_dict.get("username"),
            secret_dict.get("port"),
            secret_dict.get("database"),
            secret_dict.get("host"),
        )

    def get_secret(self):
        secret_name = "HighTimesDB"
        region_name = os.environ["AWS_REGION"]
        session = boto3.session.Session()
        client = session.client(service_name="secretsmanager", region_name=region_name)
        try:
            get_secret_value_response = client.get_secret_value(SecretId=secret_name)
            return get_secret_value_response["SecretString"]
        except Exception as e:
            raise e

    def make_connection(self):
        rds_client = boto3.client("rds")

        username, port, database, endpoint = self.get_database_credentials()

        database_token = rds_client.generate_db_auth_token(
            DBHostname=endpoint,
            Port=port,
            DBUsername=username,
            Region=os.environ["AWS_REGION"],
        )

        return pymysql.connect(
            host=endpoint,
            user=username,
            passwd=database_token,
            port=int(port),
            db=database,
            autocommit=True,
            ssl={"ssl": True},
        )

    def log_err(self, errmsg):
        logger.error(errmsg)
        return {
            "body": errmsg,
            "headers": {},
            "statusCode": 400,
            "isBase64Encoded": "false",
        }

    def compute_checksum(self, data):
        return hashlib.sha256(str(data).encode("utf-8")).digest()


def handler(event, context):
    body = event.get("body", "{}")
    data = json.loads(body)

    db = HTDatabase()
    try:
        # Extract the data you want to insert from the event or any other source
        translated_data = {
            "title": data.get("title"),
            "text": data.get("text"),
            "id": data.get("id"),
        }
        checksum = db.compute_checksum(translated_data)
        if data.get("checksum") != checksum.hex():
            return {
                "statusCode": 500,
                "body": "Data corruption. Checksums are not the same.",
            }

        cnx = db.make_connection()
        cursor = cnx.cursor()

        queryStringParameters = event.get("queryStringParameters")
        if not queryStringParameters:
            return {
                "statusCode": 400,
                "body": "queryStringParameters not provided in the event.",
            }

        text_column = queryStringParameters.get("text_column")
        if not text_column:
            return {
                "statusCode": 400,
                "body": "text_column not provided in queryStringParameters.",
            }

        title_column = queryStringParameters.get("title_column")
        if not title_column:
            return {
                "statusCode": 400,
                "body": "title_column not provided in queryStringParameters.",
            }

        checksum_column = queryStringParameters.get("checksum_column")
        if not title_column:
            return {
                "statusCode": 400,
                "body": "checksum_column not provided in queryStringParameters.",
            }

        try:
            # Check if the article already exists based on id and checksum
            select_statement = f"""
                SELECT COUNT(*) FROM HighTimes.first_translation
                WHERE id = %s AND {checksum_column} = %s
            """
            cursor.execute(select_statement, (translated_data["id"], checksum))
            result = cursor.fetchone()

            # If a row with the same id and checksum is found, it means the article already exists
            if result and result[0] > 0:
                return {
                    "statusCode": 200,
                    "body": "Article translation already exists.",
                    "isBase64Encoded": "false",
                }

            # Create an INSERT statement
            insert_statement = f"""
                INSERT INTO first_translation (id, {title_column}, {text_column}, {checksum_column}, status)
                VALUES (%s, %s, %s, %s, 'pending')
                ON DUPLICATE KEY UPDATE
                {title_column} = VALUES({title_column}),
                {text_column} = VALUES({text_column}),
                {checksum_column} = VALUES({checksum_column}),
                status = 'pending';
            """

            try:
                # Execute the INSERT statement with the data
                cursor.execute(
                    insert_statement,
                    (data.get("id"), data.get("title"), data.get("text"), checksum),
                )
            except Exception as e:
                return {
                    "[ERROR]": f"{e} : {event.get('id')} : {translated_data.get('id')}"
                }

        except Exception as e:
            return db.log_err(
                "[ERROR]: Cannot execute INSERT statement.\n{}".format(
                    traceback.format_exc()
                )
            )

        return {
            "body": "Data inserted successfully",
            "headers": {},
            "statusCode": 200,
            "isBase64Encoded": "false",
        }

    except Exception as e:
        return db.log_err(
            "[ERROR]: Cannot connect to the database from the handler.\n{}".format(
                traceback.format_exc()
            )
        )

    finally:
        try:
            cnx.close()
        except:
            pass
