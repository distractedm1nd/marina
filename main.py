import logging
import os
from telegram_bot import TeamManagementBot
from service import TeamManagementService
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main() -> None:
    # Load environment variables
    load_dotenv()

    # Get bot token from environment variable
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        logger.error("No bot token found! Please set TELEGRAM_BOT_TOKEN environment variable")
        return

    try:
        # Initialize service and bot
        service = TeamManagementService(database_path='team_management.db')
        bot = TeamManagementBot(token=bot_token, service=service)

        logger.info("Starting bot...")
        bot.run()

    except Exception as e:
        logger.error(f"Error running bot: {str(e)}")
        raise

if __name__ == '__main__':
    main()
