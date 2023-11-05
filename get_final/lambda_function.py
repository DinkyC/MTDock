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
        SELECT text_id, edited_content   
        FROM edited_translations 
        """
        conditions = []
        params = []

        if kwargs.get("title"):
            conditions.append("JSON_EXTRACT(edited_translations.edited_content, '$.title') = %s")
            params.append(kwargs["title"])

        # Adjust the id condition based on direction
        if kwargs.get("id"):
            if kwargs.get("direction") == "next":
                conditions.append("edited_translations.text_id > %s")
            elif kwargs.get("direction") == "prev":
                conditions.append("edited_translations.text_id < %s")
            else:
                conditions.append("edited_translations.text_id = %s")
            params.append(kwargs["id"])

        if kwargs.get("providers_id"):
            conditions.append("translations.providers_id = %s")
            params.append(kwargs["providers_id"])

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

    if not id:
        logger.info("No id provided.")
    if not title:
        logger.info("No title provided.")

    try:
        query, params = db.construct_query(title=title, id=id, direction=direction, providers_id=providers_id)
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
        # If there's a result, process it
        if result:
            # Convert the tuple to a dictionary
            entry = {"id": result[0][0], "text": loaded}

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

