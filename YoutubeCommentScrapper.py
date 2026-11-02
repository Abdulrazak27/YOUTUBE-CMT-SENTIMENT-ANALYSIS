import os
import csv
import requests
import warnings
warnings.filterwarnings('ignore')

try:
    import streamlit as st
    DEVELOPER_KEY = st.secrets.get("YOUTUBE_API_KEY", os.getenv("YOUTUBE_API_KEY", ""))
except Exception:
    DEVELOPER_KEY = os.getenv("YOUTUBE_API_KEY", "")
BASE = "https://www.googleapis.com/youtube/v3"
SESSION = requests.Session()
SESSION.verify = False  # bypass SSL

def _get(endpoint, params):
    params['key'] = DEVELOPER_KEY
    r = SESSION.get(f"{BASE}/{endpoint}", params=params)
    return r.json()

def get_channel_id(video_id):
    data = _get("videos", {"part": "snippet", "id": video_id})
    if 'items' in data and len(data['items']) > 0:
        return data['items'][0]['snippet']['channelId']
    return None

def save_video_comments_to_csv(video_id, max_comments=500):
    if not video_id:
        return ""
    comments = []
    params = {"part": "snippet", "videoId": video_id, "textFormat": "plainText", "maxResults": 100}
    while True:
        data = _get("commentThreads", params)
        for item in data.get('items', []):
            s = item['snippet']['topLevelComment']['snippet']
            comments.append([s['authorDisplayName'], s['textDisplay']])
        if 'nextPageToken' in data and len(comments) < max_comments:
            params['pageToken'] = data['nextPageToken']
        else:
            break
    filename = video_id + '.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Username', 'Comment'])
        w.writerows(comments)
    return filename

def get_video_stats(video_id):
    data = _get("videos", {"part": "statistics", "id": video_id})
    if 'items' in data and len(data['items']) > 0:
        return data['items'][0].get('statistics', {'viewCount': '0', 'likeCount': '0', 'commentCount': '0'})
    return {'viewCount': '0', 'likeCount': '0', 'commentCount': '0'}

def get_channel_info(youtube, channel_id):
    if not channel_id:
        return {
            'channel_title': 'Unknown Channel',
            'video_count': '0',
            'channel_logo_url': '',
            'channel_created_date': '',
            'subscriber_count': '0',
            'channel_description': 'No description available'
        }
    data = _get("channels", {"part": "snippet,statistics", "id": channel_id})
    if 'items' in data and len(data['items']) > 0:
        item = data['items'][0]
        return {
            'channel_title':        item['snippet'].get('title', 'Unknown'),
            'video_count':          item.get('statistics', {}).get('videoCount', '0'),
            'channel_logo_url':     item['snippet'].get('thumbnails', {}).get('high', {}).get('url', ''),
            'channel_created_date': item['snippet'].get('publishedAt', ''),
            'subscriber_count':     item.get('statistics', {}).get('subscriberCount', '0'),
            'channel_description':  item['snippet'].get('description', '')
        }
    return {
        'channel_title': 'Unknown Channel',
        'video_count': '0',
        'channel_logo_url': '',
        'channel_created_date': '',
        'subscriber_count': '0',
        'channel_description': 'No description available'
    }

# dummy for compatibility
youtube = None