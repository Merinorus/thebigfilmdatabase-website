"""Connection to the database."""

import sqlite3

from app.config import settings

# Cache the database in RAM for faster access
db_file_connection = sqlite3.connect(settings.DB_SQLITE_FILEPATH)
db_ram_connection = sqlite3.connect(":memory:")
db_file_connection.backup(db_ram_connection)
db_file_connection.close()

total_count = len(db_ram_connection.cursor().execute("SELECT * FROM films").fetchall())
