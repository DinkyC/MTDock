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
            "headers": {
                "Access-Control-Allow-Origin": "*",
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
        if data.get("checksum") != checksum.hex():
            return {
                "statusCode": 500,
                "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST,OPTIONS",
                },
                "body": "Data corruption. Checksums are not the same.",
            }

        cnx = db.make_connection()
        cursor = cnx.cursor()

        try:
            # Check if the article already exists based on id and checksum
            select_statement = f"""
                SELECT COUNT(*) FROM HighTimes.translations
                WHERE text_id = %s AND checksum = %s
            """
            cursor.execute(select_statement, (translated_data["id"], checksum))
            result = cursor.fetchone()

            # If a row with the same id and checksum is found, it means the article already exists
            if result and result[0] > 0:
                return {
                    "statusCode": 200,
                    "headers": {
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                    "body": "Article translation already exists.",
                    "isBase64Encoded": "false",
                }

            # Create an INSERT statement
            insert_statement = f"""
            INSERT INTO translations (text_id, content, providers_id, lang_to, lang_from, checksum)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                content = VALUES(content),
                checksum = VALUES(checksum);
            """
            
            if data.get("title"):
                loaded = {"title": data.get("title"), "text": data.get("text")}
            else:
                loaded = {"text": data.get("text")}

            json_data = json.dumps(loaded)

            try:
                # Execute the INSERT statement with the data
                cursor.execute(
                    insert_statement,
                    (data.get("id"), json_data, data.get("providers_id"), data.get("lang_to"), data.get("lang_from"), checksum),
                )
            except Exception as e:
                return {
                    "[ERROR]": f"{e} : {event.get('id')} : {translated_data.get('id')}"
                }

            insert_update_statement = f"""
                UPDATE HighTimes
                SET status = 'pending'
                WHERE id = %s;
            """
            try:
                cursor.execute(
                        insert_update_statement, 
                        (data.get("id"))
                               )
            except Exception as e:
                return db.log_err(
                    "[ERROR]: Cannot execute update statement.\n{}".format(
                        traceback.format_exc()
                    )
                )

        except Exception as e:
            return db.log_err(
                "[ERROR]: Cannot execute INSERT statement.\n{}".format(
                    traceback.format_exc()
                )
            )

        return {
            "body": "Data inserted successfully",
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST,OPTIONS",
            },
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


