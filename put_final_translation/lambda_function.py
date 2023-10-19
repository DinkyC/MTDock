import pymysql
import logging
import traceback
import os
import hashlib
import boto3
import json
import pdb
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
            "title": data.get("title"),
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
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST,OPTIONS",
                },
                "isBase64Encoded": "false",
            }

        try:
            # Check if the article already exists based on id and checksum
            select_statement = """
                SELECT COUNT(*) FROM HighTimes.final_translation
                WHERE id = %s AND checksum = %s
            """
            cursor.execute(select_statement, (data.get("id"), checksum))
            result = cursor.fetchone()

            # If a row with the same id and checksum is found, it means the article already exists
            if result and result[0] > 0:
                return {
                    "statusCode": 200,
                    "body": "Article already exists.",
                    "headers": {
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                    "isBase64Encoded": "false",
                }

            insert_or_update_statement = """
            INSERT INTO final_translation 
            (id, title, BodyText, comments, aws_rating, gcp_rating, azure_rating, checksum) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            title = VALUES(title), 
            BodyText = VALUES(BodyText), 
            comments = VALUES(comments), 
            aws_rating = VALUES(aws_rating), 
            gcp_rating = VALUES(gcp_rating), 
            azure_rating = VALUES(azure_rating), 
            checksum = VALUES(checksum);
            """

            try:
                # Execute the INSERT statement with the data
                cursor.execute(
                    insert_statement,
                    (
                        data.get("id"),
                        data.get("title"),
                        data.get("text"),
                        data.get("comments", None),
                        data.get("aws_rating"),
                        data.get("gcp_rating"),
                        data.get("azure_rating"),
                        checksum,
                    ),
                )

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
                    "headers": {
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "POST,OPTIONS",
                    },
                    "isBase64Encoded": "false",
                }

        except Exception as e:
            return db.log_err(
                "ERROR: Cannot execute INSERT statement.\n{}".format(
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
            "ERROR: Cannot connect to the database from the handler.\n{}".format(
                traceback.format_exc()
            )
        )

    finally:
        try:
            cnx.close()
        except:
            pass


if __name__ == "__main__":
    data = {"id": 100, "title": "\u00daltima hora: los legisladores de California finalmente abordan la marihuana medicinal\r", "text": "\r\nSACRAMENTO, California (AP) \u2014 Los legisladores de California contaron una legislaci\u00f3n de gran alcance pero menos ambiciosa sobre el cambio clim\u00e1tico, una regulaci\u00f3n estatal de la marihuana medicinal y una medida profundamente emotiva para permitir la ayuda para morir entre los cientos de proyectos de ley que aprobaron antes de cerrar la sesi\u00f3n legislativa de 2015. temprano el s\u00e1bado. A principios de 20 a\u00f1os despu\u00e9s de que los votantes de California aprobaran el uso de marihuana con fines medicinales, los legisladores finalmente acordaron un paquete de proyectos de ley para crear las primeras reglas de operaci\u00f3n y licencias a nivel estatal para los productores de marihuana y los puntos de venta minorista de marihuana. Lo hicieron ante una probable iniciativa electoral del pr\u00f3ximo a\u00f1o para legalizar la marihuana recreativa. El marco busca gestionar la marihuana medicinal desde la semilla hasta el humo, exigiendo 17 categor\u00edas de licencia separadas, requisitos de etiquetado detallados y un sistema de seguimiento del producto completo con c\u00f3digos de barras y manifiestos de env\u00edo. \u201cCalifornia se ha quedado atr\u00e1s del resto de la naci\u00f3n y no logr\u00f3 garantizar una estructura regulatoria integral\u201d, dijo el asamble\u00edsta Reggie Jones-Sawyer, dem\u00f3crata por Los \u00c1ngeles. \"Esta industria es el salvaje oeste y debemos tomar medidas para abordarlo\". Si se promulga tal como est\u00e1 redactada, la legislaci\u00f3n impondr\u00eda controles estrictos a una industria que nunca ha tenido que cumplir con ninguno y proporcionar\u00eda un modelo de c\u00f3mo se podr\u00eda tratar la marihuana recreativa si se legaliza. La administraci\u00f3n Brown ayud\u00f3 a elaborar el paquete y se esperaba que \u00e9l lo firmara.", "comments": "12", "aws_rating": 4, "gcp_rating": 4, "azure_rating": 2, "checksum": "cb2baeee9bfbd4d19844efbeb484a443a908f3a987353de2f277aacdea77b43d"}
    loaded = json.dumps(data)
    event = {
      "resource": "/your/resource/path",
      "path": "/your/resource/path",
      "httpMethod": "POST",
      "headers": {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Host": "your-api-id.execute-api.your-region.amazonaws.com",
        "User-Agent": "curl/7.53.1"
      },
      "multiValueHeaders": {
        "Accept": ["*/*"],
        "Content-Type": ["application/json"]
      },
      "queryStringParameters": {
        "param1": "value1",
        "param2": "value2"
      },
      "multiValueQueryStringParameters": {
        "param1": ["value1"],
        "param2": ["value2", "value2B"]
      },
      "pathParameters": {
        "pathParam1": "value1"
      },
      "stageVariables": {
        "stageVarName": "stageVarValue"
      },
      "requestContext": {
        "requestId": "request-id",
        "path": "/your/resource/path",
        "httpMethod": "POST",
        "stage": "prod"
      },
      "body": loaded,
      "isBase64Encoded": "false"
    }

    handler(event, None)
