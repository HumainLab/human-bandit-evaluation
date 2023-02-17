# Human Bandit Evaluation Platform

This is the web interface and database backend for studying how recommendations affect user comic preferences.

The comics used for our experiements are under `human_bandit_evaluation/app/static/images` and the comic interaction results are in an exported MongoDB database under `human_bandit_evaluation/database/mdb`.

TODO: Add a License.

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

To run this in a production setting, set up an Apache web server with the included virtualenv. TODO: More details will be provided in the future.

### Saving and restoring databases to/from backups

To export the `user` or `responses` databases to a backup directory, run the `mongodump` command as follows.
```bash
mongodump --db=<either users or responses> --out=<output directory>
```

To create a backup, run the `mongorestore` command similarly below.
```bash
mongorestore --db=<either users or responses> --dir=<output directory>
```

If necessary, a CRON job can be used to make periodic backups. For instance, an hourly backup can be initiated with the following command that creates backup directories with names such as `Sun Jan 17 09:46:02 UTC 2021`. To run it, copy the tab into the list of cron jobs with `crontab -e`.
```bash
0 * * * * 'mongodump --db=<either users or responses> --out="<backups directory>/`date`"' >/dev/null 2>&1
```

The data from the database can also be exported to a CSV using the following command.
```bash
mongoexport --host localhost --db <either users or responses> --collection <either users for responses> --type csv --out <output path> --fields <output fields>
```

