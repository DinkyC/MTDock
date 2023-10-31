from flask import Flask, render_template, url_for, redirect, flash, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from flask_bcrypt import Bcrypt
import pymysql
from datetime import timedelta
import os
import boto3
import json
import hashlib
import requests
import logging
import urllib.parse
import pandas as pd
pymysql.install_as_MySQLdb()

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class AWSClient:
    def __init__(self):
        self.ssm = boto3.client("ssm")

    def get_database_credentials(self):
        secret = self.get_secret()
        secret_dict = json.loads(secret)
        return secret_dict.get('username'), secret_dict.get('port'), secret_dict.get('database'), secret_dict.get('database_endpoint'), secret_dict.get('password')


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

    def get_parameters_from_store(self, params_keys):
        response = self.ssm.get_parameters(Names=params_keys, WithDecryption=True)

        # Construct a dictionary to hold the parameter values
        params_dict = {}

        for param in response["Parameters"]:
            params_dict[param["Name"]] = param["Value"]

        return params_dict
    
    def compute_checksum(self, data):
        return hashlib.sha256(str(data).encode("utf-8")).digest()


    # def make_token(self):
    #     rds_client = boto3.client('rds')
    #
    #     username, port, database, endpoint = self.get_database_credentials()
    #
    #     database_token = rds_client.generate_db_auth_token(
    #         DBHostname=endpoint,
    #         Port=port,
    #         DBUsername=username,
    #         Region=os.environ['AWS_REGION']
    #         )
    #
    #     return database_token 
    #
def create_app():
    aws = AWSClient()

    username, port, database, host, password = aws.get_database_credentials()

   # token = aws.make_token()

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{username}:{password}@{host}/{database}" #?ssl=1&ssl_ca=/home/daniel/dev/translate/TranslationPortalAWS/Translator_Dashboard/certs/AmazonRootCA1.pem"
    app.config['SECRET_KEY'] = 'thisisasecretkey'
    app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=14)

    db = SQLAlchemy()
    db.init_app(app)
    bcrypt = Bcrypt(app)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    return app, db, login_manager, bcrypt

app, db, login_manager, bcrypt = create_app()

def extract_title_and_text(data):
    # Step 1: Trim input
    lines = data.strip().split('\n')
    
    # Step 2: Set default values
    title = ""
    text = ""
    
    # Extract title if it exists
    if lines:
        title = lines[0]
    
    # Extract text if it exists
    if len(lines) > 1:
        # Step 4: Handle multiple newlines by filtering out empty lines
        text_lines = filter(bool, lines[1:])
        text = "\n".join(text_lines)
    
    return title, text

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)


