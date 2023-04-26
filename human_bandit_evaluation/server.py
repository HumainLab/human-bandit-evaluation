"""Rapport Rating Collection System Server
Usage:
    server.py [options]

Options:
    -h --help           Display this message.
    -v --version        Display current version.
    -d --debug          Flask debug option
    -p --port=<int>     Flask server port [default: 8000]
    --db=<file>         File to TinyDB json [default: ./database/db.json]
    --counter=<file>    File path to TinyDB counter [default: ./database/counter.json]
"""
import boto3
import datetime
import json
import logging
import logging.config
import os
import pickle
import random
import time

from configobj import ConfigObj
from docopt import docopt
from enum import Enum
from flask import (Flask, Response, jsonify, render_template, request, redirect,
                   send_from_directory, url_for)
from flask_login import current_user, UserMixin
import flask_login
from xml.dom.minidom import parseString

# from tinydb import TinyDB, Query
from pymongo import MongoClient
#import sqlite3
from algorithms import FixedSequence, EpsilonGreedy, ExploreThenCommit, TS, UserSelected, UCB

logger = logging.getLogger()

app = Flask(__name__, template_folder='app/templates',
            static_folder='app/static')
client = MongoClient('localhost', 27017)
users_db = client.users.users
responses_db = client.responses.responses
survey_db = client.survey.survey
attention_check_db = client.attention_check.attention_check
mdb = client.newsent_database

# categories = ['Family', 'Gag', 'Office', 'Political']
# colors = ["#ff993c", "#75c44c", "#6e7ec0", "#b82b57"]
categories = ['Family', 'Gag', 'Political (Conservative)', 'Office', 'Political (Liberal)']
colors = ["#6e7ec0", "#6e7ec0", "#6e7ec0", "#6e7ec0", "#6e7ec0"]
category_to_path = {'Family': 'family/baldo',
                    'Gag': 'gag/theargylesweater',
                    'Office': 'office/the-born-loser',
                    'Political (Conservative)': 'political/lisabenson',
                    'Political (Liberal)': 'political/nickanderson'}

fake_mturk_database = ['123', '456', '789']

login_manager = flask_login.LoginManager()
login_manager.init_app(app)
# Set the secret key to some random bytes. Keep this really secret!
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

class User(UserMixin):
    def __init__(self, user_id, username):
        self.user_id = user_id
        self.username = username
        # NOTE: For now, set is_authenticated to True so that authorization
        #       essentially persists across sessions for free. Later on, this
        #       should be stored in an actual database.
        # self._is_authenticated = False
        self._is_authenticated = True 
    def get_id(self):
        return self.user_id

@login_manager.user_loader
def load_user(user_id):
    u = users_db.find_one({"user_id": user_id})
    if not u:
        return
    user = User(u['user_id'], u['username'])
    return user

@login_manager.request_loader
def request_loader(request):
    username = request.form.get('username')
    u = users_db.find_one({"username": username})
    if (not u) or (request.form['password'] != u['password']):
        return
    else:
        user = User(u['user_id'], request.form['username'])
        return user

