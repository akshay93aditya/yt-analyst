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


def format_metadata(videos):
    formatted_data = []
    for video in videos:
        title = video.get('title', 'Unknown Title')
        channel_name = video.get('channel_name', 'Unknown Channel')
        views = video.get('views', 'Unknown Views')
        subscribers = video.get('subscribers', 'Unknown Subscribers')
        publish_date = video.get('publish_date', 'Unknown Date')

        formatted_data.append(
            f"Video titled {title} by {channel_name} has {views} views and {subscribers} subscribers. It was published on {publish_date}."
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


def fetch_comments(video_ids, max_comments=100):
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


def analyze_with_openai(prompt, text):
    CHUNK_SIZE = 1850  # Adjust based on the model's token limit
    chunks = [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
    responses = []

    for chunk in chunks:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system",
                    "content": "You are an expert social media research consultant"},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": chunk}
            ]
        )
        responses.append(response.choices[0].message['content'].strip())

    return ' '.join(responses)


# Derive insights from aggregated responses


def derive_insights(transcripts, comments, videos):
    insights = {}

   # Combine all transcripts and comments
    transcript_text = " ".join(transcripts)
    comments_text = " ".join(comments)

    # Format metadata
    metadata = format_metadata(videos)

    # Base prompt
    # Replace with the actual topic the user inputted
    user_topic = query
    # Replace with the actual goal the user inputted
    user_goal = choice
    base_prompt = f"Role: System. Content: You are an expert social media research consultant hired to provide qualitative research insights for a creator. The creator wants to make a video about {user_topic} and aims to optimize for {user_goal}. Based on the provided data about various videos, their views, likes, dislikes, and the content of their transcripts and comments, please provide insights on the following:"

    # Analyze Transcripts
    insights['transcript_analysis'] = {
        "biggest_youtuber": analyze_with_openai(base_prompt + " Who is the biggest YouTuber in this category?", transcript_text + ' ' + metadata),
        "topics_covered": analyze_with_openai(base_prompt + " What topics are most often covered in these transcripts?", transcript_text)
    }

    # Analyze Comments
    insights['comment_analysis'] = {
        "positive_reactions": analyze_with_openai(base_prompt + " What are the positive reactions in these comments related to?", comments_text),
        "negative_reactions": analyze_with_openai(base_prompt + " What are the negative reactions in these comments related to?", comments_text),
        "referenced_creators": analyze_with_openai(base_prompt + " Which creators or YouTubers are referenced often in these comments?", comments_text),
        "viewer_requests": analyze_with_openai(base_prompt + " What do viewers request or wish to see most often in these comments?", comments_text),
        "tired_topics": analyze_with_openai(base_prompt + " What topics or themes do viewers seem tired of or mention negatively?", comments_text),
        # Assuming you've integrated the word cloud function
        "word_cloud": analyze_with_openai(base_prompt + "Generate a list of words for a wordcloud of the most commonly used words and phrases", comments_text)
    }

    return insights


# def generate_wordcloud(text):
#     wordcloud = WordCloud(width=800, height=800,
#                           background_color='white',
#                           stopwords=set(STOPWORDS),
#                           min_font_size=10).generate(text)

#     plt.figure(figsize=(8, 8), facecolor=None)
#     plt.imshow(wordcloud)
#     plt.axis("off")
#     plt.tight_layout(pad=0)
#     plt.show()
#     if save_to_file:
#         plt.savefig("wordcloud.png", format="png")
#     else:
#         plt.show()


if __name__ == "__main__":
    query = input("I want to make a video about ")

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

    transcripts = fetch_transcripts(top_video_ids)
    comments = fetch_comments(top_video_ids)

    insights = derive_insights(transcripts, comments, videos)
    for key, value in insights.items():
        print(f"{key}: {value}")
