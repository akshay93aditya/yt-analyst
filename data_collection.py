import os
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv
import re
from transformers import AutoModelForCausalLM, AutoTokenizer

load_dotenv()
API_KEY = os.getenv('youtube_api_key')
youtube = build('youtube', 'v3', developerKey=API_KEY)


def fetch_video_details(query, max_results=10):
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

    return videos


def generate_insights(videos):
    # Load pre-trained model and tokenizer
    model_name = "llama-2-7b"  # This is the Llama model you downloaded
    # Path to the model being used
    model_path = "/Users/akshay/Desktop/llama/llama-2-7b"
    model = AutoModelForCausalLM.from_pretrained(model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path)

    # Prepare a prompt for the model
    prompt = "Based on the following YouTube video data, provide insights:\n"
    for video in videos[:5]:  # Taking a sample of 5 videos for brevity
        prompt += f"Title: {video['title']}, Views: {video['views']}, Likes: {video['likes']}, Comments: {video['comments']}\n"

    # Generate insights using Llama
    input_ids = tokenizer.encode(prompt, return_tensors='pt')
    output = model.generate(input_ids, max_length=500, num_return_sequences=1,
                            no_repeat_ngram_size=2, early_stopping=True)
    generated_text = tokenizer.decode(output[0], skip_special_tokens=True)

    # Extract only the generated insights
    insights = generated_text.split(prompt)[1].strip()

    return insights


if __name__ == "__main__":
    query = input("Enter a search query: ")
    results = fetch_video_details(query)
    insights = generate_insights(results)
    print("\nGenerated Insights:\n", insights)
