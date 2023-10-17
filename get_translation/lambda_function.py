import pymysql
import logging
import traceback
import os 
import json
import boto3
import pdb
logger=logging.getLogger()
logger.setLevel(logging.INFO)

class HTDatabase:
    def construct_query(self, title_column, text_column, table, checksum_column, **kwargs):
        VALID_TABLES = ['final_translation', 'first_translation']
        VALID_COLUMNS = ['gcp_text', 'gcp_title', 'azure_text', 'azure_title', 'aws_title', 'aws_text',
                         'gcp_checksum', 'aws_checksum', 'azure_checksum', 'title', 'BodyText', 'checksum']
        
        # Sanitize table and column names
        if table not in VALID_TABLES:
            raise ValueError("Invalid table name")
        if title_column not in VALID_COLUMNS:
            raise ValueError("Invalid column name for title_column")
        if text_column not in VALID_COLUMNS:
            raise ValueError("Invalid column name for text_column")
        if checksum_column not in VALID_COLUMNS:
            raise ValueError("Invalid column name for checksum_column")

        base_query = f"SELECT id, {title_column}, {text_column}, {checksum_column} FROM {table}"
        conditions = []
        params = []
        
        if kwargs.get('title'):
            conditions.append(f"{title_column} = %s")
            params.append(kwargs['title'])
        if kwargs.get('id'):
            conditions.append("id = %s")
            params.append(kwargs['id'])

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        base_query += " LIMIT 1"
        
        return base_query, params

    def get_database_credentials(self):
        secret = self.get_secret()
        secret_dict = json.loads(secret)
        return secret_dict.get('username'), secret_dict.get('port'), secret_dict.get('database'), secret_dict.get('host')


    def get_secret(self):
        secret_name = "HighTimesDB"
        region_name = os.environ['AWS_REGION'] 
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager', region_name=region_name)
        try:
            get_secret_value_response = client.get_secret_value(SecretId=secret_name)
            return get_secret_value_response['SecretString']
        except Exception as e:
            raise e

    def make_connection(self):
        rds_client = boto3.client('rds')

        username, port, database, endpoint = self.get_database_credentials()

        database_token = rds_client.generate_db_auth_token(
            DBHostname=endpoint,
            Port=port,
            DBUsername=username,
            Region=os.environ['AWS_REGION']
            )

        return pymysql.connect(
            host=endpoint,
            user=username,
            passwd=database_token,
            port=int(port),
            db=database,  
            autocommit=True,
            ssl={'ssl': True}
        )

    def log_err(self, errmsg):
        logger.error(errmsg)
        return {"body": errmsg , "headers": {}, "statusCode": 400,
            "isBase64Encoded":"false"}

logger.info("Cold start complete.") 

def handler(event,context):
    db = HTDatabase()

    queryStringParameters = event.get("queryStringParameters", {})

    # Extract values or set to None if not provided
    id = queryStringParameters.get("id")
    title = queryStringParameters.get("title")

    title_column = queryStringParameters.get("title_column")
    text_column = queryStringParameters.get("text_column")
    checksum_column = queryStringParameters.get("checksum_column")
    table = queryStringParameters.get("table")

    if not id:
        logger.info("No id provided.")
    if not title:
        logger.info("No title provided.")

    try:
        if table == 'first_translation':
            query, params = db.construct_query(title_column, text_column, table, checksum_column, title=title, id=id)
        else:
            query, params = db.construct_query('title', 'BodyText', table, 'checksum', title=title, id=id)
    except Exception as e:
        logger.error(f"[ERROR]: Cannot construct query. {e}")
        return {
            "statusCode": 500,
            "body": f"[ERROR]: Cannot construct query.\n{str(e)}"
        }


    try:
        cnx = db.make_connection()
        cursor=cnx.cursor()
        
        try:
            cursor.execute(query, params)
        except:
            return db.log_err ("[ERROR]: Cannot execute cursor.\n{}".format(
                traceback.format_exc()) )

    
        try:
            result = cursor.fetchall()
            cursor.close()
        except:
            return db.log_err("[ERROR]: Cannot retrieve query data.\n{}".format(
                traceback.format_exc()))

        checksum = result[0][3].hex()
        # If there's a result, process it
        if result:
            # Convert the tuple to a dictionary
            entry = {
                "id": result[0][0],
                "title": result[0][1],
                "text": result[0][2],
                "checksum": checksum
            }
        else:
            entry = {}
        return {
            "body": json.dumps(entry),  # Serialize list to JSON
            "statusCode": 200,
            "headers" : {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET,OPTIONS',
                },
            "isBase64Encoded": "false"
        }

    except:
        return db.log_err("[ERROR]: Cannot connect to database from handler.\n{}".format(
            traceback.format_exc()))


    finally:
        try:
            cnx.close()
        except: 
            pass 

