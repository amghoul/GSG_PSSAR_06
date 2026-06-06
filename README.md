# Chess Database — Extended Schema Documentation

This repository houses a clean, normalized relational database built from raw chess game logs (`chess_games.csv`). The pipeline splits flat data across three specialized tables—**players**, **openings**, and **games**—enforcing strict validation constraints via SQLite to guarantee structural and relational integrity.

---

## 1. Architectural Overview & Normalization Strategy
Using an explicit `CREATE TABLE` structure instead of automated inference (such as Pandas `to_sql(if_exists='replace')`) is crucial. Automated inferences leave columns with zero constraints, treat primary/foreign relationships merely as abstract notes rather than functional bounds, fail to set mandatory fields as `NOT NULL`, and bypass `CHECK` verification parameters completely.

---

## 2. Comprehensive Schema Reference

### Table A: players
Maintains a definitive list of unique participants across the platform.

* **username**
    * *Type:* TEXT
    * *Constraints:* PRIMARY KEY, NOT NULL
    * *Description:* The unique identifier / handle of the chess player.
* **last_rating**
    * *Type:* INTEGER
    * *Constraints:* NOT NULL
    * *Description:* The most recent Elo rating recorded for the player across their latest processed match.
* **total_games**
    * *Type:* INTEGER
    * *Constraints:* NOT NULL, DEFAULT 0
    * *Description:* The cumulative count of matches played (combining White and Black appearances).

### Table B: openings
Acts as a standardized reference lookup for distinct tactical openings.

* **opening_code**
    * *Type:* TEXT
    * *Constraints:* PRIMARY KEY, NOT NULL
    * *Description:* The standardized ECO classification code (e.g., C00, A00).
* **opening_shortname**
    * *Type:* TEXT
    * *Constraints:* NOT NULL
    * *Description:* The broad family categorization label (e.g., French Defense).
* **opening_fullname**
    * *Type:* TEXT
    * *Constraints:* NOT NULL
    * *Description:* The highly descriptive variation name (e.g., French Defense: King's Indian Attack).

### Table C: games
The central transaction matrix recording the full profile of played matches.

* **game_id**
    * *Type:* INTEGER
    * *Constraints:* PRIMARY KEY, NOT NULL
    * *Description:* Unique transactional record key identifying each match.
* **white_id**
    * *Type:* TEXT
    * *Constraints:* NOT NULL, FOREIGN KEY REFERENCES players(username)
    * *Description:* Relational link identifying the player controlling the White pieces.
* **black_id**
    * *Type:* TEXT
    * *Constraints:* NOT NULL, FOREIGN KEY REFERENCES players(username)
    * *Description:* Relational link identifying the player controlling the Black pieces.
* **winner**
    * *Type:* TEXT
    * *Constraints:* NOT NULL, CHECK(winner IN ('White', 'Black', 'Draw'))
    * *Description:* The resulting outcome of the match.
* **victory_status**
    * *Type:* TEXT
    * *Constraints:* NOT NULL
    * *Description:* The operational conclusion mode (e.g., Mate, Resign, Draw, Out of Time).
* **turns**
    * *Type:* INTEGER
    * *Constraints:* NOT NULL, CHECK(turns >= 1)
    * *Description:* Total ply/move iterations completed during the confrontation.
* **time_increment**
    * *Type:* TEXT
    * *Constraints:* NOT NULL
    * *Description:* Time control configurations set up for the arena.
* **rated**
    * *Type:* INTEGER
    * *Constraints:* NOT NULL, CHECK(rated IN (0, 1))
    * *Description:* Boolean indicator flag where 1 denotes official ladder matches and 0 casual ones.
* **opening_code**
    * *Type:* TEXT
    * *Constraints:* NOT NULL, FOREIGN KEY REFERENCES openings(opening_code)
    * *Description:* Relational link tracking the deployed tactical opener.
* **white_rating**
    * *Type:* INTEGER
    * *Constraints:* NOT NULL
    * *Description:* The precise Elo rating of the White player at the exact moment of this match.
* **black_rating**
    * *Type:* INTEGER
    * *Constraints:* NOT NULL
    * *Description:* The precise Elo rating of the Black player at the exact moment of this match.

---

## 3. Relational Constraints & Integrity Verification

### Foreign Key (FK) Justification
To ensure absolute stability, relational entries depend completely on foundational parent dimensions. These constraints prevent orphaned records or data corruption from invalid text configurations:

* **games(white_id) REFERENCES players(username)**: Dictates that a user account must exist within the `players` table before they can be listed as the White competitor in any match.
* **games(black_id) REFERENCES players(username)**: Dictates that a user account must exist within the `players` table before they can be listed as the Black competitor in any match.
* **games(opening_code) REFERENCES openings(opening_code)**: Ensures that every logged match references a registered ECO opening code from the `openings` master database, preventing invalid taxonomy labels.

*Note: Foreign Key enforcement is explicitly verified during database initialization using the mandatory runtime directive:* `PRAGMA foreign_keys = ON;`

---

## 4. Operational Defenses: CHECK Constraints Explained
`CHECK` constraints act as the database's internal security perimeter. They validate row data before write operations are finalized, discarding anomalous entries at the engine layer:

* **CHECK(winner IN ('White', 'Black', 'Draw'))**
    Protects the dataset from structural corruptions, clerical typing typos, or case mismatch anomalies (such as writing `white`, `WHITE`, `W`, or `player1`). It restricts input strictly to this uniform tuple of valid strings.
* **CHECK(turns >= 1)**
    Protects against logic failures, corrupt logs, or broken match records. A valid chess match cannot exist with zero moves, meaning any broken record attempting to pass a negative value or zero is rejected.
* **CHECK(rated IN (0, 1))**
    Maintains clean binary storage for matching structures. It restricts data ingestion strictly to valid boolean flags (`0` or `1`), avoiding arbitrary notation drift.

---

## 5. Query Optimization & Index Matrix
High-frequency filtration parameters and join keys are accelerated using explicit indexes to replace intensive full table scans (`SCAN`) with targeted binary pointer searches (`SEARCH`):

* **idx_games_white** on `games(white_id)`: Optimizes queries analyzing personal white metrics, profile lookup tracking, and user win ratios.
* **idx_games_black** on `games(black_id)`: Accelerates targeted historical lookups for matches played using the black pieces.
* **idx_games_opening** on `games(opening_code)`: Speeds up complex relational joins between the core ledger and taxonomy definitions.
* **idx_games_winner** on `games(winner)`: Accelerates high-frequency tactical aggregate calculations (such as general draw metrics and victory margins).