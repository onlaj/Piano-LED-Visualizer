from flask import Flask

UPLOAD_FOLDER = 'Songs/'


webinterface = Flask(__name__, template_folder='templates')
webinterface.config['TEMPLATES_AUTO_RELOAD'] = True
webinterface.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
webinterface.config['MAX_CONTENT_LENGTH'] = 32 * 1000 * 1000

from webinterface import views
from webinterface import views_api