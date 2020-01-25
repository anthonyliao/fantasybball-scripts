import datetime
import logging
import random
import re
import sqlite3
import time

import pandas
import requests
from bs4 import BeautifulSoup
import yahooapi
import json

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)5s: %(message)s')
logging.info('start')


with open('api-info.private', 'r') as f:
    data = json.loads(''.join(f.readlines()))
    client_id = data['client_id']
    client_secret = data['client_secret']
    logging.info(client_id)
    logging.info(client_secret)

with open('token.private', 'r') as f:
    data = json.loads(''.join(f.readlines()))
    refresh_token = data['refresh_token']
    logging.info(refresh_token)

with open('token.private', 'w') as f:
    access_token = yahooapi.renew_token(
        client_id, client_secret, refresh_token)
    data['access_token'] = access_token
    f.writelines(json.dumps(data, indent=2, sort_keys=True))
