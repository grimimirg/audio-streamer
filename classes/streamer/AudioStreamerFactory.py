from classes.streamer.streamers.CardAudioStreamer import CardAudioStreamer
from classes.streamer.streamers.MicrophoneAudioStreamer import MicrophoneAudioStreamer
from classes.streamer.streamers.LiquidMusicStreamer import LiquidMusicStreamer
from utilities.Logger import Logger


class AudioStreamerFactory:
    """Factory class for creating audio streamer instances.
    
    This factory encapsulates the creation logic for different audio streamer types,
    providing a clean interface for instantiating the appropriate streamer based on
    the selected input method.
    """

    _STREAMER_MAP = {
        'microphone': MicrophoneAudioStreamer,
        'interface': CardAudioStreamer,
        'liquid_music': LiquidMusicStreamer
    }

    @classmethod
    def create(cls, input_method: str):
        """Create an audio streamer instance based on the input method.
        
        Args:
            input_method: The selected input method. Valid values are:
                         - 'microphone': Built-in or USB microphone
                         - 'interface': External sound card or line-in
                         - 'liquid_music': File-based music playback
        
        Returns:
            An instance of the appropriate audio streamer class.
        
        Raises:
            ValueError: If the input method is not recognized.
        
        Example:
            >>> streamer = AudioStreamerFactory.create('microphone')
            >>> isinstance(streamer, MicrophoneAudioStreamer)
            True
        """
        streamer_class = cls._STREAMER_MAP.get(input_method)
        
        if streamer_class is None:
            Logger.warning(f"Unknown input method: {input_method}, defaulting to microphone")
            return MicrophoneAudioStreamer()
        
        streamer = streamer_class()
        Logger.info(f"Created {streamer_class.__name__} for {input_method} input")
        return streamer

    @classmethod
    def get_available_methods(cls) -> list:
        """Get a list of all available input methods.
        
        Returns:
            list: A list of available input method keys.
        
        Example:
            >>> AudioStreamerFactory.get_available_methods()
            ['microphone', 'interface', 'liquid_music']
        """
        return list(cls._STREAMER_MAP.keys())

    @classmethod
    def is_method_valid(cls, input_method: str) -> bool:
        """Check if an input method is valid.
        
        Args:
            input_method: The input method to validate.
        
        Returns:
            bool: True if the input method is valid, False otherwise.
        
        Example:
            >>> AudioStreamerFactory.is_method_valid('microphone')
            True
            >>> AudioStreamerFactory.is_method_valid('invalid')
            False
        """
        return input_method in cls._STREAMER_MAP

    @classmethod
    def get_method_description(cls, input_method: str) -> str:
        """Get a human-readable description for an input method.
        
        Args:
            input_method: The input method to get description for.
        
        Returns:
            str: A description of the input method, or 'Unknown' if not found.
        
        Example:
            >>> AudioStreamerFactory.get_method_description('microphone')
            'Built-in or USB microphone'
        """
        descriptions = {
            'microphone': 'Built-in or USB microphone',
            'interface': 'External sound card or line-in',
            'liquid_music': 'File-based music playback'
        }
        return descriptions.get(input_method, 'Unknown')
