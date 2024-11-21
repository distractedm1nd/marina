import sqlite3
from contextlib import contextmanager

class DatabaseConnection:
    def __init__(self, database_path: str = 'team_management.db'):
        self.database_path = database_path
        self.setup_database()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.database_path)
        try:
            yield conn
        finally:
            conn.close()

    def setup_database(self):
        """Create necessary database tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Create teams table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS teams (
                    team_name TEXT PRIMARY KEY
                )
            ''')

            # Create team_members table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS team_members (
                    username TEXT,
                    team_name TEXT,
                    FOREIGN KEY (team_name) REFERENCES teams(team_name),
                    PRIMARY KEY (username, team_name)
                )
            ''')

            # Create chat_teams table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chat_teams (
                    chat_id INTEGER,
                    team_name TEXT,
                    FOREIGN KEY (team_name) REFERENCES teams(team_name),
                    PRIMARY KEY (chat_id, team_name)
                )
            ''')

            conn.commit()