@app.route("/")
def root():
    if current_user.is_authenticated:
        if all_tasks_completed(current_user):
            if all_survey_tasks_completed(current_user):
                return redirect(url_for('finish'))
            elif has_initial_survey_task(current_user):
                return redirect(url_for('survey'))
            else:
                return redirect(url_for('end_of_study'))
        # TODO: Check if there is an existing session that the user was
        #       disconnected from. If so, reinitialize the session to the
        #       previous save point. Otherwise, start an experiment.
        if is_recent_task_completed(current_user):
            algorithm, recent_task_id, seen_imgs = get_user_state(current_user)

            fixed_task_parameters = get_fixed_task_parameters(current_user)
            fixed_task_parameters = fixed_task_parameters[recent_task_id]
            # Sample the image to show.
            if isinstance(algorithm, UserSelected):
                next_category = categories[0]
            elif is_instance_of_bandit_algorithm(algorithm):
                next_category = categories[algorithm.get_arm()]
            elif isinstance(algorithm, FixedSequence):
                next_category = fixed_task_parameters.category
            next_task_id = recent_task_id + 1
            category = category_to_path[next_category]
            if fixed_task_parameters.sample_method == 'random':
                img_path = sample_img_from_category(category, seen_imgs)
            elif fixed_task_parameters.sample_method == 'increasing_order':
                img_path = sample_img_from_category_in_increasing_order(
                        category, seen_imgs)
                print("Pick increasing order for category %s with path %s" % (category, img_path))
            else:
                img_path = fixed_task_parameters.image_path
            # Apply attention check.
            fixed_task_parameters = resolve_manual_attention_checks_for_fixed_task_parameters(
                    fixed_task_parameters, img_path)
            attention_checks = fixed_task_parameters.attention_checks
            # Record beginning of the task.
            responses_db.insert_one({
                'user_id': current_user.user_id,
                'task_id': next_task_id,
                'image_category': category,
                'image_path': img_path,
                'start_time': time.time(),
                'task_completed': False,
                'algorithm': pickle.dumps(algorithm),
                'attention_checks': fixed_task_parameters.attention_checks
            })
        else:
            most_recent_response = get_most_recent_response(current_user)
            img_path = most_recent_response['image_path']
            recent_task_id = most_recent_response['task_id']
            next_task_id = recent_task_id  # The current task is incomplete.
            attention_checks = most_recent_response['attention_checks']
        print('attention_checks', attention_checks)
        # Show next category choice buttons if there is at least one entry left
        # for UserSelected mode.
        is_user_selected = check_user_selected(current_user)
        category_items = None
        if is_user_selected:
            if not one_task_away_from_completion(current_user):
                category_items = list(zip(range(len(categories)), categories, colors))
                random.shuffle(category_items)
        print('category_items', category_items)

        return render_template("index.html",
                               categories=category_items,
                               img_path=img_path,
                               task_id=next_task_id,
                               attention_checks=attention_checks,
                               is_user_selected=is_user_selected)
    else:
        return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == 'POST':
        u = users_db.find_one({"username": request.form['username']})
        if (u is not None) and (request.form['password'] == u['password']):
            user = User(u['user_id'], request.form['username'])
            flask_login.login_user(user)
            return redirect(url_for('root'))
        else:
            error = 'Invalid Credentials. Please try again.'
    return render_template("login.html", error=error)

@app.route("/login/user=<username>/password=<password>")
def login_auto(username, password):
    error = None
    u = users_db.find_one({"username": username})
    if (u is not None) and (password == u['password']):
        user = User(u['user_id'], username)
        flask_login.login_user(user)
        return redirect(url_for('root'))
    else:
        error = 'Invalid Credentials. Please try again.'
    return render_template("login.html", error=error)

class MTurkApprovalStatus(Enum):
    Approved = 1
    IncorrectQualtricsCode = 2
    MTurkIDNotFound = 3
@app.route("/mturk_authenticate", methods=["GET", "POST"])
def mturk_authenticate():
    username, password, error = None, None, None
    error_msg = ('One of the following errors occured: '
                 '    (1) MTurk Worker ID is not valid or study is already complete. '
                 'Please enter a valid MTurk Worker ID. '
                 '    (2) If you just completed the initial survey task, you may have '
                 'to wait up to 1-2 minutes to continue to this task. '
                 'If you have any further questions, please contact the '
                 'requester.')
    if current_user.is_authenticated:
        u = users_db.find_one({"user_id": current_user.get_id()})
        if all_tasks_completed(current_user) and all_survey_tasks_completed(current_user):
            error = error_msg
        else:
            username, password = u['username'], u['password']
    elif request.method == 'POST':
        mturk_id = request.form['mturk_id']
        mturk_validation_result = validate_mturk_status(mturk_id)
        # if mturk_id not in fake_mturk_database:    \\ This is for debugging.
        if mturk_validation_result == MTurkApprovalStatus.MTurkIDNotFound:
            error = error_msg
        elif mturk_validation_result == MTurkApprovalStatus.IncorrectQualtricsCode:
            error = ('Unfortunately, your Qualtrics code is incorrect so you '
                     'cannot participate in this study.')
        elif mturk_validation_result == MTurkApprovalStatus.Approved:
            # Assign the MTurker a username and password, or retrieve the one
            # that has been assigned. Only return the user information if the
            # user is being assigned or the task has not been finished.
            u = users_db.find_one({"mturk_id": mturk_id})
            if u is None:
                candidate_users = list(users_db.find({"mturk_id": None}))
                if len(candidate_users) == 0:
                    error = error_msg
                else:
                    selected_user = random.choice(candidate_users)
                    selected_user['mturk_id'] = mturk_id
                    users_db.replace_one({'user_id': selected_user['user_id']},
                                         selected_user)
            else:
                selected_user = u
                if all_tasks_completed(User(u['user_id'], u['username'])):
                    error = error_msg
                    selected_user = None
            if selected_user is not None:
                username = selected_user['username']
                password = selected_user['password']
    return render_template("mturk_auth.html", username=username,
                           password=password, error=error)

