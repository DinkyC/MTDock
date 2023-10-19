from flask import Flask, render_template, url_for, redirect, flash, request
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
pymysql.install_as_MySQLdb()


#CA_CERT = os.environ['CA_CERT']

class AWSClient:
    def __init__(self):
        self.ssm = boto3.client("ssm")
        self.params_keys = ["put_final"]

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

    def get_parameters_from_store(self):
        response = self.ssm.get_parameters(Names=self.params_keys, WithDecryption=True)

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
    params_dict = aws.get_parameters_from_store()

    AWSRating = request.form.get('AWSRating')
    GCPRating = request.form.get('GCPRating')
    AzureRating = request.form.get('AzureRating')

    id = request.form.get('currentIndex')

    translation = request.form.get('finalTranslation')
    title, text = extract_title_and_text(translation)

    comments = request.form.get('CommentsContent')

    data = {
            "id": int(id),
            "title": title,
            "text": text
            }

    checksum = aws.compute_checksum(data)

    data["comments"] = comments
    data["aws_rating"] = AWSRating
    data["gcp_rating"] = GCPRating
    data["azure_rating"] = AzureRating
    data["checksum"] = checksum.hex()
   
    try:
        response = requests.post(params_dict.get('put_final'), data=json.dumps(data), headers={'Content-Type': 'application/json'})
        if response.status_code != 200:
            raise Exception(f"Unexpected status code: {response.content} {data}")
        flash('Successfully submitted!', 'success')
    except Exception as e:
        flash(f'Incorrect submission. Please check submission fields. Error: {e}', 'danger')


    return render_template('index.html')



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
