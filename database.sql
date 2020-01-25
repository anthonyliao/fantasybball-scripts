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