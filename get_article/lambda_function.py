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
        base_query = "SELECT id, title, BodyText FROM HighTimes"
        conditions = []
        params = []

        title = kwargs.get('title')
        id = kwargs.get('id')
        page = kwargs.get('page')
        per_page = kwargs.get('per_page')

        if title:
            conditions.append("title = %s")
            params.append(title)
        if id:
            conditions.append("id = %s")
            params.append(id)

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        if page is not None and per_page is not None:
            offset = (page - 1) * per_page
            base_query += f" LIMIT {per_page} OFFSET {offset}"
        else:
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
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,OPTIONS",
            },
            "statusCode": 400,
            "isBase64Encoded": "false",
        }


logger.info("Cold start complete.")


def handler(event, context):
    db = HTDatabase()

    queryStringParameters = event.get("queryStringParameters", {})

    # Extract values or set to None if not provided
    id = queryStringParameters.get("id")
    title = queryStringParameters.get("title")

    page = queryStringParameters.get("page")
    per_page = queryStringParameters.get("per_page")

    if not id:
        logger.info("No id provided.")
    if not title:
        logger.info("No title provided.")

    try:
        query, params = db.construct_query(title=title, id=id, page=page, per_page=per_page)
    except Exception as e:
        logger.error(f"[ERROR]: Cannot construct query. {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
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

        entries = []

        # If there's a result, process it
        if result:
            if len(result) == 1:
                # If there's only one result, return it as a dictionary
                entry = {"id": result[0][0], "title": result[0][1], "text": result[0][2]}
                return {
                    "body": json.dumps(entry),  # Serialize dictionary to JSON
                    "headers": {
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET,OPTIONS",
                    },
                    "statusCode": 200,
                    "isBase64Encoded": False,  # Boolean value, not a string
                }
            else:
                # If there are multiple results, process them as a list of dictionaries
                for row in result:
                    entry = {"id": row[0], "title": row[1], "text": row[2]}
                    entries.append(entry)
        else:
            # Handle the case when there are no results
            entry = {}
            return {
                "body": json.dumps(entry),  # Serialize dictionary to JSON
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET,OPTIONS",
                },
                "statusCode": 200,
                "isBase64Encoded": False,  # Boolean value, not a string
            }

        # If there are multiple results, return them as a list of dictionaries
        return {
            "body": json.dumps(entries),  # Serialize list of dictionaries to JSON
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,OPTIONS",
            },
            "statusCode": 200,
            "isBase64Encoded": False,  # Boolean value, not a string
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
#         "httpMethod": "POST",
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
#             "httpMethod": "POST",
#             "stage": "prod",
#         },
#         "isBase64Encoded": False,
#     }
#     handler(event, None)
