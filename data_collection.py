import os
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv
import statistics
import re
import openai

load_dotenv()

# Youtube API Auth
API_KEY = os.getenv('youtube_api_key')
youtube = build('youtube', 'v3', developerKey=API_KEY)

# OpenAI API Auth
openai.api_key = os.getenv('openai_api_key')


# fixing time formats from iso8601

def iso8601_duration_to_seconds(duration):
    # Extract hours, minutes, and seconds
    hours, minutes, seconds = 0, 0, 0
    hours_match = re.search(r'(\d+)H', duration)
    if hours_match:
        hours = int(hours_match.group(1))
    minutes_match = re.search(r'(\d+)M', duration)
    if minutes_match:
        minutes = int(minutes_match.group(1))
    seconds_match = re.search(r'(\d+)S', duration)
    if seconds_match:
        seconds = int(seconds_match.group(1))
    return hours * 3600 + minutes * 60 + seconds


def fetch_top_videos(query, max_results=100, order="viewCount"):
    search_response = youtube.search().list(
        q=query,
        type="video",
        order=order,
        part="id",
        maxResults=max_results
    ).execute()

    video_ids = [item["id"]["videoId"] for item in search_response["items"]]
    return video_ids


def fetch_video_details(video_ids):
    video_details_response = youtube.videos().list(
        id=','.join(video_ids),
        part="id,snippet,statistics,contentDetails"
    ).execute()

    videos = video_details_response["items"]
    return videos


def calculate_statistics(videos):
    views = [int(video['statistics']['viewCount'])
             for video in videos if 'viewCount' in video['statistics']]
    likes = [int(video['statistics']['likeCount'])
             for video in videos if 'likeCount' in video['statistics']]
    dislikes = [int(video['statistics']['dislikeCount'])
                for video in videos if 'dislikeCount' in video['statistics']]
    comments = [int(video['statistics']['commentCount'])
                for video in videos if 'commentCount' in video['statistics']]

    stats = {
        "average_views": sum(views) / len(views) if views else "No data",
        "median_views": statistics.median(views) if views else "No data",
        "average_likes": sum(likes) / len(likes) if likes else "No data",
        "median_likes": statistics.median(likes) if likes else "No data",
        "average_dislikes": sum(dislikes) / len(dislikes) if dislikes else "No data",
        "median_dislikes": statistics.median(dislikes) if dislikes else "No data",
        "average_comments": sum(comments) / len(comments) if comments else "No data",
        "median_comments": statistics.median(comments) if comments else "No data",
    }
    return stats


def generate_insights_for_batch(video_batch):
    messages = [{"role": "system",
                 "content": "You are a helpful assistant that provides insights on YouTube videos."}]

    for video in video_batch:
        user_message = f"Tell me about this video: {video['title']} by {video['channel_name']}. It has {video['views']} views and was uploaded on {video['upload_date']}."
        messages.append({"role": "user", "content": user_message})

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages
    )

    # Extracting the assistant's messages from the response
    assistant_messages = [choice['message']['content']
                          for choice in response['choices']]

    return assistant_messages


def fetch_all_insights(videos, batch_size=5):
    insights = []

    # Split videos into batches
    video_batches = [videos[i:i + batch_size]
                     for i in range(0, len(videos), batch_size)]

    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(
            generate_insights_for_batch, video_batches))

    # Flatten the results
    for batch in results:
        insights.extend(batch)

    return insights


# Example usage:
# if __name__ == "__main__":
#     query = input("Enter a search query: ")
#     videos = fetch_video_details(query)
#     all_insights = fetch_all_insights(videos)
#     for insight in all_insights:
#         print(insight)

if __name__ == "__main__":
    query = input("I want to make a video about")

    print("\nOptimize for:")
    print("1. Views")
    print("2. Recency")
    print("3. Subscribers (Note: This will sort by channel popularity, not individual video subscribers)")

    choice = input("Enter your choice (1/2/3): ")

    order = "viewCount"  # default
    if choice == "2":
        order = "date"
    elif choice == "3":
        # This will sort by the number of videos a channel has, as a proxy for channel popularity
        order = "videoCount"

    top_video_ids = fetch_top_videos(query, order=order)
    videos = fetch_video_details(top_video_ids)
    stats = calculate_statistics(videos)
    for key, value in stats.items():
        print(f"{key}: {value}")