@app.route("/static/images/<filename>", methods=["GET"])
def send_image(filename):
    if current_user.is_authenticated:
        if all_tasks_completed(current_user) or all_survey_tasks_completed(current_user):
            return redirect(url_for('root'))
        else:
            base = os.path.dirname(os.path.abspath(__file__))
            image_dir = os.path.join(base, 'app', 'static', 'images')
            return send_from_directory(image_dir, filename)
    else:
        return redirect(url_for('login'))

@app.route("/finish")
def finish():
    if current_user.is_authenticated:
        if all_tasks_completed(current_user):
            if all_survey_tasks_completed(current_user):
                return render_template("finish.html",
                                       survey_code=get_survey_code(current_user))
            elif has_initial_survey_task(current_user):
                return redirect(url_for('survey'))
            else:
                return redirect(url_for('end_of_study'))
        else:
            return redirect(url_for('root'))
    else:
        return redirect(url_for('login'))

@app.route("/end_of_study")
def end_of_study():
    if current_user.is_authenticated:
        return render_template("end_of_study.html")
    else:
        return redirect(url_for('login'))

@app.route("/survey", methods=["GET", "POST"])
def survey():
    if current_user.is_authenticated:
        if all_tasks_completed(current_user):
            if all_survey_tasks_completed(current_user):
                return redirect(url_for('root'))
            algorithm, _, _ = get_user_state(current_user)
            u = users_db.find_one({"user_id": current_user.get_id()})
            presurvey_entries = list(survey_db.find({"user_id": int(current_user.user_id),
                                                     "final_survey": False})
                                              .sort('start_time', -1))
            # If there is a dangling survey entry, then a GET request should
            # replay the pre-survey task and a POST request should complete
            # the pre-survey task.
            if (len(presurvey_entries) > 0) and (not presurvey_entries[0]['task_completed']):
                last_survey_entry = presurvey_entries[0]
                if request.method == 'GET':
                    # Replay this particular task.
                    image_path1 = last_survey_entry['image_path1']
                    image_path2 = last_survey_entry['image_path2']
                    return render_template("survey.html",
                                           survey_type=last_survey_entry['survey_type'],
                                           image_path1=image_path1,
                                           image_path2=image_path2,
                                           color=colors[0],
                                           task_id=len(presurvey_entries))
                else:
                    content = request.json or request.form
                    data = content.to_dict()
                    finalized_survey_entry = presurvey_entries[0]
                    finalized_survey_entry['session_start_time'] = float(data['start_time'])
                    finalized_survey_entry['finish_time'] = float(data['finish_time'])
                    finalized_survey_entry['submit_time'] = float(data['submit_time'])
                    finalized_survey_entry['task_completed'] = True
                    finalized_survey_entry['user_response'] = data['user_response']
                    survey_db.replace_one({'user_id': presurvey_entries[0]['user_id'],
                                           'survey_task_id': presurvey_entries[0]['survey_task_id']},
                                          finalized_survey_entry)
                    return redirect(url_for('root'))
            # If the pre-survey tasks are all completed, then run the survey.
            # Otherwise, initialize a new pre-survey task.
            if len(presurvey_entries) == u["num_survey_entries_to_show"]:
                if request.method == 'GET':
                    is_algorithm_driven = is_instance_of_bandit_algorithm(algorithm)
                    return render_template("survey.html",
                                           color=colors[0],
                                           is_algorithm_driven=is_algorithm_driven)
                else:
                    user_response = []
                    content = request.json or request.form
                    data = content.to_dict()
                    print(data)
                    num_responses = len([x for x in data.keys()
                                         if x.startswith('user_response')]) // 2
                    for i in range(num_responses):
                        question = data['user_response[%d][question]' % i]
                        answer = data['user_response[%d][answer]' % i]
                        user_response.append(dict(question=question, answer=answer))
                    survey_db.insert_one({
                        'user_id': current_user.user_id,
                        'survey_task_id': len(presurvey_entries) + 1,
                        'user_response': user_response,
                        'task_completed': True,
                        'final_survey': True
                    })
            else:
                survey_parameters = get_survey_parameters(current_user)[len(presurvey_entries)]
                # Initialize a new task
                new_survey_entry = {
                    'user_id': current_user.user_id,
                    'survey_task_id': len(presurvey_entries) + 1,
                    'survey_type': survey_parameters['survey_type'],
                    'start_time': time.time(),
                    'task_completed': False,
                    'final_survey': False
                }
                responses = responses_db.find({"user_id": int(current_user.user_id),
                                               "task_completed": True})
                seen_paths = set([x['image_path1'] for x in presurvey_entries] +
                                 [x['image_path2'] for x in presurvey_entries])
                unseen_responses = [x for x in responses if x['image_path'] not in seen_paths]
                if survey_parameters['survey_type'] == 'pairwise_memory':
                    # Sample two previous entries at random.
                    response1 = random.choice(unseen_responses)
                    unseen_responses.remove(response1)
                    response2 = random.choice(unseen_responses)
                    new_survey_entry['image_path1'] = response1['image_path']
                    new_survey_entry['image_path2'] = response2['image_path']
                    new_survey_entry['enjoyment_score1'] = response1['enjoyment_score']
                    new_survey_entry['enjoyment_score2'] = response2['enjoyment_score']
                elif survey_parameters['survey_type'] == 'memory':
                    # Sample one of the previous entries at random, or one of the unseen
                    # images, each with 50% probability.
                    if random.randint(0, 1):
                        response = random.choice(unseen_responses)
                    else:
                        unseen_out_of_sample_responses = []
                        for category in categories:
                            unseen_out_of_sample_responses += [x for x in show_all_imgs_by_category(category_to_path[category]) if x not in seen_paths]
                        image_path = random.choice(unseen_out_of_sample_responses)
                        response = dict(image_path=image_path, enjoyment_score=-1)
                    new_survey_entry['image_path1'] = response['image_path']
                    new_survey_entry['image_path2'] = ''
                    new_survey_entry['enjoyment_score1'] = response['enjoyment_score']
                    new_survey_entry['enjoyment_score2'] = -1
                elif survey_parameters['survey_type'] == 'rating_memory':
                    response = random.choice(unseen_responses)
                    new_survey_entry['image_path1'] = response['image_path']
                    new_survey_entry['image_path2'] = ''
                    new_survey_entry['enjoyment_score1'] = response['enjoyment_score']
                    new_survey_entry['enjoyment_score2'] = -1
                survey_db.insert_one(new_survey_entry)
                return render_template("survey.html",
                                       survey_type=survey_parameters['survey_type'],
                                       image_path1=new_survey_entry['image_path1'],
                                       image_path2=new_survey_entry['image_path2'],
                                       color=colors[0],
                                       task_id=len(presurvey_entries) + 1)
        return redirect(url_for('root'))
    else:
        return redirect(url_for('login'))


