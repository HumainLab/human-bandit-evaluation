import sys
sys.path.insert(0, '/var/www/html/flaskapp')

activate_this = '/home/ubuntu/preference-learning-platform/preference_learning_platform/env/bin/activate_this.py'
with open(activate_this) as file_:
    exec(file_.read(), dict(__file__=activate_this))

from server import app as application
