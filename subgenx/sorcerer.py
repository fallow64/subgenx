import os
import yt_dlp
from abc import ABC, abstractmethod

from subgenx.util import Config, is_file_whisper_compatible, is_youtube_url


class Source(ABC):
    @abstractmethod
    def can_handle(self, location: str, config: Config) -> bool:
        """Check if the source can handle the given location."""
        pass

    @abstractmethod
    def handle(self, location: str, config: Config) -> str | list[str] | None:
        """
        Handle the location and return the path to the audio file.

        If the source returns a string, it is a single audio file.

        If it returns a list, it a list of further locations to source.

        If it returns None, it means the source could not handle the location.
        """
        pass


class BaseSource(Source):
    def can_handle(self, location: str, config: Config) -> bool:
        return is_file_whisper_compatible(location)

    def handle(self, location: str, config: Config) -> str:
        # If the location is an audio file, return it as is
        return location


class DirectorySource(Source):
    def can_handle(self, location: str, config: Config) -> bool:
        return os.path.isdir(location)

    def handle(self, location: str, config: Config) -> str | list[str] | None:
        # Recursively find all audio files in the directory
        audio_files = []
        for root, _, files in os.walk(location):
            for file in files:
                full_path = os.path.join(root, file)
                # If the file is compatible with Whisper, add it to the list
                if is_file_whisper_compatible(full_path):
                    audio_files.append(full_path)

        # If there is only one audio file, return it as a string
        # Otherwise return the list of audio files (empty list if none found)
        return audio_files[0] if len(audio_files) == 1 else audio_files


class YoutubeSource(Source):
    def can_handle(self, location: str, config: Config) -> bool:
        return is_youtube_url(location)

    def handle(self, location: str, config: Config) -> str | None:
        print(f"Downloading audio from YouTube: {location}")
        
        ydl_opts = {
            "outtmpl": "%(title)s.%(ext)s",
            "windowsfilenames": True,  # Ensure Windows compatibility
            "restrictfilenames": True,  # Restrict filenames to only ASCII characters
            "paths": {"home": config.download_dir},
        }
        
        if config.include_video:
            # If the user wants to download the video instead of just the audio
            ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        else:            
            # Only download the audio
            ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
            ydl_opts["extractaudio"] = True  # Download only the audio

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(location, download=True)
            audio_file = ydl.prepare_filename(info)
            return audio_file


class Sorcerer:
    def __init__(self, config: Config):
        self.config = config
        self.sources = [BaseSource(),
                        YoutubeSource(),
                        DirectorySource()]

    def handle_location(self, location: str) -> list[str] | None:
        results = []
        location_queue = [location]

        while len(location_queue) > 0:
            current_location = location_queue.pop(0)
            result = self._handle_single_location(current_location)

            if result is not None:
                if isinstance(result, str):
                    results.append(result)
                elif isinstance(result, list):
                    location_queue.extend(result)

        return results if results else None

    def _handle_single_location(self, location: str) -> str | list[str] | None:
        for source in self.sources:
            if source.can_handle(location, self.config):
                # location_result can be a single audio file path, a list of further locations, or None
                location_result = source.handle(location, self.config)

                if location_result is None:
                    continue

                # location_result can be a string (single file) or a list (multiple loations to check further)
                return location_result

        # No source could handle the location
        return None
