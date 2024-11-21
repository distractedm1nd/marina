from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.error import BadRequest
from service import TeamManagementService
import logging
from typing import NoReturn, Optional, Dict
import sqlite3

class TeamManagementBot:
    def __init__(self, token: str, service: TeamManagementService) -> None:
        self.token = token
        self.service = service
        self.logger = logging.getLogger(__name__)
        self.user_id_cache: Dict[str, int] = {}
        self.setup_user_cache()

    def setup_user_cache(self) -> None:
        """Setup user ID cache table"""
        with sqlite3.connect(self.service.db.database_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_ids (
                    username TEXT,
                    user_id INTEGER NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (username, user_id)
                )
            ''')
            conn.commit()

    async def cache_user_id(self, username: str, user_id: int) -> None:
        """Store user ID in cache"""
        if not username:  # Don't cache empty usernames
            return

        self.user_id_cache[username] = user_id
        with sqlite3.connect(self.service.db.database_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_ids (username, user_id)
                VALUES (?, ?)
            ''', (username, user_id))
            conn.commit()

    def get_cached_user_id(self, username: str) -> Optional[int]:
        """Get user ID from cache"""
        if username in self.user_id_cache:
            return self.user_id_cache[username]

        with sqlite3.connect(self.service.db.database_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM user_ids WHERE username = ?', (username,))
            result = cursor.fetchone()
            if result:
                self.user_id_cache[username] = result[0]
                return result[0]
        return None

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle any message to capture user information"""
        if update.effective_user and update.effective_user.username:
            await self.cache_user_id(
                update.effective_user.username.lower(),
                update.effective_user.id
            )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        if not update.effective_user or not update.effective_message:
            return

        if update.effective_user.username:
            await self.cache_user_id(
                update.effective_user.username.lower(),
                update.effective_user.id
            )

        welcome_message = """
Welcome to the Team Management Bot! 🤖

To get started:
1. Make me an admin in your group chats
2. Use these commands:

/create_team <team_name> - Create a new team
/add_to_team @username team_name - Add user to team
/remove_from_team @username team_name - Remove user from team
/add team_name - Add team to current chat
/offboard @username - Remove user from all teams
/list_teams - Show all teams
/list_members team_name - Show team members

For users to be added to teams, they should:
1. Start a chat with me (@your_bot_username)
2. Send me any message
        """
        await update.effective_message.reply_text(welcome_message)

    async def get_user_id(self, username: str, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
        """Get user ID through multiple methods"""
        clean_username = username.lstrip('@').lower()

        cached_id = self.get_cached_user_id(clean_username)
        if cached_id:
            return cached_id
        return None

    async def create_team(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /create_team command"""
        if not context.args or not update.effective_message:
            await update.effective_message.reply_text("Usage: /create_team <team_name>")
            return

        team_name = context.args[0].lower()
        result = self.service.create_team(team_name)
        await update.effective_message.reply_text(str(result["message"]))

    async def add_to_team(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /add_to_team command"""
        if not context.args or len(context.args) != 2 or not update.effective_message:
            await update.effective_message.reply_text("Usage: /add_to_team @username team_name")
            return

        username, team_name = context.args[0], context.args[1]
        clean_username = username.lstrip('@').lower()

        user_id = await self.get_user_id(username, context)
        if not user_id:
            await update.effective_message.reply_text(
                f"I don't know user {username} yet! Please ask them to:\n"
                f"1. Start a chat with me (@{context.bot.username})\n"
                f"2. Send me any message\n"
                f"Then try adding them to the team again."
            )
            return

        result = self.service.add_member_to_team(clean_username, team_name)

        if result["success"]:
            chats_to_add = result.get("chats_to_add", [])
            for chat_id in chats_to_add:
                try:
                    chat = await context.bot.get_chat(chat_id)
                    if chat.username:  # Public chat
                        chat_link = f"https://t.me/{chat.username}"
                    else:  # Private chat
                        invite = await chat.create_invite_link()
                        chat_link = invite.invite_link

                    try:
                        await context.bot.send_message(
                            user_id,
                            f"You've been added to team {team_name}! Join the chat here: {chat_link}"
                        )
                    except Exception as e:
                        self.logger.error(f"Couldn't send direct message to user: {str(e)}")
                        if update.effective_message:
                            await update.effective_message.reply_text(
                                f"Please share this link with {username}: {chat_link}"
                            )
                except Exception as e:
                    self.logger.error(f"Failed to create invite for chat {chat_id!r}: {str(e)}")

        if update.effective_message:
            await update.effective_message.reply_text(str(result["message"]))

    async def remove_from_team(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /remove_from_team command"""
        if not context.args or len(context.args) != 2 or not update.effective_message:
            await update.effective_message.reply_text("Usage: /remove_from_team @username team_name")
            return

        username, team_name = context.args[0], context.args[1]
        clean_username = username.lstrip('@').lower()

        user_id = await self.get_user_id(username, context)
        if not user_id:
            await update.effective_message.reply_text(
                f"I don't know user {username}! They need to start a chat with me first."
            )
            return

        result = self.service.remove_member_from_team(clean_username, team_name)

        if result["success"]:
            chats_to_remove = result.get("chats_to_remove", [])
            for chat_id in chats_to_remove:
                try:
                    await context.bot.ban_chat_member(
                        chat_id=chat_id,
                        user_id=user_id
                    )
                    await context.bot.unban_chat_member(
                        chat_id=chat_id,
                        user_id=user_id
                    )
                except Exception as e:
                    self.logger.error(f"Failed to remove user from chat {chat_id!r}: {str(e)}")

        await update.effective_message.reply_text(str(result["message"]))

    async def add_team_to_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /add command"""
        if not context.args or not update.effective_chat or not update.effective_message:
            await update.effective_message.reply_text("Usage: /add team_name")
            return

        team_name = context.args[0].lower()
        result = self.service.add_team_to_chat(update.effective_chat.id, team_name)

        if result["success"]:
            members_to_add = result.get("members_to_add", [])
            failed_members = []

            try:
                chat = await context.bot.get_chat(update.effective_chat.id)
                if chat.username:
                    chat_link = f"https://t.me/{chat.username}"
                else:
                    invite = await chat.create_invite_link()
                    chat_link = invite.invite_link

                for username in members_to_add:
                    user_id = await self.get_user_id(username, context)
                    if user_id:
                        try:
                            await context.bot.send_message(
                                user_id,
                                f"Team {team_name} has been added to a new chat! Join here: {chat_link}"
                            )
                        except Exception as e:
                            failed_members.append(username)
                            self.logger.error(f"Failed to notify user {username}: {str(e)}")
                    else:
                        failed_members.append(username)

                response = str(result["message"])
                if failed_members:
                    response += f"\nCouldn't notify these users: {', '.join(failed_members)}"
                response += f"\n\nTeam members can join using this link: {chat_link}"

                await update.effective_message.reply_text(response)
            except Exception as e:
                self.logger.error(f"Failed to create invite link: {str(e)}")
                await update.effective_message.reply_text(str(result["message"]))

    async def offboard_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /offboard command"""
        if not context.args or not update.effective_message:
            await update.effective_message.reply_text("Usage: /offboard @username")
            return

        username = context.args[0]
        clean_username = username.lstrip('@').lower()

        user_id = await self.get_user_id(username, context)
        if not user_id:
            await update.effective_message.reply_text(
                f"I don't know user {username}! They need to start a chat with me first."
            )
            return

        result = self.service.offboard_user(clean_username)

        if result["success"]:
            chats_to_remove = result.get("chats_to_remove", [])
            failed_chats = []

            for chat_id in chats_to_remove:
                try:
                    await context.bot.ban_chat_member(
                        chat_id=chat_id,
                        user_id=user_id
                    )
                    await context.bot.unban_chat_member(
                        chat_id=chat_id,
                        user_id=user_id
                    )
                except Exception as e:
                    failed_chats.append(str(chat_id))
                    self.logger.error(f"Failed to remove user from chat {chat_id!r}: {str(e)}")

            response = str(result["message"])
            if failed_chats:
                response += f"\nFailed to remove from some chats: {', '.join(failed_chats)}"

            await update.effective_message.reply_text(response)

    async def list_teams(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /list_teams command"""
        if not update.effective_message:
            return

        teams = self.service.get_teams()
        if not teams:
            await update.effective_message.reply_text("No teams exist yet!")
            return

        team_list = "\n".join(f"• {team}" for team in teams)
        await update.effective_message.reply_text(f"Teams:\n{team_list}")

    async def list_members(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /list_members command"""
        if not context.args or not update.effective_message:
            await update.effective_message.reply_text("Usage: /list_members team_name")
            return

        team_name = context.args[0].lower()
        members = self.service.get_team_members(team_name)

        if not members:
            await update.effective_message.reply_text(f"Team '{team_name}' has no members!")
            return

        member_list = "\n".join(f"• @{member}" for member in members)
        await update.effective_message.reply_text(f"Members of team '{team_name}':\n{member_list}")

    def run(self) -> NoReturn:
        """Start the bot"""
        application = Application.builder().token(self.token).build()

        # Add command handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("create_team", self.create_team))
        application.add_handler(CommandHandler("add_to_team", self.add_to_team))
        application.add_handler(CommandHandler("remove_from_team", self.remove_from_team))
        application.add_handler(CommandHandler("add", self.add_team_to_chat))
        application.add_handler(CommandHandler("offboard", self.offboard_user))
        application.add_handler(CommandHandler("list_teams", self.list_teams))
        application.add_handler(CommandHandler("list_members", self.list_members))

        # Add message handler to capture user information
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Start the bot
        application.run_polling()
