# Redefining the structured classes and lambda handler
import boto3
import os
import requests
import json
import ast
from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime, JSON, LargeBinary
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import logging
from botocore.exceptions import ClientError
import hashlib
import traceback
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
# Define the SQLAlchemy ORM model for the 'HighTimes' table
Base = declarative_base()

def log_err(errmsg):
    logger.error(errmsg)
    return {"body": errmsg , "headers": {}, "statusCode": 400,
        "isBase64Encoded":"false"}


class HighTimes(Base):
    __tablename__ = 'first_translation'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=True)
    BodyText = Column(Text, nullable=True)
    checksum = Column(LargeBinary, nullable=True)  # Added checksum column

class DatabaseManager:
    def __init__(self):
        try:
            self.username, self.password, self.endpoint = self.get_database_credentials()
            logger.info(f"successfully got username, password and endpoint {self.endpoint}")
        except Exception as e:
            return log_err ("ERROR: Cannot get credentials.\n{}".format(
                traceback.format_exc()))

        try:
            self.DATABASE_URL = f"mysql+pymysql://{self.username}:{self.password}@{self.endpoint}/HighTimes"
            self.engine = create_engine(self.DATABASE_URL)
            self.Session = sessionmaker(bind=self.engine)
            logger.info(f"successfully made database connect {self.DATABASE_URL}")
        except Exception as e:
            return log_err ("ERROR: Cannot initiate engine.\n{}".format(
                traceback.format_exc()))
        
    def get_database_credentials(self):
        secret = self.get_secret()
        secret_dict = json.loads(secret)
        return secret_dict.get('username'), secret_dict.get('password'), secret_dict.get('host')

    @staticmethod
    def compute_checksum(data):
        return hashlib.sha256(str(data).encode('utf-8')).digest()

    def get_secret(self):
        secret_name = "HighTimesDB"
        region_name = "us-west-1"
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager', region_name=region_name)
        try:
            get_secret_value_response = client.get_secret_value(SecretId=secret_name)
            return get_secret_value_response['SecretString']
        except ClientError as e:
            return log_err ("ERROR: Cannot get secret value.\n{}".format(
                traceback.format_exc()))

    def insert_translation(self, translated_data):
        try:
            session = self.Session()
        except Exception as e:
            return log_err ("ERROR: Failed to start session.\n{}".format(
                traceback.format_exc()))

        title = translated_data.get('title')
        text = translated_data.get('text')
        ID = translated_data.get('id')
        checksum = self.compute_checksum(translated_data)
        try:
            entry = HighTimes(id=ID, title=title, BodyText=text, checksum=checksum)
        except Exception as e:
            return log_err ("ERROR: Cannot failed to string together data.\n{}".format(
                traceback.format_exc()))

        try:
            session.add(entry)
            session.commit()
            return {"status": "success", "message": "Data inserted successfully."}
        except Exception as e:
            session.rollback()
            return log_err ("ERROR: Cannot insert data.\n{}".format(
                traceback.format_exc()))
        finally:
            session.close()


# Main Lambda Handler
def handler(event, context):
    # Extracting data from the event
    translated_title = event.get("title")
    translated_text = event.get("text")
    record_id = event.get("id")  # Assuming the key for the ID in the event is "id"
    logger.info(f"{translated_text} \n {translated_title} \n {record_id}")
    if not (translated_title and translated_text and record_id):
        return {"status": "failure", "message": "Missing required data in the request."}

    translated_data = {"title": translated_title, "text": translated_text, "id": record_id}

    logger.info(translated_data)
    
    # Sending translated data to RDS
    try:
        send_to_rds_response = DatabaseManager().insert_translation(translated_data)
        logger.info("made insertion")
    except Exception as e:
        return log_err ("ERROR: Cannot insert data.\n{}".format(
            traceback.format_exc()))

    return {
        "status": "success",
        "translated_data": translated_data,
        "db_response": send_to_rds_response
    }

# if __name__ == "__main__":
#     event = {"translated_text" : "hello", "translated_title" : "yup", "id" : 20}
#     handler(event, {})
