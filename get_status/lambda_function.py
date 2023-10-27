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


def lambda_handler(event, context):
    db = HTDatabase()
    
    query = """
    SELECT DISTINCT HighTimes.status, HighTimes.title, translations.lang_to, translations.lang_from 
    FROM HighTimes 
    LEFT JOIN translations ON HighTimes.id=translations.text_id 
    WHERE HighTimes.status='done' OR HighTimes.status='pending';
    """

    try:
        cnx = db.make_connection()
        cursor = cnx.cursor()

        try:
            cursor.execute(query)
        except Exception as e:
            return db.log_err(
                "[ERROR]: Cannot execute cursor.\n{}".format(traceback.format_exc())
            )

        try:
            columns = [desc[0] for desc in cursor.description]  # Get column names
            result = [dict(zip(columns, row)) for row in cursor.fetchall()]  # Convert result into list of dictionaries 
            cursor.close()
        except Exception as e:
            return db.log_err(
                "[ERROR]: Cannot fetch all. \n{}".format(traceback.format_exc())
            )

        return {
            "body": json.dumps(result),  # Serialize list to JSON
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,OPTIONS",
            },
            "statusCode": 200,
            "isBase64Encoded": "false",
        }
    except Exception as e:
            return db.log_err(
                "[ERROR]: Cannot execute cursor.\n{}".format(traceback.format_exc())
            )

# if __name__ == "__main__":
#     handler(None, None)
#





