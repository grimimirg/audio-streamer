import logging
import os
from dotenv import load_dotenv

# Load environment variables
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
env_file = os.path.join(root_dir, '.env')
load_dotenv(env_file)

# Get debug flag from environment
DEBUG_MODE = os.getenv('AUDIO_STREAMER_DEBUG', 'False').lower() in ('true', '1', 'yes', 'on')


class Logger:
    """Centralized logging wrapper that controls output based on AUDIO_STREAMER_DEBUG flag.
    
    All logging calls in the application should use this class instead of the standard
    logging module. Logs will only be output when AUDIO_STREAMER_DEBUG is set to True.
    """
    
    _logger = logging.getLogger(__name__)
    
    @classmethod
    def setup(cls):
        """Configure the logger if debug mode is enabled."""
        if DEBUG_MODE:
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            cls._logger.setLevel(logging.DEBUG)
        else:
            # Disable all logging when debug mode is off
            cls._logger.setLevel(logging.CRITICAL)
            # Add a null handler to prevent warnings
            cls._logger.addHandler(logging.NullHandler())
    
    @classmethod
    def debug(cls, message):
        """Log debug message (only if DEBUG is enabled)."""
        if DEBUG_MODE:
            cls._logger.debug(message)
    
    @classmethod
    def info(cls, message):
        """Log info message (only if DEBUG is enabled)."""
        if DEBUG_MODE:
            cls._logger.info(message)
    
    @classmethod
    def warning(cls, message):
        """Log warning message (only if DEBUG is enabled)."""
        if DEBUG_MODE:
            cls._logger.warning(message)
    
    @classmethod
    def error(cls, message):
        """Log error message (only if DEBUG is enabled)."""
        if DEBUG_MODE:
            cls._logger.error(message)
    
    @classmethod
    def critical(cls, message):
        """Log critical message (only if DEBUG is enabled)."""
        if DEBUG_MODE:
            cls._logger.critical(message)


# Initialize logger on import
Logger.setup()
