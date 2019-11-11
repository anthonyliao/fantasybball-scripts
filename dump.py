import time
import requests
import json
import base64
import xmltodict
from basketball_reference_web_scraper import client
from fuzzywuzzy import process
import csv
from functools import wraps
import subprocess
import shutil
import datetime
import getopt
import sys
import unidecode

"""
0 */3 * * * bash -c 'HOME=/home/ubuntu/; eval "$(ssh-agent -s)" && ssh-add /home/ubuntu/.ssh/somesshkey; source /home/ubuntu/code/fantasybball-scripts/.venv/bin/activate && pushd /home/ubuntu/code/fantasybball-scripts; git pull; python3 dump.py -u > dump.log 2>&1; deactivate; popd'
"""

opts, _ = getopt.getopt(sys.argv[1:], 'u')
upload = '-u' in [x for x, _ in opts]
print(f'upload:{upload}')

with open('api-info.private', 'r') as f:
    api_info = json.load(f)
    league_id = api_info['league_id']
    print(f'league_id:{league_id}')
    gist_id = api_info['gist']
    print(f'gist:{gist_id}')
    gist_location = api_info['gist_location']
    print(f'gist_location:{gist_location}')

def with_authorization(func):
    @wraps(func)
    def call(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            if 'token_expired' not in str(e):
                raise e
            with open('api-info.private', 'r') as f:
                api_info = json.load(f)
                client_id = api_info['client_id']
                client_secret = api_info['client_secret']
                print(f'client_id:{client_id}')
                print(f'client_secret:{client_secret}')
            print('renewing token')
            encoded_auth = base64.b64encode(f'{client_id}:{client_secret}'.encode('utf-8')).decode('utf-8')
            headers = { 
                'Authorization': f'Basic {encoded_auth}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            print(f'headers:{headers}')
            params = {
                'grant_type': 'refresh_token',
                'redirect_url': 'oob',
                'refresh_token': self.refresh
            }
            print(f'params:{params}')
            resp = requests.post('https://api.login.yahoo.com/oauth2/get_token', data=params, headers=headers)
            if resp.status_code != 200:
                raise Exception(f'unable to get new token:{resp.text}')
            resp_json = resp.json()
            with open('token.private', 'w') as f:
                f.write(json.dumps(resp_json, sort_keys=True, indent=4))
            self.access = resp_json['access_token']
            print(f'token renewed:{self.access}')
            return func(self, *args, **kwargs)
    return call

class YahooApiCaller():
    def __init__(self):
        with open('token.private', 'r') as f:
            token = json.load(f)
            self.access = token['access_token']
            self.refresh = token['refresh_token']
            print(f'access:{self.access}')
            print(f'refresh:{self.refresh}')

    @with_authorization
    def make_request(self, is_post, url):
        headers = {
            'Authorization': f'Bearer {self.access}'
        }
        resp = requests.post(url, headers=headers) if is_post else requests.get(url, headers=headers)
        if resp.status_code != 200:
            raise Exception(resp.text)
        return resp

    def teams(self, league_id):
        url = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{league_id}/standings'
        resp = self.make_request(False, url)
        if resp.status_code != 200:
            raise Exception(resp.text)
        data = xmltodict.parse(resp.text)
        for team in data['fantasy_content']['league']['standings']['teams']['team']:
            yield team['team_key'], team['name']

    def roster(self, team_id):
        url = f'https://fantasysports.yahooapis.com/fantasy/v2/team/{team_id}/roster/players'
        resp = self.make_request(False, url)
        if resp.status_code != 200:
            raise Exception(resp.text)
        data = xmltodict.parse(resp.text)
        for player in data['fantasy_content']['team']['roster']['players']['player']:
            yield player['player_key'], player['name']['full'], player

caller = YahooApiCaller()
print([x for x in caller.teams(league_id)])

player_owners = {}
player_statuses = {}
for team_id, team_name in caller.teams(league_id):
    for player_id, player_name, player_data in caller.roster(team_id):
        player_owners[player_name] = team_name
        player_statuses[player_name] = player_data['status'] if 'status' in player_data else ''

# print(player_owners.keys())

stats={}
bbref_totals = client.players_season_totals(season_end_year=2020)
for x in bbref_totals:
    x['name'] = unidecode.unidecode(x['name'])
    stats[x['name']] = x
bbref_adv = client.players_advanced_season_totals(season_end_year=2020)
for x in bbref_adv:
    x['name'] = unidecode.unidecode(x['name'])
    stats[x['name']].update(x)
bbref_adv_2019 = client.players_advanced_season_totals(season_end_year=2019)
for x in bbref_adv_2019:
    x['name'] = unidecode.unidecode(x['name'])
    if x['name'] in stats:
        for key, val in x.items():
            stats[x['name']][f'{key}_2019'] = val
print(f'bbref_totals:{len(stats)}')

print(stats.keys())

for x in stats.values():
    x['status'] = ''

for player_name, owner in player_owners.items():
    print(f'assigning {player_name}')
    if player_name in stats.keys():
        info = stats[player_name]
    else:
        match, _ = process.extractOne(player_name, stats.keys())
        info = stats[match]
    info['owner'] = owner
    info['status'] = player_statuses[player_name]
    
# print(next( y for y in stats.values()))

dump_file = 'gistfile1.txt'
print(f'writing to file: {dump_file}')

fieldnames = [
    'name',
    'age',
    'owner',
    'team',
    'player_efficiency_rating',
    'usage_percentage',
    'total_rebound_percentage',
    'three_point_attempt_rate',
    'assist_percentage',
    'steal_percentage',
    'block_percentage',
    'minutes_played',
    'games_played',
    'true_shooting_percentage',
    'assists',
    'steals',
    'blocks',
    'made_field_goals',
    'attempted_field_goals',
    'made_three_point_field_goals',
    'attempted_three_point_field_goals',
    'made_free_throws',
    'attempted_free_throws',
    'turnover_percentage',
    # 'win_shares',
    'box_plus_minus',
    # 'defensive_box_plus_minus',
    # 'defensive_rebound_percentage',
    # 'defensive_rebounds',
    # 'defensive_win_shares',
    'free_throw_attempt_rate',
    # 'games_started',
    # 'offensive_box_plus_minus',
    # 'offensive_rebound_percentage',
    # 'offensive_rebounds',
    # 'offensive_win_shares',
    # 'personal_fouls',
    'positions',
    # 'slug',
    'turnovers',
    # 'value_over_replacement_player',
    # 'win_shares_per_48_minutes',
    'status',
    'player_efficiency_rating_2019',
    'usage_percentage_2019',
    'total_rebound_percentage_2019',
    'three_point_attempt_rate_2019',
    'assist_percentage_2019',
    'steal_percentage_2019',
    'block_percentage_2019',
    'player_efficiency_rating_diff',
    'usage_percentage_diff',
    'total_rebound_percentage_diff',
    'three_point_attempt_rate_diff',
    'assist_percentage_diff',
    'steal_percentage_diff',
    'block_percentage_diff'
]

for x in stats.keys():
    player_stats = stats[x]
    for field in fieldnames:
        if f'{field}_2019' in fieldnames and f'{field}_2019' in player_stats:
            player_stats[f'{field}_diff'] = float(player_stats[field]) - float(player_stats[f'{field}_2019'])
            

with open(dump_file, 'w') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(sorted(stats.values(), key=lambda x: x['name']))

if upload:
    subprocess.run('git reset --hard origin/master', cwd=gist_location, check=True, shell=True)
    shutil.copy(dump_file, gist_location)
    comment = f'updated {datetime.datetime.utcnow().isoformat()}'
    proc = subprocess.run(f'git add {dump_file} && git commit -m "{comment}" && git push -v', cwd=gist_location, check=True, shell=True)

print('done')
