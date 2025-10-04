import os
import praw
import gspread
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Reddit Configuration
reddit = praw.Reddit(
    client_id=os.getenv('REDDIT_CLIENT_ID'),
    client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
    user_agent=os.getenv('REDDIT_USER_AGENT')
)

def fetch_reddit_feedback(subreddit_name, query, limit=100):
    """Fetch posts from Reddit"""
    try:
        print(f"🔍 Attempting to fetch from r/{subreddit_name}")
        print(f"   Query: '{query}' (empty={not query or query.strip() == ''})")
        
        subreddit = reddit.subreddit(subreddit_name)
        feedbacks = []
        
        # If no query, fetch all new posts
        if not query or query.strip() == '':
            print(f"   Using .new() to fetch all posts")
            posts = subreddit.new(limit=limit)
        else:
            print(f"   Using .search() with query")
            posts = subreddit.search(query, limit=limit, time_filter='month')
        
        post_count = 0
        for post in posts:
            post_count += 1
            print(f"   Found post: {post.title[:50]}...")
            feedbacks.append({
                'id': len(feedbacks) + 1,
                'feedback_text': f"{post.title}. {post.selftext}",
                'source': f'Reddit r/{subreddit_name}',
                'timestamp': post.created_utc
            })
        
        print(f"✓ Fetched {len(feedbacks)} posts from Reddit")
        return feedbacks
    
    except Exception as e:
        print(f"✗ Reddit fetch error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return []
    
def fetch_google_sheets_feedback(sheet_url):
    """Fetch feedback from public Google Sheet"""
    try:
        # Extract sheet ID from URL
        sheet_id = sheet_url.split('/d/')[1].split('/')[0]
        
        # Read as CSV (public sheets only)
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url)
        
        df.columns = df.columns.str.strip()
        
        # Auto-detect feedback column
        feedback_col = None
        for col in ['feedback', 'Feedback', 'feedback_text', 'comment', 'Comment']:
            if col in df.columns:
                feedback_col = col
                break
        
        if not feedback_col:
            feedback_col = df.columns[0]  # Use first column as fallback
        
        feedbacks = []
        for idx, row in df.iterrows():
            feedbacks.append({
                'id': idx + 1,
                'feedback_text': str(row[feedback_col]),
                'source': 'Google Forms'
            })
        
        print(f"Fetched {len(feedbacks)} rows from Google Sheets")
        return feedbacks
    
    except Exception as e:
        print(f"Google Sheets fetch error: {e}")
        return []