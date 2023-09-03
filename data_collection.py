import os
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv
import statistics
import re
import openai
from wordcloud import WordCloud
from wordcloud import STOPWORDS
import matplotlib.pyplot as plt

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


def chunk_text(text, max_length):
    """Breaks down a long text into chunks that are within the specified max_length."""
    words = text.split()
    chunks = []
    current_chunk = []

    for word in words:
        if len(' '.join(current_chunk) + ' ' + word) <= max_length:
            current_chunk.append(word)
        else:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
    chunks.append(' '.join(current_chunk))
    return chunks


# Fetch and sort videos based on user input


def fetch_top_videos(search_type, query, max_results=10, order="viewCount"):
    q = " "  # initialize q as an empty string
    if search_type == "about":
        q = query
    elif search_type == "in the style of":
        # This will search for videos from a specific channel
        q = f"channel:{query}"
    elif search_type == "like":
        # For this, you might need a more complex approach, like fetching details of the provided video and then searching for similar videos.
        # For simplicity, I'm just using the video title for now.
        video_details = youtube.videos().list(id=query, part="snippet").execute()
        video_title = video_details["items"][0]["snippet"]["title"]
        q = video_title

    search_response = youtube.search().list(
        q=q,
        type="video",
        order=order,
        part="id",
        maxResults=max_results
    ).execute()

    video_ids = [item["id"]["videoId"] for item in search_response["items"]]
    return video_ids

# Fetch video details based on predefined format


def fetch_video_details(video_ids):
    video_details_response = youtube.videos().list(
        id=','.join(video_ids),
        part="id,snippet,statistics,contentDetails"
    ).execute()

    videos = video_details_response["items"]
    return videos


# Calculate stats for videos


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

# Format data to prevent youtube video id's being passed to OpenAI


def remove_video_ids(text):
    # Regular expression to match typical YouTube video IDs
    pattern = r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{11}(?![A-Za-z0-9_-])'
    return re.sub(pattern, '', text)


def format_metadata(videos):
    formatted_data = []
    for video in videos:
        title = video['snippet']['title']
        channel_name = video['snippet']['channelTitle']
        views = video['statistics']['viewCount'] if 'viewCount' in video['statistics'] else "N/A"
        subscribers = "N/A"  # YouTube API doesn't provide subscribers for individual videos
        publish_date = video['snippet']['publishedAt']

        formatted_data.append(
            f"Video titled {title} by {channel_name} has {views} views. It was published on {publish_date}."
        )
    return ' '.join(formatted_data)


# Fetch transcripts of videos & comments


def fetch_transcripts(video_ids):
    transcripts = {}
    for video_id in video_ids:
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            transcripts[video_id] = transcript
        except:
            continue
    return transcripts


def fetch_comments(video_ids, max_comments=10):
    comments = {}
    for video_id in video_ids:
        try:
            response = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=max_comments,
                order="relevance",  # Fetch most relevant comments
                textFormat="plainText"
            ).execute()

            comments_list = [item["snippet"]["topLevelComment"]
                             ["snippet"]["textDisplay"] for item in response["items"]]
            comments[video_id] = comments_list
        except:
            continue
    return comments


# Analyze chunked up content


def analyze_with_openai(prompt, text, videos_metadata, query, choice):
    CHUNK_SIZE = 1850  # Adjust this according to the token constraints of your model
    chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
    responses = []

    # Base prompt
    user_topic = query
    user_goal = choice

    for chunk in chunks:
        messages = [
            {"role": "system", "content": f"You are an expert social media research consultant hired to provide qualitative research insights for a creator. The creator wants to make a video about {user_topic} and aims to optimize for {user_goal}. Based on the provided data about various videos, their views, likes, dislikes, and the content of their transcripts and comments, please provide insights on the following:"},
            {"role": "user", "content": f"{prompt} {videos_metadata}"},
            {"role": "user", "content": chunk}
        ]

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages
        )

        responses.append(response['choices'][0]['message']['content'].strip())

    # Here, instead of joining all the responses, we'll return the most relevant one.
    # This is a simple heuristic, but you can refine it further.
    return max(responses, key=len)


