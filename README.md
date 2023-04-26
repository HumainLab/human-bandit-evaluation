# Human Bandit Evaluation Platform

This is the web interface and database backend for studying how recommendations affect user comic preferences.

The comics used for our experiements are under `human_bandit_evaluation/app/static/images` and the comic interaction results are in an exported MongoDB database under `human_bandit_evaluation/database/mdb`.

### Installation

First, install requirements
```bash
pip install -r requirements.txt
```

### Setup

The comics are included as part of the repository.

To populate the users database, use the `setup_dbs.py` script in the `preference_learning_interface` directory to generate a `users.json` file that contains randomly generated `username`, `password` and `survey_code`. Once this is done, configure each user's experiemtn by filling in the fields `algorithm`, `num_entries_to_show`, and `comics_per_entry`. Further users can be added afterwards by repeating this process.

We use [MongoDB](https://www.mongodb.com/blog/post/getting-started-with-python-and-mongodb) for storing users and their responses. By default, they are stored as Collections (equivalent to tables) in MongoDB databases `users`, `responses`. Both the databases are stored in the folder `data` inside the home folder.

### Deployment
To run the server locally, first enable the virtualenv by running the following command.
```bash
source preference_learning_interface/env/bin/activate
```

When run locally, the website is located at [here](http://localhost:8000/)
```bash
python server.py # add "-d" for debug mode 
```

To run this in a production setting, set up an Apache web server with the included virtualenv. TODO: More details will be provided in the near future.

### Configuring a study

Here, we include more details on how to configure a study, which includes factors such as the number of users/comics, the recommendation algorithm,and the end-of-study survey.
(The recommendation algorithms include bandit algorithms, fixed sequences, and self-selection.)
Configuring a study requires defining two JSON files, `users.json` and `global_task_config.json`.

`users.json` is a list of JSON dictionaries that have the following schema:
```
user_id: The ID of the user in the database. Must be unique and greater than 0.
username: The username of the user, typically auto-generated.
password: The password of the user, typically auto-generated.
survey_code: The survey code of the user for receiving payment after completing the study. Allowed to be unique for all users for additional security.
algorithm: The name of the algorithm for this user's study. One of ['ucb', 'ts', 'etc', 'eps', 'fixed_sequence', 'user_selected'].
fixed_task_parameters (optional): If the algorithm is set to 'fixed_task_sequence', define a list of JSON dictionaries with schema: 
                                      category: The category of comic to be recommended.
                                      sample_method: The method of obtaining the instance of the category.
                                      image_path: If provided, will use a specific instance of the category at the given path.
survey_parameters (optional): If provided, overwrites the 'survey_parameters' in the global task config JSON.
                                  survey_type: One of ['memory', 'rating_memory', 'pairwise_memory'].
```
This is used to populate the `users` database.

`global_task_config.json` is a JSON with the following schema:
```
comics_per_entry: The number of comics to show for each evaluation item. [default: 1]
num_entries_to_show: The number of total comics to show during the study. [default: 50]
num_survey_entries_to_show: The number of post-study survey entries to show. [default: 6]
fixed_task_parameters: A single instance or a list of JSON dictionaries with schema:
                           category: The category of comic to be recommended.
                           sample_method: The method of obtaining the instance of the category.
                           image_path: If provided, will use a specific instance of the category at the given path.
survey_parameters: A single instance or a list of JSON dictionaries with schema:
                       survey_type: One of ['memory', 'rating_memory', 'pairwise_memory'].
```
The `global_task_config.json' is supplied alongside `users.json` when configuring the study. Any matching fields (including the number of entries to show if one should so choose) will be overwritten by the value of the field in the user JSON.

### Setting up a Mechanical Turk experiment.
The system is designed to ensure that each MTurk worker can only receive at most one account. This is done by setting up two tasks. First, they must complete a pre-study MTurk task that involves filling out a Qualtrics survey and enter the completion code into the website at endpoint `/mturk_authenticate`. If the completion code is correct and their MTurk ID is found among the submitted pre-study MTurk task responses, the worker will be given the credentials to complete the study. Second, the user should join the primary study MTurk task. They can then complete the study using the login credentials that were given in the first task. Once they have completed the study, they will be given a unique MTurk completion code that they must enter into the Mturk interface which will be validated by the experimenter.

In order to properly query the MTurk API for the task and response information, key-value `configobj` configuration files must be defined at paths `.aws/config` and `.aws/credentials`. The `config` file should contain a comma-separated list of HIT IDs under `hit_id` and the Qualtrics completion code under `qualtrics_code`. The `credentials` file should contain the `aws_access_key_id` and `aws_secret_access_key`. The default region name is `us-east-1` in the code, which can be configured as necessary.

### Saving and restoring databases to/from backups

To export the `user` or `responses` databases to a backup directory, run the `mongodump` command as follows.
```bash
mongodump --db=<either users or responses> --out=<output directory>
```

To create a backup, run the `mongorestore` command similarly below.
```bash
mongorestore --db=<either users or responses> --dir=<output directory>
```

The data from the database can also be exported to a CSV using the following command.
```bash
mongoexport --host localhost --db <either users or responses> --collection <either users for responses> --type csv --out <output path> --fields <output fields>
```

