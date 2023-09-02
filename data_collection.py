import os
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv
from statistics import median
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


def fetch_video_details(query, max_results=1000):
    search_response = youtube.search().list(
        q=query,
        part="id,snippet",
        maxResults=max_results
    ).execute()

    video_ids = [search_result["id"]["videoId"] for search_result in search_response.get(
        "items", []) if search_result["id"]["kind"] == "youtube#video"]

    video_details_response = youtube.videos().list(
        id=','.join(video_ids),
        part="id,snippet,statistics,contentDetails"
    ).execute()

    # Fetching video categories
    category_response = youtube.videoCategories().list(
        part="id,snippet",
        regionCode="IN"  # Assuming you're focusing on India, change as needed
    ).execute()
    category_dict = {item["id"]: item["snippet"]["title"]
                     for item in category_response.get("items", [])}

    videos = []
    for video in video_details_response.get("items", []):
        # Extract hashtags from description
        hashtags = re.findall(r'#\w+', video["snippet"]["description"])
        video_data = {
            "title": video["snippet"]["title"],
            "description": video["snippet"]["description"],
            "channel_name": video["snippet"]["channelTitle"],
            "views": video["statistics"]["viewCount"],
            "likes": video["statistics"].get("likeCount", 0),
            "dislikes": video["statistics"].get("dislikeCount", 0),
            "comments": video["statistics"].get("commentCount", 0),
            "upload_date": video["snippet"]["publishedAt"],
            "duration": video["contentDetails"]["duration"],
            "language": video["snippet"].get("defaultAudioLanguage", "Unknown"),
            "category": category_dict.get(video["snippet"]["categoryId"], "Unknown"),
            "hashtags": hashtags
        }
        videos.append(video_data)
    # Sorting videos by views
    videos.sort(key=lambda x: int(x['views']), reverse=True)

    return videos[:max_results]  # Return top videos based on views


def calculate_statistics(videos):
    views = [int(video['views']) for video in videos if video['views']]
    subscribers = [int(video['channel_subscribers'])
                   for video in videos if video.get('channel_subscribers')]
    comments = [int(video['comments'])
                for video in videos if video['comments']]
    durations = [iso8601_duration_to_seconds(
        video['duration']) for video in videos if video['duration']]
    upload_dates = [int(video['upload_date'].split('-')[0])
                    for video in videos]  # Extracting year

    stats = {
        "average_views": sum(views) / len(views),
        "median_views": median(views),
        "average_subscribers": sum(subscribers) / len(subscribers),
        "median_subscribers": median(subscribers),
        "total_channels": len(set([video['channel_name'] for video in videos])),
        "average_comments": sum(comments) / len(comments),
        "median_comments": median(comments),
        "average_duration": sum(durations) / len(durations),
        "median_duration": median(durations),
        "most_common_upload_year": mode(upload_dates),
        "related_categories": list(set([video['category'] for video in videos])),
        # You'll need to implement this function
        "common_hashtags": most_common_hashtags(videos)
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
    query = input("I want to make a video about, ")
    videos = fetch_video_details(query)
    stats = calculate_statistics(videos)
    print(stats)
