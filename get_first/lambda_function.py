import pymysql
import logging
import traceback
import os
import json
# import pdb
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class HTDatabase:
    def construct_query(self, **kwargs):
        base_query = """
        SELECT status, translations.content, lang_to, lang_from, providers_id, text_id
        FROM translations
        INNER JOIN HighTimes ON translations.text_id = HighTimes.id
        """
        conditions = []
        params = []

        if kwargs.get("title"):
            conditions.append("JSON_EXTRACT(translations.content, '$.title') = %s")
            params.append(kwargs["title"])

        # Adjust the id condition based on direction
        if kwargs.get("id"):
            if kwargs.get("direction") == "next":
                conditions.append("translations.text_id > %s")
            elif kwargs.get("direction") == "prev":
                conditions.append("translations.text_id < %s")
            else:
                conditions.append("translations.text_id = %s")
            params.append(kwargs["id"])

        if kwargs.get("providers_id"):
            conditions.append("translations.providers_id = %s")
            params.append(kwargs["providers_id"])

        # Add a condition for lang_to, if specified
        if kwargs.get("lang_to"):
            conditions.append("translations.lang_to = %s")
            params.append(kwargs["lang_to"])

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        base_query += " LIMIT 1"

        return base_query, params

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
                "Access-Control-Allow-Methods": "GET,OPTIONS",
            },
            "statusCode": 400,
            "isBase64Encoded": "false",
        }


logger.info("Cold start complete.")

def lambda_handler(event, context):
    db = HTDatabase()
    queryStringParameters = event.get("queryStringParameters", {})

    # Extract values or set to None if not provided
    id = queryStringParameters.get("id")
    title = queryStringParameters.get("title")
    providers_id = queryStringParameters.get("providers_id")

    direction = queryStringParameters.get("direction")
    lang_to = queryStringParameters.get("to_lang")

    if not id:
        logger.info("No id provided.")
    if not title:
        logger.info("No title provided.")

    try:
        query, params = db.construct_query(title=title, id=id, direction=direction, providers_id=providers_id, lang_to=lang_to)
    except Exception as e:
        logger.error(f"[ERROR]: Cannot construct query. {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "https://mtdock.com",
                "Access-Control-Allow-Methods": "GET,OPTIONS",
            },
            "body": f"[ERROR]: Cannot construct query.\n{str(e)}",
        }

    try:
        cnx = db.make_connection()
        cursor = cnx.cursor()

        try:
            cursor.execute(query, params)
        except:
            return db.log_err(
                "[ERROR]: Cannot execute cursor.\n{}".format(traceback.format_exc())
            )

        try:
            result = cursor.fetchall()
            cursor.close()
        except:
            return db.log_err(
                "[ERROR]: Cannot retrieve query data.\n{}".format(
                    traceback.format_exc()
                )
            )
       
        if cursor.rowcount == 0:
            return db.log_err("[ERROR] no result for given id or title")

        loaded = json.loads(result[0][1])
        
        provider = None

        match result[0][4]:
            case 1:
                provider = "AWS"
            case 2:
                provider = "GCP"
            case 3:
                provider = "AZURE"
            case _:
                return db.log_err(
                "[ERROR]: Cannot retrieve provider.\n{}".format(
                    traceback.format_exc()
                )
            )

        # If there's a result, process it
        if result:
            # Convert the tuple to a dictionary
            entry = {"id": result[0][5], "status": result[0][0], "text": loaded, "lang_to": result[0][2], "lang_from": result[0][3], "providers_id": provider}
        else:
            entry = {}
        return {
            "body": json.dumps(entry),  # Serialize list to JSON
            "headers": {
                "Access-Control-Allow-Origin": "https://mtdock.com",
                "Access-Control-Allow-Methods": "GET,OPTIONS",
            },
            "statusCode": 200,
            "isBase64Encoded": "false",
        }

    except:
        return db.log_err(
            "[ERROR]: Cannot connect to database from handler.\n{}".format(
                traceback.format_exc()
            )
        )

    finally:
        try:
            cnx.close()
        except:
            pass

# if __name__ == "__main__":
#     event = {
#         "resource": "/your/resource/path",
#         "path": "/your/resource/path",
#         "httpsMethod": "POST",
#         "headers": {
#             "Accept": "*/*",
#             "Content-Type": "application/json",
#             "Host": "your-api-id.execute-api.your-region.amazonaws.com",
#             "User-Agent": "curl/7.53.1",
#         },
#         "multiValueHeaders": {"Accept": ["*/*"], "Content-Type": ["application/json"]},
#         "queryStringParameters": {"id": 2},
#         "multiValueQueryStringParameters": {
#             "param1": ["value1"],
#             "param2": ["value2", "value2B"],
#         },
#         "pathParameters": {"pathParam1": "value1"},
#         "stageVariables": {"stageVarName": "stageVarValue"},
#         "requestContext": {
#             "requestId": "request-id",
#             "path": "/your/resource/path",
#             "httpsMethod": "POST",
#             "stage": "prod",
#         },
#         "isBase64Encoded": False,
#     }
#     lambda_handler(event, None)
