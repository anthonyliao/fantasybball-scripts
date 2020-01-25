import argparse
import datetime
import json
import logging
import random
import re
import sqlite3
import time

import pandas
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)5s: %(message)s')

parser = argparse.ArgumentParser(
    description='pulls rotowire projections from yahoo')
parser.add_argument(
    '-s', type=str, help='YYYY-MM-DD start date to pulling stats, default to today')
parser.add_argument('-l', type=int,
                    help='number of days to pull from start date, default to 1')
args = parser.parse_args()

logging.info('start')

begin_time = int(time.time())
playdate_start = datetime.datetime.strptime(
    args.s, '%Y-%m-%d').date() if args.s else datetime.date.today()
playdate_duration = args.l or 1
logging.info(f'playdate_start: {playdate_start}')
logging.info(f'playdate_duration: {playdate_duration}')

with open('projection-settings.private', 'r') as f:
    data = json.loads(''.join(f.readlines()))
    cookie = data['cookie']
    logging.info(f'cookie:{cookie}')
    league_id = data['league_id']
    logging.info(f'league_id:{league_id}')
    sqlite_db = data['database']
    logging.info(f'sqlite_db:{sqlite_db}')

logging.info(f'sqlite3.version:{sqlite3.version}')
logging.info(f'sqlite3.sqlite_version:{sqlite3.sqlite_version}')
sqlite_con = sqlite3.connect(sqlite_db)

try:
    playdates = [playdate_start + datetime.timedelta(days=x)
                 for x in range(0, playdate_duration)]
    for playdate in playdates:
        logging.info(f'playdate:{playdate}')
        max_results_per_page = 25
        for offset in range(0, 1000, max_results_per_page):
            # Sort by PTS desc
            url = f'https://basketball.fantasysports.yahoo.com/nba/{league_id}/players?sort=AR&sdir=1&status=ALL&pos=P&stat1=S_P&date={playdate}&count={offset}&jsenabled=1'
            headers = {'Cookie': cookie}
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200:
                raise Exception(
                    f'failed getting projections: {resp.status_code}, {resp.text}')
            html = resp.text
            soup = BeautifulSoup(html, 'html.parser')
            # Find table containing player data
            table = soup.find('div', id='players-table').find('table')
            # If tbody is missing, means there's no more results
            if not table.tbody:
                print(f'no more results on offset:{offset}')
                break
            # Remove the top column header of the table, keep the bottom column header
            table.thead.find('tr', class_='First').decompose()
            # Remove the sort arrow
            table.thead.find('span', class_='arrow').decompose()
            # Fix player names
            for x in table.tbody.find_all('td', class_='player'):
                player_tag = x.find('div', class_='ysf-player-name').find('a')
                link = player_tag['href']
                name = player_tag.string
                x.clear()
                x.string = f'{name}|{link}'
            table_html = table.prettify()
            table_df = pandas.read_html(table_html)
            assert len(table_df) == 1
            table_df = table_df[0]
            table_df['DATE'] = playdate
            table_df['LAST_UPDATE'] = begin_time
            table_df[['PLAYER', 'URL']] = table_df['Players'].str.split(
                '|', expand=True)
            table_df['YAHOO_ID'] = table_df['URL'].apply(lambda x: re.match(
                r'https://sports.yahoo.com/nba/players/([0-9]*)', x).group(1)).astype(int)

            def cast_float_func(x):
                return [0.0 if y == '-' else float(y) for y in x]

            table_df[['FGM', 'FGA']] = table_df['FGM  /  A*'].str.split(
                '/', expand=True).apply(cast_float_func)
            table_df[['FTM', 'FTA']] = table_df['FTM  /  A*'].str.split(
                '/', expand=True).apply(cast_float_func)
            # logging.info(table_df.dtypes)
            columns = ['DATE', 'PLAYER', 'YAHOO_ID', 'FGM', 'FGA', 'FTM', 'FTA',
                       '3PTM', 'PTS', 'REB', 'AST', 'ST', 'BLK', 'TO', 'LAST_UPDATE']
            # csv = table_df.loc[:, columns].to_csv(index=False,  header=True)
            # logging.info(csv)
            # break
            # for _, row in table_df.loc[:, columns].iterrows():
            #     logging.info(row['PLAYER'])

            with sqlite_con:
                for _, row in table_df.loc[:, columns].iterrows():
                    sql = """REPLACE INTO projections (playdate, player, yahoo_id, fgm, fga, ftm, fta, ptm, pts, reb, ast, stl, blk, tov, last_update)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    sqlite_con.execute(sql, [row[col] for col in columns])

            logging.info(f'offset:{offset}, fetched:{len(table_df)}')

            if len(table_df) < 25:
                print(f'last page:{offset}')
                break
            else:
                # Random 5-7 seconds between pages to Yahoo denying us access
                time.sleep(5.0 + (random.random() * 2.0))

        # 100-120 seconds between dates to Yahoo denying us access
        time.sleep(100.0 + (random.random() * 20.0))
finally:
    sqlite_con.close()

logging.info('end')
