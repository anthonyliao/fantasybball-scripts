import logging
import datetime
import requests
import xmltodict
import json
import sqlite3


def teams(league_id, access_token):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    url = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{league_id}/teams/roster'
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception(resp.text)
    resp_data = xmltodict.parse(resp.text)

    # logging.info(f'resp_data:{json.dumps(resp_data)}')
    # with open('teams.json', 'w') as f:
    #     f.writelines(json.dumps(resp_data, sort_keys=True, indent=4))
    teams_roster = {}
    for team in resp_data['fantasy_content']['league']['teams']['team']:
        players = [x['player_id'] for x in team['roster']['players']['player']]
        team_name = team['name']
        team_key = team['team_key']
        teams_roster[team_key] = (team_name, players)
    return teams_roster


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


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)5s: %(message)s')
    logging.info('start')

    with open('api-info.private', 'r') as f:
        data = json.loads(''.join(f.readlines()))
        league_id = data['league_id']

    with open('token.private', 'r') as f:
        data = json.loads(''.join(f.readlines()))
        access_token = data['access_token']
        logging.info(access_token)

    teams_roster = teams(league_id, access_token)

    sqlite_db = 'data.db'
    try:
        sqlite_con = sqlite3.connect(sqlite_db)
        sqlite_con.set_trace_callback(logging.debug)

        with sqlite_con:
            for team_id, value in teams_roster.items():
                name, players = value
                logging.info(team_id)
                logging.info(name)
                logging.info(players)

                sql = 'DELETE FROM rosters WHERE team_id = ?'
                sqlite_con.execute(sql, (team_id,))
                for player_id in players:
                    sql = 'INSERT INTO rosters (league_id, team_id, team_name, yahoo_id) VALUES (?, ?, ?, ?)'
                    sqlite_con.execute(
                        sql, (league_id, team_id, name, player_id))

    finally:
        sqlite_con.close()