@app.route('/submit', methods=["POST"])
def submit():
    content = request.json or request.form
    data = content.to_dict()
    obj = {}

    # Load (presumably) incomplete entry to finalize with submission.
    incomplete_response_entry = responses_db.find_one({
        'user_id': current_user.user_id,
        'task_id': int(data['task_id']),
    })
    path_to_category = {y:x for (x, y) in category_to_path.items()}
    prev_image_category = path_to_category[incomplete_response_entry['image_category']]
    prev_image_category_arm = categories.index(prev_image_category)
    print(incomplete_response_entry)
    if incomplete_response_entry['task_completed']:
        print("Dropping redundant request for user_id %d, task_id %d." %
              (current_user.user_id, int(data['task_id'])))
        return jsonify(dict(refresh_page=True))

    # Insert entry in responses DB and sample the next image to show
    # which should not overlap with any previous shown image.
    algorithm, recent_task_id, seen_imgs = get_user_state(current_user)
    next_task_id = recent_task_id + 1
    enjoyment_score = float(data['feedback']) if len(data['feedback']) > 0 else -1.0
    assert int(enjoyment_score) == enjoyment_score
    enjoyment_score = int(enjoyment_score)
    # Choose the next category based on the algorithm.
    if isinstance(algorithm, UserSelected):
        user_selected_category = data['user_selected_category']
        if user_selected_category in category_to_path:
            category = category_to_path[user_selected_category]
        else:
            category = ''
    elif is_instance_of_bandit_algorithm(algorithm):
        user_selected_category = data['user_selected_category']
        algorithm.update_arm(prev_image_category_arm, enjoyment_score)
        category = category_to_path[categories[algorithm.get_arm()]]
    elif isinstance(algorithm, FixedSequence):
        user_selected_category = data['user_selected_category']
        # fixed_sequence_categories = get_fixed_sequence_categories(current_user)
        if next_task_id <= len(get_fixed_task_parameters(current_user)):
            # category = category_to_path[fixed_sequence_categories[next_task_id-1]]
            fixed_task_parameters = get_fixed_task_parameters(current_user)[next_task_id-1]
            category = category_to_path[fixed_task_parameters.category]
        else:
            category = ''

    # Process attention checks.
    finalized_attention_checks = []
    prev_fixed_task_parameters = get_fixed_task_parameters(current_user)[recent_task_id-1]
    prev_fixed_task_parameters = resolve_manual_attention_checks_for_fixed_task_parameters(
            prev_fixed_task_parameters, incomplete_response_entry['image_path'])
    if prev_fixed_task_parameters.attention_checks is not None:
        unfinalized_attention_checks = {x['question']: x for x in
                                        prev_fixed_task_parameters.attention_checks}
        print(unfinalized_attention_checks)
        # Javascript dictionaries must be indexed by the full path that includes
        # the nested key, which includes 'question' and 'user_response'.
        num_attention_checks = len([x for x in data.keys() if x.startswith('attention_checks')]) // 2
        for i in range(num_attention_checks):
            question = data['attention_checks[%d][question]' % i]
            user_response = data['attention_checks[%d][user_response]' % i]
            entry = unfinalized_attention_checks[question]
            entry['user_response'] = user_response
            finalized_attention_checks.append(entry)

    # Insert entry for the response into the database.
    print(current_user.user_id, int(data['task_id']))
    print(type(current_user.user_id), int(data['task_id']))
    print(list(responses_db.find()))
    finalized_response_entry = {
        'user_id': incomplete_response_entry['user_id'], # user_id is synonymous with exp_id
        'task_id': incomplete_response_entry['task_id'], # the ID of this particular user-img task
        'start_time': incomplete_response_entry['start_time'],
        'session_start_time': float(data['start_time']),
        'finish_time': float(data['finish_time']),
        'submit_time': float(data['submit_time']),
        'enjoyment_score': enjoyment_score,
        'image_category': incomplete_response_entry['image_category'],
        'user_selected_category': user_selected_category, # Optional.
        'image_path': incomplete_response_entry['image_path'],
        'algorithm': pickle.dumps(algorithm),
        'attention_checks': finalized_attention_checks,
        'task_completed': True
    }
    responses_db.replace_one({'user_id': incomplete_response_entry['user_id'],
                              'task_id': incomplete_response_entry['task_id']},
                             finalized_response_entry)
    if not all_tasks_completed(current_user):
        fixed_task_parameters = get_fixed_task_parameters(current_user)[next_task_id-1]
        if fixed_task_parameters.sample_method == 'random':
            next_image_path = sample_img_from_category(category, seen_imgs)
        elif fixed_task_parameters.sample_method == 'increasing_order':
            next_image_path = sample_img_from_category_in_increasing_order(
                    category, seen_imgs)
            print("Pick increasing order for category %s with path %s" % (category, next_image_path))
        else:
            next_image_path = fixed_task_parameters.image_path

        fixed_task_parameters = resolve_manual_attention_checks_for_fixed_task_parameters(
            fixed_task_parameters, next_image_path)
        print('attention_checks', fixed_task_parameters.attention_checks)
        obj['next_image_path'] = next_image_path
        obj['task_id'] = next_task_id
        obj['last_task'] = (check_user_selected(current_user) and
                            one_task_away_from_completion(current_user))
        obj['attention_checks'] = fixed_task_parameters.attention_checks
        obj['refresh_page'] = False
        # Possibly add randomized categories for next entry.
        if check_user_selected(current_user):
            if not one_task_away_from_completion(current_user):
                category_items = categories.copy()
                random.shuffle(category_items)
                obj['next_categories'] = category_items
                print('Adding next_categories', category_items)
        responses_db.insert_one({
            'user_id': current_user.user_id,
            'task_id': next_task_id,
            'image_category': category,
            'image_path': next_image_path,
            'start_time': time.time(),
            'task_completed': False,
            'algorithm': pickle.dumps(algorithm),
            'attention_checks': fixed_task_parameters.attention_checks
        })
    else:
        obj['next_image_path'] = '' 

    return jsonify(obj)


