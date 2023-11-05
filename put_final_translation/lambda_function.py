import pymysql
import logging
import traceback
import os
import hashlib
import boto3
import json
# import pdb
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
            "headers": {
                    "Access-Control-Allow-Origin": "https://mtdock.com",
                    "Access-Control-Allow-Methods": "POST,OPTIONS",
            },
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
            "text": data.get("text"),
            "id": data.get("id"),
        }

        checksum = db.compute_checksum(translated_data)
        cnx = db.make_connection()
        cursor = cnx.cursor()

        if checksum.hex() != data.get("checksum"):
            return {
                "statusCode": 500,
                "body": "Data corruption",
                "headers": {
                    "Access-Control-Allow-Origin": "https://mtdock.com",
                    "Access-Control-Allow-Methods": "POST,OPTIONS",
                },
                "isBase64Encoded": "false",
            }

        try:
            # Check if the article already exists based on id and checksum
            select_statement = """
                SELECT COUNT(*) FROM HighTimes.edited_translations
                WHERE text_id = %s AND checksum = %s
            """
            cursor.execute(select_statement, (data.get("id"), checksum))
            result = cursor.fetchone()

            # If a row with the same id and checksum is found, it means the article already exists
            if result and result[0] > 0 and data.get("resubmit"):
                return {
                    "statusCode": 200,
                    "body": "Article already exists.",
                    "headers": {
                        "Access-Control-Allow-Origin": "https://mtdock.com",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                    "isBase64Encoded": "false",
                }

            insert_or_update_statement = """
            INSERT INTO edited_translations 
            (text_id, edited_content, checksum) 
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            text_id = VALUES(text_id),
            edited_content = VALUES(edited_content),
            checksum = VALUES(checksum);
            """

            try:
                if data.get("title"):
                    loaded = {"title": data.get("title"), "text": data.get("text")}
                else:
                    loaded = {"text": data.get("text")}

                json_data = json.dumps(loaded)
                
                try:
                    # Execute the INSERT statement with the data
                    cursor.execute(
                        insert_or_update_statement,
                        (
                            data.get("id"),
                            json_data,
                            checksum.hex(),
                        ),
                    )
                except Exception as e:
                    return db.log_err(
                        "ERROR: Cannot execute INSERT statement for edited_translations.\n{}".format(
                        traceback.format_exc()
                    )
                )
 

                # Update status in first_translation table after successful insert
                update_status_statement = """
                UPDATE HighTimes
                SET status = 'done'
                WHERE id = %s;
                """

                try:
                    cursor.execute(update_status_statement, (data.get("id"),))
                except Exception as e:
                    return db.log_err(
                        "ERROR: Cannot execute UPDATE on status.\n{}".format(
                        traceback.format_exc()
                    )
                )

            except Exception as e:
                return {
                    "statusCode": 500,
                    "body": "Element not passed in",
                    "headers": {
                        "Access-Control-Allow-Origin": "https://mtdock.com",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                    "isBase64Encoded": "false",
                }
            
            try:
                AWS_PROVIDERS_ID = 1
                GCP_PROVIDERS_ID = 2
                AZURE_PROVIDERS_ID = 3

                select_statement_id = """
                SELECT translation_id 
                FROM translations 
                WHERE text_id = %s AND providers_id IN (%s, %s, %s);
                """
                
                cursor.execute(select_statement_id, (data.get('id'), AWS_PROVIDERS_ID, AZURE_PROVIDERS_ID, GCP_PROVIDERS_ID))
                result = cursor.fetchall()

                aws_translation_id = result[0]
                gcp_translation_id = result[1]
                azure_translation_id = result[2]

                insert_ratings = """
                INSERT INTO ratings (translation_id, rating_value, providers_id)
                VALUES 
                    (%s, %s, %s),
                    (%s, %s, %s),
                    (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    rating_value = VALUES(rating_value),
                    providers_id = VALUES(providers_id);
                """

                # Prepare the parameters for the INSERT statement
                params = (
                    aws_translation_id, data.get("aws_rating"), AWS_PROVIDERS_ID,
                    gcp_translation_id, data.get("gcp_rating"), GCP_PROVIDERS_ID,
                    azure_translation_id, data.get("azure_rating"), AZURE_PROVIDERS_ID
                )

                # Execute the INSERT statement
                cursor.execute(insert_ratings, params)

            except Exception as e:
                return db.log_err(
                    "ERROR: Cannot execute INSERT statement for ratings.\n{}".format(
                        traceback.format_exc()
                    )
                )

            try:
                insert_comments = f"""
                INSERT INTO comments (text_id, comments)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE
                    text_id = VALUES(text_id);
                """
                cursor.execute(insert_comments, (data.get("id"), data.get("comments")))

            except Exception as e:
                return db.log_err(
                    "ERROR: Cannot execute INSERT statement for comments.\n{}".format(
                        traceback.format_exc()
                    )
                )

        except Exception as e:
            return db.log_err(
                "ERROR: Cannot execute INSERT statements.\n{}".format(
                    traceback.format_exc()
                )
            )

        return {
            "body": "Data inserted successfully",
            "headers": {
                "Access-Control-Allow-Origin": "https://mtdock.com",
                "Access-Control-Allow-Methods": "POST,OPTIONS",
            },
            "statusCode": 200,
            "isBase64Encoded": "false",
        }

    except Exception as e:
        return db.log_err(
            "ERROR: Cannot connect to the database from the handler.\n{}".format(
                traceback.format_exc()
            )
        )

    finally:
        try:
            cnx.close()
        except:
            pass

#
# if __name__ == "__main__":
#     data = {"text": "hello", "id": 5, "aws_rating": 2, "gcp_rating": 3, "azure_rating": 4, "comments": "", "checksum": "49ada0c9015d01690a9494975260fa2ceebc02f9c3ca23fc1baab9a52eb3b2d6"}
#id=1&from_lang='en'&to_lang='es'     load = json.dumps(data)
#     event = {
#       "resource": "/your/resource/path",
#       "path": "/your/resource/path",
#       "httpsMethod": "POST",
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
#         "httpsMethod": "POST",
#         "stage": "prod"
#       },
#       "body": load,
#       "isBase64Encoded": "false"
#     }
#
#     handler(event, None)
