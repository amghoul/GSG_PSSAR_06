# Chess Database — Extended Schema Documentation (Table Format)

This repository houses a clean, normalized relational database built from raw chess game logs (`chess_games.csv`). The pipeline splits flat data across three specialized tables—**players**, **openings**, and **games**—enforcing strict validation constraints via SQLite to guarantee structural and relational integrity.

---

## 1. Architectural Overview & Normalization Strategy
Using an explicit `CREATE TABLE` structure instead of automated inference (such as Pandas `to_sql(if_exists='replace')`) is crucial. Automated inferences leave columns with zero constraints, treat primary/foreign relationships merely as abstract notes rather than functional bounds, fail to set mandatory fields as `NOT NULL`, and bypass `CHECK` verification parameters completely.

---

## 2. Comprehensive Schema Reference

### Table A: players
Maintains a definitive list of unique participants across the platform.

| Column Name | Data Type | Primary/Foreign Key | Constraints | Description / Business Rules |
| :--- | :--- | :--- | :--- | :--- |
| **username** | TEXT | **PRIMARY KEY** | NOT NULL | The unique identifier / handle of the chess player. |
| **last_rating** | INTEGER | *None* | NOT NULL | The most recent Elo rating recorded for the player across their latest processed match. |
| **total_games** | INTEGER | *None* | NOT NULL, DEFAULT 0 | The cumulative count of matches played (combining White and Black appearances). |

---

### Table B: openings
Acts as a standardized reference lookup for distinct tactical openings.

| Column Name | Data Type | Primary/Foreign Key | Constraints | Description / Business Rules |
| :--- | :--- | :--- | :--- | :--- |
| **opening_code** | TEXT | **PRIMARY KEY** | NOT NULL | The standardized ECO classification code (e.g., C00, A00). |
| **opening_shortname** | TEXT | *None* | NOT NULL | The broad family categorization label (e.g., French Defense). |
| **opening_fullname** | TEXT | *None* | NOT NULL | The highly descriptive variation name (e.g., French Defense: King's Indian Attack). |

---

### Table C: games
The central transaction matrix recording the full profile of played matches.

| Column Name | Data Type | Primary/Foreign Key | Constraints | Description / Business Rules |
| :--- | :--- | :--- | :--- | :--- |
| **game_id** | INTEGER | **PRIMARY KEY** | NOT NULL | Unique transactional record key identifying each match. |
| **white_id** | TEXT | **FOREIGN KEY** | NOT NULL | Relational link identifying the player controlling the White pieces. References `players(username)`. |
| **black_id** | TEXT | **FOREIGN KEY** | NOT NULL | Relational link identifying the player controlling the Black pieces. References `players(username)`. |
| **winner** | TEXT | *None* | NOT NULL, CHECK | The resulting outcome of the match. CHECK ensures values are ('White', 'Black', 'Draw'). |
| **victory_status** | TEXT | *None* | NOT NULL | The operational conclusion mode (e.g., Mate, Resign, Draw, Out of Time). |
| **turns** | INTEGER | *None* | NOT NULL, CHECK | Total ply/move iterations completed during the confrontation. CHECK ensures `turns >= 1`. |
| **time_increment** | TEXT | *None* | NOT NULL | Time control configurations set up for the arena. |
| **rated** | INTEGER | *None* | NOT NULL, CHECK | Boolean indicator flag where 1 denotes official ladder matches and 0 casual ones. CHECK ensures `rated IN (0, 1)`. |
| **opening_code** | TEXT | **FOREIGN KEY** | NOT NULL | Relational link tracking the deployed tactical opener. References `openings(opening_code)`. |
| **white_rating** | INTEGER | *None* | NOT NULL | The precise Elo rating of the White player at the exact moment of this match. |
| **black_rating** | INTEGER | *None* | NOT NULL | The precise Elo rating of the Black player at the exact moment of this match. |

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