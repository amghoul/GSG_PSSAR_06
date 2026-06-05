import os
import sqlite3
import logging
import pandas as pd

log = logging.getLogger(__name__)
num_spaces = len("Q01 answer -->")

# Step 0: Create Schema
def create_schema(conn: sqlite3.Connection) -> None:
    """
    We need to create and normalize 3 tables out of the csv data:
    Players, Openings, Games
    
    Define all three tables with explicit types, PRIMARY KEYs,
    FOREIGN KEYs, NOT NULL constraints, and CHECK constraints.

    Why explicit CREATE TABLE instead of letting to_sql() infer?
    - to_sql() creates columns with no constraints whatsoever
    - FK relationships would exist in comments only, not enforced
    - CHECK constraints (winner IN (...), turns >= 1) would be absent
    - NOT NULL would not be set on any column
    - Column types would be SQLite affinity guesses, not intentional choices

    Insertion order matters:
      players and openings must exist before games,
      because games has FK references to both.
    """

    # Drop in reverse FK dependency order so re-runs are clean
    conn.execute("DROP TABLE IF EXISTS games")
    conn.execute("DROP TABLE IF EXISTS openings")
    conn.execute("DROP TABLE IF EXISTS players")


    # Players: one raw per uniqu player. 
    conn.execute("""
        CREATE TABLE players (
            username     TEXT    PRIMARY KEY NOT NULL,
            last_rating  INTEGER NOT NULL,
            total_games  INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Openings: one row per unique opening code.
    conn.execute("""
        CREATE TABLE openings (
            opening_code      TEXT PRIMARY KEY NOT NULL,
            opening_shortname TEXT NOT NULL,
            opening_fullname  TEXT NOT NULL
        )
    """)

    # Games: The core table 
    # White_id and Black_id are foreign keys to players.username
    # Opening_code is a foreign key to openings.opening_code
    # I'm gonna keep the ratings even though in normalzation we can driv them from players. 
    # This is a delibrate de-normalization for analytical convenience.
    conn.execute("""
        CREATE TABLE games (
            game_id        INTEGER PRIMARY KEY NOT NULL,
            white_id       TEXT    NOT NULL
                               REFERENCES players(username),
            black_id       TEXT    NOT NULL
                               REFERENCES players(username),
            winner         TEXT    NOT NULL
                               CHECK(winner IN ('White', 'Black', 'Draw')),
            victory_status TEXT    NOT NULL,
            turns          INTEGER NOT NULL
                               CHECK(turns >= 1),
            time_increment TEXT    NOT NULL,
            rated          INTEGER NOT NULL
                               CHECK(rated IN (0, 1)),
            opening_code   TEXT    NOT NULL
                               REFERENCES openings(opening_code),
            white_rating   INTEGER NOT NULL,
            black_rating   INTEGER NOT NULL
        )
    """)
    
    
    log.info("Schema created: players, openings, games (with FK + CHECK constraints)")


# Step 1: Build Database
def build_tables(conn: sqlite3.Connection, chess: pd.DataFrame) -> None:
    """
    Prepare DataFrames and load them into the pre-defined schema.

    Why to_sql() with if_exists='append' after CREATE TABLE?
    - 'replace' would drop and recreate the table, losing all constraints
    - 'append' inserts rows into the table we already defined
    - This is the correct pattern: define schema explicitly, load data separately

    Insertion order: players → openings → games
    (games has FK references to both; they must exist first)
    """

    # Players: one raw per uniqu player. 
    white = chess[["white_id", "white_rating"]].rename(
        columns={"white_id": "username", "white_rating": "rating"}
    )
    black = chess[["black_id", "black_rating"]].rename(
        columns={"black_id": "username", "black_rating": "rating"}
    )
    players_df = (
        pd.concat([white, black])
        .groupby("username")["rating"]
        .last()
        .reset_index()
        .rename(columns={"rating": "last_rating"})
    )
    # Total games is how many time did they appear as white/black
    white_counts = chess["white_id"].value_counts().rename("w")
    black_counts = chess["black_id"].value_counts().rename("b")
    players_df["total_games"] = (
        players_df["username"]
       .map(white_counts.add(black_counts, fill_value=0))
        .astype(int)
    ) 

    # Turn players into sql table
    players_df.to_sql("players", conn, if_exists="append", index=False)

    log.info(f"Players table: {len(players_df)} rows have been added.")

    # Openings: one row per unique opening code.
    openings_df = (
        chess[["opening_code", "opening_shortname", "opening_fullname"]]
        .drop_duplicates("opening_code")
        .reset_index(drop=True)
    )
    openings_df.to_sql("openings", conn, if_exists="append", index=False)
    log.info(f"Openings table: {len(openings_df)} rows have been added.")

    # Games: The core table 
    # White_id and Black_id are foreign keys to players.username
    # Opening_code is a foreign key to openings.opening_code
    # I'm gonna keep the ratings even though in normalzation we can driv them from players. 
    # This is a delibrate de-normalization for analytical convenience.
    
    games_df = chess[[
        "game_id", "white_id", "black_id", "winner", "victory_status", "turns", "time_increment", 
        "rated", "white_rating", "black_rating", "opening_code",
    ]].copy()
    games_df.to_sql("games", conn, if_exists="append", index=False)
    log.info(f"Games table: {len(games_df)} rows have been added.")

    # Indexes for faster queries on FK columns sice they are a common target for join\where clauses.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_games_white    ON games(white_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_games_black    ON games(black_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_games_opening  ON games(opening_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_games_winner   ON games(winner)")
    log.info("Indexes created on games(white_id, black_id, opening_code, winner)")


def verify_schema(conn: sqlite3.Connection) -> None:
    """
    Assert expected row counts AND confirm FK/CHECK constraints are present.
    Reads the CREATE TABLE SQL from sqlite_master and checks for key phrases.
    """
    # Row counts
    for table, expected in [("players", 15635), ("openings", 365), ("games", 20058)]:
        actual = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert actual == expected, f"Expected {expected} rows in {table}, but got {actual}."
        log.info(f"✅ Verified {table} table: {actual} rows.")

    # Constraint verification — read the stored DDL from sqlite_master
    ddl_rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    ddl = {name: sql for name, sql in ddl_rows}

    # players: must have PRIMARY KEY
    assert "PRIMARY KEY" in ddl["players"], "players: missing PRIMARY KEY"

    # openings: must have PRIMARY KEY
    assert "PRIMARY KEY" in ddl["openings"], "openings: missing PRIMARY KEY"

    # games: must have FKs and CHECK constraints
    assert "REFERENCES players" in ddl["games"],  "games: missing FK to players"
    assert "REFERENCES openings" in ddl["games"], "games: missing FK to openings"
    assert "CHECK" in ddl["games"],               "games: missing CHECK constraints"
    assert "winner IN" in ddl["games"],            "games: missing winner CHECK"
    assert "turns >= 1" in ddl["games"],           "games: missing turns CHECK"

    log.info("✓ Schema constraints verified: PKs, FKs, CHECK all present")

    # Verify FK enforcement is active
    fk_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk_status == 1, "PRAGMA foreign_keys is OFF — FKs will not be enforced"
    log.info("✓ PRAGMA foreign_keys = ON confirmed")

def query(conn: sqlite3.Connection, sql: str) -> pd.DataFrame:
    """Convenience wrapper: SQL → DataFrame."""
    return pd.read_sql(sql, conn)

########
  
def result_foramt(df: pd.DataFrame, q_number: int, output_message: str="")-> None:
    log.info(f"Q{q_number} answer -->")
    match q_number:
        case 1:
            log.info(f"{' ' * num_spaces} {output_message} {df['total_games'].iloc[0]} ")
            log.info(f"{' ' * num_spaces}The number of rated games is: {df['rated_games'].iloc[0]}")
        case _: 
            df_string = df.to_string(index=False)
            log.info(f"{' ' * num_spaces} {output_message}")
            for line in df_string.splitlines():
                log.info(f"{' ' * num_spaces}{line}")
        
def q1(conn: sqlite3.Connection,q_number: int)-> None:
    # Q01 answer -->
    # The total games in the database is: 20058 
    # The number of rated games is: 16155
    sql= """
        SELECT COUNT(*) AS total_games,
        SUM(rated) AS rated_games
        FROM games;
        """
    df = query(conn, sql)
    output_message= "The total games in the database is: "
    result_foramt(df,q_number,output_message)

def q2(conn: sqlite3.Connection,q_number: int)-> None:
    ######### Q2
    # Q02 answer --> The victory_status distinct values and their counts:
    #                victory_status  victory_count
    #                       Resign          11147
    #                   Out of Time           1680
    #                          Mate           6325
    #                         Draw            906
    sql= """
    SELECT 
        victory_status, 
        COUNT(*) AS victory_count
    FROM games
    GROUP BY victory_status
    ORDER BY victory_status DESC;
        """
    df = query(conn, sql)
    output_message= "The victory_status distinct values and their counts:"
    result_foramt(df,q_number,output_message)
    
def q3(conn: sqlite3.Connection,q_number: int)-> None:
    # Q03 answer --> The 10 games with most turns are:
    #                game_id winner  turns
    #                  11555  White    349
    #                  13860  White    349
    #                  16387   Draw    259
    #                   4237   Draw    255
    #                  16646   Draw    226
    #                  15479   Draw    222
    #                  16944  Black    222
    #                   6777   Draw    221
    #                  13231  Black    218
    #                  13556   Draw    216
    sql= """
    SELECT 
        game_id, winner, turns
    FROM games
    ORDER BY turns DESC
    LIMIT 10;
        """
    df = query(conn, sql)
    output_message= "The 10 games with most turns are:"
    result_foramt(df,q_number,output_message)

def q4(conn: sqlite3.Connection,q_number: int)-> None:
    # Q04 answer --> The Win rate for ech winnder category (White, Black, and Draw):
    #               winner  total_wins  win_rate
    #                White       10001     49.86
    #                Black        9107     45.40
    #                 Draw         950      4.74
    sql= """
    SELECT 
        winner AS winner,
        COUNT(*) AS total_wins,
        ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM games), 2) AS win_rate
    FROM games
    GROUP BY winner
    ORDER BY win_rate DESC;
        """
    df = query(conn, sql)
    output_message= "The Win rate for ech winnder category (White, Black, and Draw):"
    result_foramt(df,q_number,output_message)

def q5(conn: sqlite3.Connection,q_number: int)-> None:
    # Q05 answer --> The average and maximum number of turn for each victory_Status:
    #               victory_status  average_turns  max_turns
    #                         Draw          83.78        259
    #                  Out of Time          72.74        349
    #                         Mate          65.42        222
    #                       Resign          53.91        218
    sql= """
        SELECT 
            victory_status,
            ROUND(AVG(turns), 2) AS average_turns,
            MAX(turns) AS max_turns
        FROM games
        GROUP BY victory_status
        ORDER BY average_turns DESC;
            """
    df = query(conn, sql)
    output_message= "The average and maximum number of turn for each victory_Status:"
    result_foramt(df,q_number,output_message)

def q6(conn: sqlite3.Connection,q_number: int)-> None:
    # Q06 answer --> The 5 opening_Codes appers frequlently that are larger than 500:
    #               opening_code  game_count
    #                        A00        1007
    #                        C00         844
    #                        D00         739
    #                        B01         716
    #                        C41         691
    sql= """
    SELECT 
        opening_code,
        COUNT(*) AS game_count
    FROM games
    GROUP BY opening_code
    HAVING game_count > 500
    ORDER BY game_count DESC
    LIMIT 5;
        """
    df = query(conn, sql)
    output_message= "The 5 opening_Codes appers frequlently that are larger than 500:"
    result_foramt(df,q_number,output_message)
    
def run_assignment(conn: sqlite3.Connection) -> None:
    """Stage 1 to 4 then Q1 to Q5"""
    # Make sure ti use the function query we built above! -Hend
    ##########Q1
    q_number = 1
    q1(conn,q_number)
    ##########Q2
    q_number +=1
    q2(conn,q_number)
    ##########Q3
    q_number +=1
    q3(conn,q_number)
    ########Q4
    q_number +=1
    q4(conn,q_number)
    ########Q5
    q_number +=1
    q5(conn,q_number)
    ########Q6
    q_number +=1
    q6(conn,q_number)

    conn.close()

#######
def main():
    print("This is for session 6: testing databases")

    # 1. Loadraw chess data
    chess = pd.read_csv(os.path.join("data", "raw", "chess_games.csv"))
    print(f"Loaded chess_games.csv: {chess.shape[0]} rows, {chess.shape[1]} columns.")

    # 2. Build database
    db_path = os.path.join("data", "processed", "chess.db")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints!! Don't forget this step, otherwise your FK constraints won't work.

    log.info("Creating schema with constraints...")
    create_schema(conn)

    log.info("Building database tables...")
    build_tables(conn, chess)

    verify_schema(conn)

    conn.commit()
    log.info(f"Database tables have been built. {os.path.getsize(db_path)/1024:.2f} KB" )

    # call the asignment function to run the queries
    run_assignment(conn)
    
    conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()

