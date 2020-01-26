CREATE TABLE projections (
    playdate text,
    player text,
    yahoo_id integer,
    fgm real,
    fga real,
    ftm real,
    fta real,
    ptm real,
    pts real,
    reb real,
    ast real,
    stl real,
    blk real,
    tov real,
    last_update integer
);

CREATE UNIQUE INDEX projections_id ON projections (playdate, yahoo_id);

CREATE TABLE rosters (
    league_id text,
    team_id text,
    team_name text,
    yahoo_id text
);