def sample_img_from_category(category, seen_imgs):
    # Apply policy to select the next comic here.
    import glob
    base = os.path.dirname(os.path.abspath(__file__))
    image_dir = os.path.join(base, 'app', 'static', 'images')
    available_paths = glob.glob(os.path.join(image_dir, category, "*.jpg"))
    available_paths = [os.path.join('static/images', category, x.split('/')[-1])
                       for x in available_paths]
    available_paths = list(filter(lambda x: x not in seen_imgs, available_paths))
    app.logger.error(base)
    app.logger.error(os.path.join(image_dir, category, "*.jpg"))
    next_image_path = random.choice(available_paths)
    return next_image_path

def sample_img_from_category_in_increasing_order(category, seen_imgs):
    # Apply policy to select the next comic here.
    import glob
    base = os.path.dirname(os.path.abspath(__file__))
    image_dir = os.path.join(base, 'app', 'static', 'images')
    available_paths = glob.glob(os.path.join(image_dir, category, "*.jpg"))
    available_paths = [os.path.join('static/images', category, x.split('/')[-1])
                       for x in available_paths]
    available_paths = list(filter(lambda x: x not in seen_imgs, available_paths))
    # available_paths = sorted(
    #     available_paths, key=lambda x: int(x.split('/')[-1].rstrip('.jpg')))
    available_paths = sorted(available_paths, key=lambda x: int(x.split('/')[-1].split('_')[0]))
    return available_paths[0]

