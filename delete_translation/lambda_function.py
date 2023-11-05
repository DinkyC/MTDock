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
                "Access-Control-Allow-Origin": "https://mtdock.com",
                "Access-Control-Allow-Methods": "DELETE,OPTIONS",
            },
            "statusCode": 400,
            "isBase64Encoded": "false",
        }


logger.info("Cold start complete.")


def lambda_handler(event, context):
    db = HTDatabase()
    queryStringParameters = event.get("queryStringParameters", {})
    id = queryStringParameters.get("id")
    lang_from = queryStringParameters.get("lang_from")
    lang_to = queryStringParameters.get("lang_to")

    try:
        query_id = """
        SELECT COUNT(*) FROM translations WHERE text_id=%s AND lang_to=%s AND lang_from=%s;
        """

        # deleted text_id from translations
        query = """
        DELETE FROM translations WHERE text_id=%s AND lang_to=%s AND lang_from=%s;
        """
        cnx = db.make_connection()
        cursor = cnx.cursor()

        cursor.execute(query_id, (id, lang_to, lang_from))
        result = cursor.fetchone()

        if result[0] == 0:
            return db.log_err("[ERROR]: Article not translated yet")

        try:
            cursor.execute(query, (id, lang_to, lang_from))
            cnx.commit()  # Commit the DELETE operation
        except Exception as e:
            return db.log_err("[ERROR]: Cannot execute cursor.\n{}".format(traceback.format_exc()))

        check_query = """
        SELECT COUNT(*) FROM translations WHERE text_id = %s;
        """
        cursor.execute(check_query, (id,))
        result = cursor.fetchone()

        if result[0] == 0:
            query_update = """
            UPDATE HighTimes SET status=NULL WHERE id=%s;
            """
            try:
                cursor.execute(query_update, (id,))
                cnx.commit()  # Commit the UPDATE operation
            except Exception as e:
                return db.log_err("[ERROR]: Cannot update.\n{}".format(traceback.format_exc()))
        
        return {
            "body": "Deleted translations",  
            "headers": {
                "Access-Control-Allow-Origin": "https://mtdock.com",
                "Access-Control-Allow-Methods": "DELETE,OPTIONS",
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





