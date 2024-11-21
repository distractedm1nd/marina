from typing import List, Dict, Union
import logging
import sqlite3
from contextlib import contextmanager

ServiceResponse = Dict[str, Union[bool, str, List[int]]]

class TeamManagementService:
    def __init__(self, database_path: str = 'team_management.db'):
        self.db = DatabaseConnection(database_path)
        self.logger = logging.getLogger(__name__)

    def create_team(self, team_name: str) -> ServiceResponse:
        """Create a new team"""
        team_name = team_name.lower()
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO teams (team_name) VALUES (?)", (team_name,))
                conn.commit()
            return {
                "success": True,
                "message": f"Team {team_name!r} created successfully"
            }
        except sqlite3.IntegrityError:
            return {
                "success": False,
                "message": f"Team {team_name!r} already exists"
            }
        except Exception as e:
            self.logger.error(f"Error creating team: {str(e)}")
            return {
                "success": False,
                "message": "Internal server error"
            }

    def add_member_to_team(self, username: str, team_name: str) -> ServiceResponse:
        """Add a member to a team"""
        username = username.replace("@", "")
        team_name = team_name.lower()

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Check if team exists
                cursor.execute("SELECT team_name FROM teams WHERE team_name = ?", (team_name,))
                if not cursor.fetchone():
                    return {
                        "success": False,
                        "message": f"Team {team_name!r} doesn't exist"
                    }

                cursor.execute(
                    "INSERT INTO team_members (username, team_name) VALUES (?, ?)",
                    (username, team_name)
                )
                conn.commit()

                # Get all chats where the team is present
                cursor.execute(
                    "SELECT chat_id FROM chat_teams WHERE team_name = ?",
                    (team_name,)
                )
                chats = cursor.fetchall()

                return {
                    "success": True,
                    "message": f"Added user {username!r} to team {team_name!r}",
                    "chats_to_add": [chat[0] for chat in chats]
                }

        except sqlite3.IntegrityError:
            return {
                "success": False,
                "message": f"User {username!r} is already in team {team_name!r}"
            }
        except Exception as e:
            self.logger.error(f"Error adding member to team: {str(e)}")
            return {
                "success": False,
                "message": "Internal server error"
            }

    def remove_member_from_team(self, username: str, team_name: str) -> ServiceResponse:
        """Remove a member from a team"""
        username = username.replace("@", "")
        team_name = team_name.lower()

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "DELETE FROM team_members WHERE username = ? AND team_name = ?",
                    (username, team_name)
                )

                if cursor.rowcount == 0:
                    return {
                        "success": False,
                        "message": f"User {username!r} is not in team {team_name!r}"
                    }

                conn.commit()

                # Get all chats where the team is present
                cursor.execute(
                    "SELECT chat_id FROM chat_teams WHERE team_name = ?",
                    (team_name,)
                )
                chats = cursor.fetchall()

                return {
                    "success": True,
                    "message": f"Removed user {username!r} from team {team_name!r}",
                    "chats_to_remove": [chat[0] for chat in chats]
                }

        except Exception as e:
            self.logger.error(f"Error removing member from team: {str(e)}")
            return {
                "success": False,
                "message": "Internal server error"
            }

    def add_team_to_chat(self, chat_id: int, team_name: str) -> ServiceResponse:
        """Add a team to a chat"""
        team_name = team_name.lower()

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Check if team exists
                cursor.execute("SELECT team_name FROM teams WHERE team_name = ?", (team_name,))
                if not cursor.fetchone():
                    return {
                        "success": False,
                        "message": f"Team {team_name!r} doesn't exist"
                    }

                # Add team to chat
                cursor.execute(
                    "INSERT INTO chat_teams (chat_id, team_name) VALUES (?, ?)",
                    (chat_id, team_name)
                )
                conn.commit()

                # Get all team members
                cursor.execute(
                    "SELECT username FROM team_members WHERE team_name = ?",
                    (team_name,)
                )
                members = cursor.fetchall()

                return {
                    "success": True,
                    "message": f"Added team {team_name!r} to chat",
                    "members_to_add": [member[0] for member in members]
                }

        except sqlite3.IntegrityError:
            return {
                "success": False,
                "message": f"Team {team_name!r} is already in this chat"
            }
        except Exception as e:
            self.logger.error(f"Error adding team to chat: {str(e)}")
            return {
                "success": False,
                "message": "Internal server error"
            }

    def offboard_user(self, username: str) -> ServiceResponse:
        """Remove a user from all teams and associated chats"""
        username = username.replace("@", "")

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # Get all chats the user needs to be removed from
                cursor.execute(
                    """
                    SELECT DISTINCT chat_id
                    FROM chat_teams
                    WHERE team_name IN (
                        SELECT team_name
                        FROM team_members
                        WHERE username = ?
                    )
                    """,
                    (username,)
                )
                chats = cursor.fetchall()

                # Remove user from all teams
                cursor.execute(
                    "DELETE FROM team_members WHERE username = ?",
                    (username,)
                )

                if cursor.rowcount == 0:
                    return {
                        "success": False,
                        "message": f"User {username!r} is not in any teams"
                    }

                conn.commit()

                return {
                    "success": True,
                    "message": f"User {username!r} has been offboarded",
                    "chats_to_remove": [chat[0] for chat in chats]
                }

        except Exception as e:
            self.logger.error(f"Error offboarding user: {str(e)}")
            return {
                "success": False,
                "message": "Internal server error"
            }

    def get_team_members(self, team_name: str) -> List[str]:
        """Get all members of a team"""
        team_name = team_name.lower()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT username FROM team_members WHERE team_name = ?",
                (team_name,)
            )
            return [row[0] for row in cursor.fetchall()]

    def get_user_teams(self, username: str) -> List[str]:
        """Get all teams a user belongs to"""
        username = username.replace("@", "")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT team_name FROM team_members WHERE username = ?",
                (username,)
            )
            return [row[0] for row in cursor.fetchall()]

    def get_chat_teams(self, chat_id: int) -> List[str]:
        """Get all teams in a chat"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT team_name FROM chat_teams WHERE chat_id = ?",
                (chat_id,)
            )
            return [row[0] for row in cursor.fetchall()]

    def get_teams(self) -> List[str]:
        """Get all teams"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT team_name FROM teams ORDER BY team_name"
            )
            return [row[0] for row in cursor.fetchall()]

    def get_team_members(self, team_name: str) -> List[str]:
        """Get all members of a team"""
        team_name = team_name.lower()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT username FROM team_members WHERE team_name = ? ORDER BY username",
                (team_name,)
            )
            return [row[0] for row in cursor.fetchall()]

class DatabaseConnection:
    def __init__(self, database_path: str):
        self.database_path = database_path
        self.setup_database()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.database_path)
        try:
            yield conn
        finally:
            conn.close()

    def setup_database(self) -> None:
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