def show_all_imgs_by_category(category):
    import glob
    base = os.path.dirname(os.path.abspath(__file__))
    image_dir = os.path.join(base, 'app', 'static', 'images')
    available_paths = glob.glob(os.path.join(image_dir, category, "*.jpg"))
    available_paths = [os.path.join('static/images', category, x.split('/')[-1])
                       for x in available_paths]
    return available_paths

def one_task_away_from_completion(user):
    u = users_db.find_one({"user_id": user.get_id()})
    all_responses = list(responses_db.find({"user_id": int(user.user_id),
                                            "task_completed": True}))
    return len(all_responses) == (u["num_entries_to_show"]-1)

def all_tasks_completed(user):
    u = users_db.find_one({"user_id": user.get_id()})
    all_responses = list(responses_db.find({"user_id": int(user.user_id),
                                            "task_completed": True}))
    return len(all_responses) >= u["num_entries_to_show"]

def all_survey_tasks_completed(user):
    u = users_db.find_one({"user_id": user.get_id()})
    presurvey_entries = list(survey_db.find({"user_id": int(user.user_id),
                                             "task_completed": True,
                                             "final_survey": False}))
    completed_survey_entry = list(survey_db.find({"user_id": int(user.user_id),
                                                  "task_completed": True,
                                                  "final_survey": True}))
    return ((len(presurvey_entries) == u["num_survey_entries_to_show"]) and
            (len(completed_survey_entry) >= 1))

