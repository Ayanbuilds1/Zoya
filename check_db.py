import sqlite3

connection = sqlite3.connect("zoya.db")

tables = connection.execute(
    "SELECT name FROM sqlite_master "
    "WHERE type='table' "
    "ORDER BY name"
).fetchall()

print([table[0] for table in tables])

connection.close()