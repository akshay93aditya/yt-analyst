import os
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv

load_dotenv ()
API_KEY = os.getenv('youtube_api_key') # Replace 'YOUR_API_KEY' with the API key you obtained earlier
youtube = build('youtube', 'v3', developerKey=API_KEY)