def has_initial_survey_task(user):
    u = users_db.find_one({"user_id": user.get_id()})
    survey_entries = list(survey_db.find({"user_id": int(user.user_id)}))
    return len(survey_entries) > 0

def get_survey_code(user):
    u = users_db.find_one({"user_id": user.get_id()})
    return u['survey_code']

def get_user_state(user):
    num_responses = responses_db.find({'user_id': int(user.user_id)}).count()
    if num_responses > 0:
        previous_responses = list(responses_db.find({'user_id': int(user.user_id)})
                                              .sort('start_time', -1))
        most_recent_response = get_most_recent_response(user)
        algorithm = pickle.loads(most_recent_response['algorithm'])
        recent_task_id = int(max([x['task_id'] for x in previous_responses]))
        seen_imgs = [x['image_path'] for x in previous_responses]
    else:
        # Read the pickled algorithm stored in the users database.
        user_entry = users_db.find_one({'user_id': int(user.user_id)})
        algorithm = pickle.loads(bytes(user_entry['algorithm']))
        recent_task_id, seen_imgs = 0, []
    return algorithm, recent_task_id, seen_imgs

def is_recent_task_completed(user):
    most_recent_response = get_most_recent_response(user)
    return ((most_recent_response == None) or
            most_recent_response['task_completed'])

def get_most_recent_response(user):
    num_responses = responses_db.find({'user_id': int(user.user_id)}).count()
    if num_responses == 0:
        return None
    all_previous_responses = list(responses_db.find({'user_id': int(user.user_id)})
                                              .sort('start_time', -1))
    most_recent_response = all_previous_responses[0]
    return most_recent_response

def check_user_selected(user):
    algorithm, recent_task_id, seen_imgs = get_user_state(current_user)
    return isinstance(algorithm, UserSelected)

def get_num_entries_to_show(user):
    u = users_db.find_one({"user_id": user.get_id()})
    return u["num_entries_to_show"]

def get_fixed_sequence_categories(user):
    u = users_db.find_one({"user_id": user.get_id()})
    return u["fixed_sequence_categories"]

def get_fixed_task_parameters(user):
    u = users_db.find_one({"user_id": user.get_id()})
    return pickle.loads(u["fixed_task_parameters"])

def get_survey_parameters(user):
    u = users_db.find_one({"user_id": user.get_id()})
    return pickle.loads(u["survey_parameters"])

def resolve_manual_attention_checks_for_fixed_task_parameters(task_params, img_path):
    attention_checks = []
    if img_path.startswith('static/images/'):
        img_path = img_path[len('static/images/'):]
    for attention_check in task_params.attention_checks:
        if attention_check['type'] == 'manual':
            matching_entries = attention_check_db.find({'img_path': img_path})
            attention_checks.extend([dict(type='manual', question=x['question'], answer=x['answer'])
                                          for x in matching_entries])
        else:
            attention_checks.append(attention_check)
    task_params.attention_checks = attention_checks
    return task_params

def is_instance_of_bandit_algorithm(algorithm):
    return (isinstance(algorithm, UCB) or
            isinstance(algorithm, EpsilonGreedy) or
            isinstance(algorithm, ExploreThenCommit) or
            isinstance(algorithm, TS))