class LoginForm(FlaskForm):
    username = StringField(validators=[
                           InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Username"})

    password = PasswordField(validators=[
                             InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})

    submit = SubmitField('Login')



@app.route('/', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if not user:
            flash('User does not exist. Please contact admin.', 'danger')
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                remember_me = True if request.form.get("remember") else False
                login_user(user, remember=remember_me)
                return redirect(url_for('dashboard'))
            else:
                flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', form=form)


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    return render_template('index.html')

@app.route('/translations', methods=['GET', 'POST'])
@login_required
def translations():
    return render_template('final.html')

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/submit_translation', methods=['POST'])
@login_required
def submit_translations():
    aws = AWSClient()
    parameter = ["put_final"]
    params_dict = aws.get_parameters_from_store(parameter)

    AWSRating = request.form.get('AWSRating')
    GCPRating = request.form.get('GCPRating')
    AzureRating = request.form.get('AzureRating')

    id = request.form.get('currentIndex')

    translation = request.form.get('finalTranslation')
    title, text = extract_title_and_text(translation)

    comments = request.form.get('CommentsContent')

    # Before constructing the data dictionary
    if not AWSRating or not GCPRating or not AzureRating or not title or not text:
        flash('Some required fields are missing!', 'danger')
        return redirect(url_for('dashboard'))

    data = {
            "id": int(id),
            "title": title,
            "text": text,
            "comments": comments,
            "aws_rating": int(AWSRating),
            "gcp_rating": int(GCPRating),
            "azure_rating": int(AzureRating)
            }
    
    check = {
        "text": text,
        "id": int(id)
            }

    checksum = aws.compute_checksum(check)

    data["checksum"] = checksum.hex()
   
    try:
        response = requests.post(params_dict.get('put_final'), json=data, headers={'Content-Type': 'application/json'})
        if response.status_code != 200:
            raise Exception(f"Unexpected status code: {response.content}")
        flash('Successfully submitted!', 'success')
    except Exception as e:
        flash(f'Incorrect submission. Please check submission fields. Error: {e}', 'danger')

    return redirect(url_for('dashboard'))  
    

@app.route('/get_status', methods=['GET', 'POST'])
@login_required
def status():
    aws = AWSClient()
    parameter = ["get_status"]
    params_dict = aws.get_parameters_from_store(parameter)
    
    response = requests.get(params_dict["get_status"], headers={'Content-Type': 'application/json'})
    
    data = response.json()
    df = pd.DataFrame(data)


    return jsonify(df.to_dict(orient='records'))

@app.route('/status', methods=['GET', 'POST'])
@login_required
def status_page():
    return render_template("status.html")


@app.route('/remove_from_queue/<id>', methods=['DELETE', 'POST'])
@login_required
def remove(id):
    aws = AWSClient()
    parameter = ["delete_trans"]
    params_dict = aws.get_parameters_from_store(parameter)

    headers = {'Content-Type': 'application/json'}
    data = request.get_json()  # Get the JSON data from the request body
    lang_to = data.get("lang_to")
    lang_from = data.get("lang_from")

    params = {"id": id, "lang_to": lang_to, "lang_from": lang_from}

    try:
        response = requests.delete(params_dict["delete_trans"], params=params, headers=headers)
        if response.status_code == 200:
            # Successfully removed item
            return jsonify({"success": True})
        else:
            # Failed to remove item
            return jsonify({"success": False, "error": "Failed to remove item"}), 500  # Return an error status code
    except Exception as e:
        logger.error("Request failed")
        return jsonify({"success": False, "error": "Request failed"}), 500  # Return an error status code


@app.route('/queue/<id>', methods=['POST'])
@login_required
def queue(id):
    aws = AWSClient()
    parameter = ["push_to_fifo"]
    params_dict = aws.get_parameters_from_store(parameter)

    headers = {'Content-Type': 'application/json'}

    from_lang = request.args.get("from_lang")
    to_lang = request.args.get("to_lang")

    params = {
        "from_lang": from_lang,
        "to_lang": to_lang,
        "id": id
            }

    try:
        response = requests.post(params_dict["push_to_fifo"], params=params, headers=headers)
        if response.status_code == 200:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to remove item"}), 500  # Return an error status code
    except Exception as e:
        logger.error("Request failed")
        return jsonify({"success": False, "error": "Request failed"}), 500  # Return an error status code

@app.route('/get_articles', methods=['GET'])
@login_required
def get_articles():
    aws = AWSClient()
    parameter = ["get_article"]
    params_dict = aws.get_parameters_from_store(parameter)
    headers = {'Content-Type': 'application/json'}
    id = request.args.get("id")
    print(f"id is equal to -> {id}")
    title = request.args.get("title")

    params = {"id": id}

    if title:
        decoded_title = urllib.parse.unquote(title)
        params["title"] = decoded_title
        try:
            response = requests.get(params_dict["get_article"], params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                df = pd.DataFrame(data, index=[0])
                return jsonify(df.to_dict(orient='records'))
        except Exception as e:
            return jsonify({"success": False, "error": "Failed to get item"}), 500 
    try:
        response = requests.get(params_dict["get_article"], params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                df = pd.DataFrame(data, index=[0])
                return jsonify(df.to_dict(orient='records'))
            else:
                df = pd.DataFrame(data)
                return jsonify(df.to_dict(orient='records'))
        else:
            return jsonify({"success": False, "error": "Failed to get items"}), 500  # Return an error status code
    except Exception as e:
        logger.error("Request failed")
        return jsonify({"success": False, "error": "Request failed"}), 500  # Return an error status code

   



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