def derive_insights(transcripts, comments, videos, query, choice):
    insights = {}

    # Combine all transcripts and comments
    transcript_text = remove_video_ids(" ".join([" ".join(
        [segment['text'] for segment in video_transcript]) for video_transcript in transcripts.values()]))
    comments_text = remove_video_ids(
        " ".join([comment for sublist in comments.values() for comment in sublist]))

    # Format metadata
    metadata = format_metadata(videos)

    # Analyze Transcripts
    insights['biggest_youtuber'] = analyze_with_openai(
        "Who is the biggest YouTuber in this category?", transcript_text, metadata, query, choice)
    insights['topics_covered'] = analyze_with_openai(
        "List the top 5 topics most often covered in these transcripts.", transcript_text, metadata, query, choice)

    # Analyze Comments
    insights['positive_reactions'] = analyze_with_openai(
        "List the top 5 positive reactions in these comments.", comments_text, metadata, query, choice)
    insights['negative_reactions'] = analyze_with_openai(
        "List the top 5 negative reactions in these comments.", comments_text, metadata, query, choice)
    insights['referenced_creators'] = analyze_with_openai(
        "Which creators or YouTubers are referenced often in these comments?", comments_text, metadata, query, choice)
    insights['viewer_requests'] = analyze_with_openai(
        "List the top 5 topics viewers request or wish to see most often in these comments.", comments_text, metadata, query, choice)
    insights['tired_topics'] = analyze_with_openai(
        "List the top 5 topics or themes viewers seem tired of or mention negatively.", comments_text, metadata, query, choice)
    insights['ideal_video'] = analyze_with_openai(
        "Describe the ideal video duration, topics, and most requested topics for a video in this category.", comments_text, metadata, query, choice)

    return insights  # This will now return a dictionary


def generate_wordcloud(text):
    wordcloud = WordCloud(width=800, height=800,
                          background_color='white',
                          stopwords=set(STOPWORDS),
                          min_font_size=10).generate(text)

    plt.figure(figsize=(8, 8), facecolor=None)
    plt.imshow(wordcloud)
    plt.axis("off")
    plt.tight_layout(pad=0)
    file_path = "/Users/akshay/Desktop/ytanalyst/png/wordcloud.png"
    plt.savefig(file_path, format="png")
    plt.close()

    return file_path


if __name__ == "__main__":
    print("\nChoose your search type:")
    print("1. About (Topic/Category search)")
    print("2. In the style of (Channel search)")
    print("3. Like (Video search)")

    search_type_choice = input("Enter your choice (1/2/3): ")

    search_type = ""
    if search_type_choice == "1":
        search_type = "about"
        query = input("\nI want to make a video about: ")
    elif search_type_choice == "2":
        search_type = "in the style of"
        query = input(
            "\nI want to make a video in the style of (Enter YouTuber or Channel name): ")
    elif search_type_choice == "3":
        search_type = "like"
        video_link = input(
            "\nI want to make a video like (Provide the video link): ")
        # Extract video ID from the link and use it as the query
        query = video_link.split("v=")[-1]

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

    print("\nCalculating stats and fetching videos")

    top_video_ids = fetch_top_videos(search_type, query, order=order)
    videos = fetch_video_details(top_video_ids)
    stats = calculate_statistics(videos)
    for key, value in stats.items():
        print(f"{key}: {value}")

    print("\nFetching transcripts and comments")
    transcripts = fetch_transcripts(top_video_ids)
    comments = fetch_comments(top_video_ids)

    print("\nDeriving insights")
    insights = derive_insights(transcripts, comments, videos, query, choice)
    for key, value in insights.items():
        print(f"{key}: {value}")
