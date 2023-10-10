import pymysql
import logging
import traceback
from os import environ
import json

endpoint=environ.get('ENDPOINT')
port=environ.get('PORT')
dbuser=environ.get('DBUSER')
password=environ.get('DBPASSWORD')
database=environ.get('DATABASE')


logger=logging.getLogger()
logger.setLevel(logging.INFO)

def construct_query(title=None, id=None):
    base_query = "SELECT id, title, BodyText FROM HighTimes"
    conditions = []
    params = []
    
    if title:
        conditions.append("title = %s")
        params.append(title)
    if id:
        conditions.append("id = %s")
        params.append(id)
    
    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)
    
    base_query += " LIMIT 1"
    
    return base_query, params


def make_connection():
    return pymysql.connect(host=endpoint, user=dbuser, passwd=password,
        port=int(port), db=database, autocommit=True)

def log_err(errmsg):
    logger.error(errmsg)
    return {"body": errmsg , "headers": {}, "statusCode": 400,
        "isBase64Encoded":"false"}

logger.info("Cold start complete.") 

def handler(event,context):
    queryStringParameters = event.get("queryStringParameters", {})

    # Extract values or set to None if not provided
    id = queryStringParameters.get("id")
    title = queryStringParameters.get("title")

    if not id:
        logger.info("No id provided.")
    if not title:
        logger.info("No title provided.")

    try:
        query, params = construct_query(title=title, id=id)
    except Exception as e:
        logger.error(f"ERROR: Cannot construct query. {e}")
        return {
            "statusCode": 500,
            "body": f"ERROR: Cannot construct query.\n{str(e)}"
        }


    try:
        cnx = make_connection()
        cursor=cnx.cursor()
        
        try:
            cursor.execute(query, params)
        except:
            return log_err ("ERROR: Cannot execute cursor.\n{}".format(
                traceback.format_exc()) )

    
        try:
            result = cursor.fetchall()
            cursor.close()
        except:
            return log_err("ERROR: Cannot retrieve query data.\n{}".format(
                traceback.format_exc()))
        # If there's a result, process it
        if result:
            # Convert the tuple to a dictionary
            entry = {
                "id": result[0][0],
                "title": result[0][1],
                "BodyText": result[0][2]
            }
        else:
            entry = {}
        return {
            "body": json.dumps(entry),  # Serialize list to JSON
            "headers": {
                "Content-Type": "application/json"  # Set appropriate response header
            },
            "statusCode": 200,
            "isBase64Encoded": "false"
        }

    except:
        return log_err("ERROR: Cannot connect to database from handler.\n{}".format(
            traceback.format_exc()))


    finally:
        try:
            cnx.close()
        except: 
            pass 


