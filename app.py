from flask import Flask, render_template, request, redirect, url_for
import data_collection  # Importing your existing script

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        search_type = request.form.get('search_type')
        query = request.form.get('query')
        choice = request.form.get('choice')

        top_video_ids = data_collection.fetch_top_videos(search_type, query)
        videos = data_collection.fetch_video_details(top_video_ids)
        stats = data_collection.calculate_statistics(videos)

        # Return the stats immediately
        return render_template('results.html', stats=stats, insights=None)

    return render_template('index.html')


@app.route('/generate_insights', methods=['POST'])
def generate_insights():
    print("Request received for insights generation.")
    search_type = request.form.get('search_type')
    query = request.form.get('query')
    choice = request.form.get('choice')

    top_video_ids = data_collection.fetch_top_videos(search_type, query)
    videos = data_collection.fetch_video_details(top_video_ids)
    transcripts = data_collection.fetch_transcripts(top_video_ids)
    comments = data_collection.fetch_comments(top_video_ids)
    insights = data_collection.derive_insights(
        transcripts, comments, videos, query, choice)
    print("Insights generation completed.")
    return render_template('insights.html', insights=insights)


if __name__ == '__main__':
    app.run(debug=True)
