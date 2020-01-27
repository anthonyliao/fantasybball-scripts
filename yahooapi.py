import base64
import json
import logging
from functools import wraps

import requests
import xmltodict
import sqlite3
import datetime


def renew_token(client_id, client_secret, refresh_token):
    encoded_auth = base64.b64encode(
        f'{client_id}:{client_secret}'.encode('utf-8')).decode('utf-8')
    headers = {
        'Authorization': f'Basic {encoded_auth}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    params = {
        'grant_type': 'refresh_token',
        'redirect_url': 'oob',
        'refresh_token': refresh_token
    }
    resp = requests.post(
        'https://api.login.yahoo.com/oauth2/get_token', data=params, headers=headers)
    if resp.status_code != 200:
        raise Exception(f'unable to get new token:{resp.text}')
    resp_json = resp.json()
    return resp_json['access_token']


def roster(team_id, access_token):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    url = f'https://fantasysports.yahooapis.com/fantasy/v2/team/{team_id}/roster'
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception(resp.text)
    resp_data = xmltodict.parse(resp.text)
    # logging.info(f'resp_data:{json.dumps(resp_data)}')
    # logging.info(resp_data['fantasy_content']['team'])
    players = resp_data['fantasy_content']['team']['roster']['players']['player']
    return [(x['player_id'], x['name']['full']) for x in players]


def matchups(team_id, access_token):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    url = f'https://fantasysports.yahooapis.com/fantasy/v2/team/{team_id}/matchups'
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception(resp.text)
    resp_data = xmltodict.parse(resp.text)
    # logging.info(f'resp_data:{json.dumps(resp_data)}')
    # logging.info(resp_data['fantasy_content']['team'])
    # return resp_data['fantasy_content']['team']
    return resp_data['fantasy_content']['team']['matchups']


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)5s: %(message)s')
    logging.info('start')
    sqlite_db = 'data.db'
    sqlite_con = sqlite3.connect(sqlite_db)
    sqlite_con.set_trace_callback(logging.debug)
    sqlite_con.row_factory = sqlite3.Row

    with open('api-info.private', 'r') as f:
        data = json.loads(''.join(f.readlines()))
        team_id = data['team_id']

    with open('token.private', 'r') as f:
        data = json.loads(''.join(f.readlines()))
        access_token = data['access_token']
        logging.info(access_token)

    r = roster(team_id, access_token)
    m = matchups(team_id, access_token)
    active_matches = [x for x in m['matchup'] if x['status'] != 'postevent']
    # logging.info(json.dumps(active_matches))
    for match in active_matches:
        week = match['week']
        if week != "15":
            continue

        week_start = match['week_start']
        week_end = match['week_end']

        opponent = next(
            x for x in match['teams']['team'] if 'is_owned_by_current_login' not in x)
        opponent_id = opponent['team_key']
        opponent_name = opponent['name']
        logging.info(f'week:{week}, opponent:{opponent_name},{opponent_id}')
        logging.info(f'my roster:{r}')
        roster_ids = ','.join([f'"{x[0]}"' for x in r])
        with sqlite_con:
            cur = sqlite_con.cursor()
            cur.execute(f'select sum(case when fga = 0 then 0 else 1 end) as games, sum(fgm), sum(fga), sum(ftm), sum(fta), sum(ptm), sum(pts), sum(reb), sum(ast), sum(stl), sum(blk), sum(tov) from projections where playdate between ? and ? and yahoo_id in ({roster_ids})',
                        [datetime.date.today(), week_end])
            d = cur.fetchone()
            # logging.info(type(d))
            for key in d.keys():
                logging.info(f'{key}: {d[key]}')
        opponent_roster = roster(opponent_id, access_token)
        logging.info(f'opponent roster:{opponent_roster}')
        opponent_roster_ids = ','.join([f'"{x[0]}"' for x in opponent_roster])
        with sqlite_con:
            cur = sqlite_con.cursor()
            cur.execute(f'select sum(case when fga = 0 then 0 else 1 end) as games, sum(fgm), sum(fga), sum(ftm), sum(fta), sum(ptm), sum(pts), sum(reb), sum(ast), sum(stl), sum(blk), sum(tov) from projections where playdate between ? and ? and yahoo_id in ({opponent_roster_ids})',
                        [datetime.date.today(), week_end])
            d = cur.fetchone()
            # logging.info(type(d))
            for key in d.keys():
                logging.info(f'{key}: {d[key]}')
    logging.info('end')
