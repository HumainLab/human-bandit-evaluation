import argparse
import json
# import pandas as pd
import pickle
import random
import time
import uuid
from pymongo import MongoClient
from algorithms import FixedSequence, EpsilonGreedy, ExploreThenCommit, TS, UserSelected, UCB
from util import Task

client = MongoClient('localhost', 27017)
users_db = client.users.users
responses_db = client.responses.responses
survey_db = client.survey.survey
attention_check_db = client.attention_check.attention_check

def clear_users_db():
    print("Clearing users database with %d entries" % users_db.count())
    users_db.remove()

def clear_responses_db():
    print("Clearing responses database with %d entries" % responses_db.count())
    responses_db.remove()

def clear_survey_db():
    print("Clearing survey database with %d entries" % survey_db.count())
    survey_db.remove()

def clear_attention_check_db():
    print("Clearing attention check database with %d entries" % attention_check_db.count())
    attention_check_db.remove()

def generate_users_json(args):
    num_users = users_db.count()
    generated_entries = []
    for i in range(int(args.num_users_to_generate)):
        username = uuid.uuid4()
        while len(list(users_db.find({'username': username}))) > 0:
            username = uuid.uuid4()
        password = uuid.uuid4().int
        generated_entries.append({'user_id': num_users + 1 + i,
                                  'username': str(username),
                                  'password': str(uuid.uuid4().int),
                                  'survey_code': str(uuid.uuid4().int)})
    with open(args.generate_users_output_file, 'w') as f:
        f.write(json.dumps(generated_entries, indent=2))

def generate_attention_check():
    a, b = random.randint(2, 10), random.randint(2, 10)
    if random.randint(0, 1):
        question = "What is %d + %d?" % (a, b)
        answer = str(a + b)
    else:
        question = "What is %d - %d?" % (a, b)
        answer = str(a - b)
    return dict(type='math', question=question, answer=answer)

def load_user_entries_into_db(args):
    users_json = json.loads(open(args.path_to_users_file, 'r').read())
    global_config_json = json.loads(open(args.path_to_global_config, 'r').read()) if args.path_to_global_config else dict()
    for user_json in users_json:
        if user_json['algorithm'] == 'user_selected':
            algorithm = UserSelected()
        elif user_json['algorithm'] == 'ucb':
            algorithm = UCB(num_arms=5)
        elif user_json['algorithm'] == 'etc':
            algorithm = ExploreThenCommit(num_arms=5)
        elif user_json['algorithm'] == 'greedy':
            algorithm = EpsilonGreedy(num_arms=5)
        elif user_json['algorithm'] == 'ts':
            algorithm = TS(num_arms=5)
        elif user_json['algorithm'] == 'fixed_sequence':
            algorithm = FixedSequence()

        num_entries_to_show = user_json.get('num_entries_to_show',
                                            global_config_json['num_entries_to_show'])
        num_survey_entries_to_show = user_json.get('num_survey_entries_to_show',
                                                   global_config_json['num_survey_entries_to_show'])
        comics_per_entry = user_json.get('comics_per_entry',
                                         global_config_json['comics_per_entry'])
        global_task_parameters = global_config_json.get('fixed_task_parameters', dict())
        if 'fixed_task_parameters' in user_json:
            # Override potential global_task_parameters with task-specific parameters.
            fixed_task_parameters = [Task(**({**global_task_parameters, **x}))
                                     for x in user_json['fixed_task_parameters']]
        else:
            # If not specified, then the fixed_task_parameters are just those
            # specified in the global config.
            fixed_task_parameters = [Task(**global_task_parameters)
                                     for _ in range(num_entries_to_show)]
        if len(fixed_task_parameters) != num_entries_to_show:
            raise Exception("length of fixed_task_parameters must be the same as num_entries_to_show")

        # Generate or read in attention checks.
        for i in range(num_entries_to_show):
            attention_checks = []
            if args.generate_math_attention_check:
                math_attention_check = generate_attention_check()
                attention_checks.append(math_attention_check)
            if args.manual_attention_check:
                attention_checks.append(dict(type='manual'))
            fixed_task_parameters[i].attention_checks = attention_checks

        # Survey parameters.
        survey_parameters = [global_config_json['survey_parameters']
                             for _ in range(num_survey_entries_to_show)]
        if 'survey_parameters' in user_json:
            if len(user_json['survey_parameters']) != num_survey_entries_to_show:
                raise Exception("length of survey_parameters must be the same as num_survey_entries_to_show")
            survey_parameters = [{**global_sp, **user_sp} for global_sp, user_sp in
                                 zip(survey_parameters, user_json['survey_parameters'])]

        users_db.insert_one({
            'user_id': user_json['user_id'],
            'username': user_json['username'],
            'password': user_json['password'],
            'survey_code': user_json['survey_code'],
            'num_entries_to_show': user_json.get('num_entries_to_show',
                                                 global_config_json['num_entries_to_show']),
            'num_survey_entries_to_show': user_json.get('num_survey_entries_to_show',
                                                        global_config_json['num_survey_entries_to_show']),
            'comics_per_entry': user_json.get('comics_per_entry',
                                              global_config_json['comics_per_entry']),
            'mturk_id': None,
            'algorithm': pickle.dumps(algorithm),
            'fixed_task_parameters': pickle.dumps(fixed_task_parameters),
            'survey_parameters': pickle.dumps(survey_parameters)})

def upload_manual_attention_checks(args):
    df = pd.read_csv(args.manual_attention_check)
    for _, row in df.iterrows():
        attention_check_db.insert_one({
            'img_path': row['img_path'],
            'question': row['question'].strip(),
            'answer': row['answer']})

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--path_to_users_file', default='')
    parser.add_argument('--path_to_global_config', default='')
    parser.add_argument('--num_users_to_generate', default=0)
    parser.add_argument('--generate_users_output_file', default='')
    parser.add_argument('--generate_users_json', action='store_true')
    parser.add_argument('--generate_math_attention_check', action='store_true')
    parser.add_argument('--manual_attention_check', default='')
    parser.add_argument('--clear_users_db', action='store_true')
    parser.add_argument('--clear_responses_db', action='store_true')
    parser.add_argument('--clear_survey_db', action='store_true')
    parser.add_argument('--clear_attention_check_db', action='store_true')
    args = parser.parse_args()

    if args.clear_users_db:
        clear_users_db()

    if args.clear_responses_db:
        clear_responses_db()

    if args.clear_survey_db:
        clear_survey_db()

    if args.clear_attention_check_db:
        clear_attention_check_db()

    if args.generate_users_json:
        generate_users_json(args)

    if args.manual_attention_check:
        upload_manual_attention_checks(args)

    if len(args.path_to_users_file) > 0:
        load_user_entries_into_db(args)