def validate_mturk_status(mturk_id):
    base = os.path.dirname(os.path.abspath(__file__))
    aws_config = ConfigObj(os.path.join(base, 'app', '.aws/config'))
    credentials = ConfigObj(os.path.join(base, 'app', '.aws/credentials'))
    hit_ids = (aws_config['hit_id'] if isinstance(aws_config['hit_id'], list) else [aws_config['hit_id']])
    qualtrics_code = aws_config['qualtrics_code']
    aws_access_key_id = credentials['aws_access_key_id']
    aws_secret_access_key = credentials['aws_secret_access_key']
    # This functionality is based off of the script found at:
    #     https://github.com/aws-samples/mturk-code-samples/blob/master/Python/RetrieveAndApproveHitSample.py
    use_hits_in_live = False  # Change this if using live instance.
    environments = {
        "live": {
            "endpoint": "https://mturk-requester.us-east-1.amazonaws.com",
            "preview": "https://www.mturk.com/mturk/preview",
            "manage": "https://requester.mturk.com/mturk/manageHITs",
        },
        "sandbox": {
            "endpoint": "https://mturk-requester-sandbox.us-east-1.amazonaws.com",
            "preview": "https://workersandbox.mturk.com/mturk/preview",
            "manage": "https://requestersandbox.mturk.com/mturk/manageHITs",
        },
    }
    mturk_environment = (environments["live"] if use_hits_in_live
                         else environments["sandbox"])
    session = boto3.Session(aws_access_key_id=aws_access_key_id,
                            aws_secret_access_key=aws_secret_access_key)
    client = session.client(
        service_name='mturk',
        region_name='us-east-1',
        endpoint_url=mturk_environment['endpoint'],
    )

    def get_assignments_for_hit(hit_id):
        hit = client.get_hit(HITId=hit_id)
        print('Hit {} status: {}'.format(hit_id, hit['HIT']['HITStatus']))
        response = client.list_assignments_for_hit(
            HITId=hit_id,
            AssignmentStatuses=['Submitted', 'Approved'],
            MaxResults=100
        )
        assignments = response['Assignments']
        pagination_token = response.get('NextToken', '')
        while pagination_token:
            response = client.list_assignments_for_hit(
                HITId=hit_id,
                AssignmentStatuses=['Submitted', 'Approved'],
                NextToken=pagination_token,
                MaxResults=100
            )
            assignments += response['Assignments']
            pagination_token = response.get('NextToken', '')
        return assignments
    assignments = []
    for hit_id in hit_ids:
        print('Querying MTurk API for hit_id %s' % hit_id)
        assignments += get_assignments_for_hit(hit_id)
    # Check if there is a matching user in Assignments and if their submitted
    # Qualtrics code matches that specified in the config file.
    for assignment in assignments:
        if mturk_id == assignment['WorkerId']:
            answer_xml = parseString(assignment['Answer'])
            # the answer is an xml document. we pull out the value of the first
            # //QuestionFormAnswers/Answer/FreeText
            answer = answer_xml.getElementsByTagName('FreeText')[0]
            # See https://stackoverflow.com/questions/317413
            user_submitted_code = " ".join(t.nodeValue for t in answer.childNodes if t.nodeType == t.TEXT_NODE)
            if qualtrics_code == user_submitted_code:
                if assignment['AssignmentStatus'] == 'Submitted':
                    client.approve_assignment(AssignmentId=assignment['AssignmentId'],
                                              OverrideRejection=False)
                return MTurkApprovalStatus.Approved
            else:
                return MTurkApprovalStatus.IncorrectQualtricsCode
    return MTurkApprovalStatus.MTurkIDNotFound

if __name__ == "__main__":
    opt = docopt(__doc__, version="version 0.1")

    # Setup logging
    logging.config.fileConfig("logging.ini", disable_existing_loggers=False)
    logger = logging.getLogger(__name__)

    # Setup DB
    #logger.info("DB path: {}".format(opt["--db"]))
    logger.info("DB path: {}".format("../data/"))
    # db = TinyDB(opt["--db"])
    client = MongoClient('localhost', 27017)
    mdb = client.newsent_database
    print(client, mdb)
    #logger.info("Counter path: {}".format(opt["--counter"]))
    logger.info("Counter path: {}".format("../data/"))
    #counter = TinyDB(opt['--counter'])
    #counter = client.counter_database

    # Start app
    app.run(debug=opt['--debug'],
            host='0.0.0.0',
            port=int(opt["--port"]),
            extra_files=["./app/static/js/index.js",
                         "./app/static/css/index.css"])
