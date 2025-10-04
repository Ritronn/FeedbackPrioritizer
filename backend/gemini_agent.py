import os
import json
import asyncio
import aiohttp
import pandas as pd
import sqlite3
import time
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
API_KEY = os.getenv('GEMINI_API_KEY')
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found. Please set it in your .env file.")

MODEL_NAME = 'gemini-2.0-flash-exp'
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"

# --- SQLite Database Setup ---
DB_PATH = "feedback.db"

def init_database():
    """Initialize SQLite database with feedback table."""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analyzed_feedback (
            id INTEGER PRIMARY KEY,
            feedback_text TEXT NOT NULL,
            source TEXT DEFAULT 'CSV',
            sentiment TEXT,
            sentiment_score REAL,
            category TEXT,
            urgency_level TEXT,
            priority_score INTEGER,
            key_issue TEXT,
            suggested_action TEXT,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print("✓ Database initialized")

def save_to_database(results_df):
    """Save analyzed results to SQLite."""
    conn = sqlite3.connect(DB_PATH)
    
    # Clear existing data (or you can append instead)
    conn.execute("DELETE FROM analyzed_feedback")
    
    # Insert new results
    results_df.to_sql('analyzed_feedback', conn, if_exists='append', index=False)
    
    conn.commit()
    conn.close()
    print(f"✓ Saved {len(results_df)} records to database")

# --- Response Schema Definition ---
FEEDBACK_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "feedback_text": {"type": "string"},
            "source": {"type": "string"},
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
            "sentiment_score": {"type": "number", "minimum": -1.0, "maximum": 1.0},
            "category": {"type": "string", "enum": ["Bug", "Feature Request", "UX Issue", "Performance", "Pricing", "Other"]},
            "urgency_level": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
            "priority_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "key_issue": {"type": "string"},
            "suggested_action": {"type": "string"}
        },
        "required": ["id", "sentiment", "sentiment_score", "category", "urgency_level", "priority_score", "key_issue", "suggested_action"]
    }
}

def build_prompt(feedback_list):
    """Builds optimized prompt for batch analysis."""
    if not feedback_list:
        return ""

    feedback_texts = "\n".join([
        f"ID {f['id']} [{f.get('source', 'Unknown')}]: {f['feedback_text']}" 
        for f in feedback_list
    ])

    prompt = f"""Analyze the following customer feedbacks and return a JSON array with analysis for each.

Priority Scoring Rules:
- Critical bugs with negative sentiment: 80-100
- High impact issues blocking users: 60-79
- UX improvements and feature requests: 40-59
- Minor issues and positive feedback: 0-39

For each feedback, include:
- Original feedback_text
- Source (Reddit/Survey/CSV/etc.)
- All analysis fields

Feedbacks:
{feedback_texts}

Return a JSON array with one object per feedback, maintaining the ID and source from input."""
    return prompt

async def analyze_feedback_batch_async(session, batch_data, batch_num, semaphore):
    """Analyzes a batch with rate limiting via semaphore."""
    async with semaphore:
        try:
            prompt = build_prompt(batch_data)
        except KeyError as e:
            print(f"[Batch {batch_num}] ❌ KeyError in build_prompt: Missing field {e}")
            print(f"   Available fields: {list(batch_data[0].keys()) if batch_data else 'No data'}")
            return []
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": FEEDBACK_SCHEMA,
                "temperature": 0.2,
            }
        }

        try:
            async with session.post(API_URL, json=payload) as response:
                if response.status != 200:
                    error_body = await response.text()
                    print(f"[Batch {batch_num}] API Error {response.status}: {error_body[:200]}...")
                    return []
                
                response_json = await response.json()
                result_text = response_json.get('candidates', [{}])[0]\
                                           .get('content', {})\
                                           .get('parts', [{}])[0]\
                                           .get('text', "").strip()

                results = json.loads(result_text)
                
                # Preserve original feedback_text and source
                for i, result in enumerate(results):
                    if i < len(batch_data):
                        result['feedback_text'] = batch_data[i]['feedback_text']
                        result['source'] = batch_data[i].get('source', 'CSV')
                
                print(f"[Batch {batch_num}] ✓ Processed {len(results)} feedbacks")
                
                # Small delay to respect rate limits
                await asyncio.sleep(0.3)
                
                return results

        except aiohttp.ClientError as e:
            print(f"[Batch {batch_num}] HTTP Error: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"[Batch {batch_num}] JSON Error: {e}")
            return []
        except Exception as e:
            print(f"[Batch {batch_num}] Unexpected error: {type(e).__name__}: {e}")
            return []

# --- EXPORTED FUNCTION FOR FLASK APP ---
async def process_feedbacks_async(feedbacks):
    """
    Wrapper function for app.py to import and use.
    Takes list of feedback dicts with 'id', 'feedback_text', and optional 'source' keys.
    Returns list of analyzed results.
    """
    # Ensure all feedbacks have required fields
    for fb in feedbacks:
        if 'source' not in fb:
            fb['source'] = 'CSV'
        if 'id' not in fb:
            fb['id'] = feedbacks.index(fb) + 1
    
    batch_size = 20
    max_concurrent = 5
    semaphore = asyncio.Semaphore(max_concurrent)
    all_tasks = []
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as session:
        for i in range(0, len(feedbacks), batch_size):
            chunk = feedbacks[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            task = analyze_feedback_batch_async(session, chunk, batch_num, semaphore)
            all_tasks.append(task)
        
        print(f"🚀 Processing {len(feedbacks)} feedbacks in {len(all_tasks)} batches...")
        results_from_tasks = await asyncio.gather(*all_tasks, return_exceptions=True)
    
    all_results = []
    for result in results_from_tasks:
        if isinstance(result, list):
            all_results.extend(result)
        elif isinstance(result, Exception):
            print(f"Task exception: {type(result).__name__}: {result}")
    
    return all_results

async def main():
    start_time = time.time()
    
    # Initialize database
    init_database()
    
    # 1. Load Data with Better Error Handling
    try:
        df = pd.read_csv("data/sample_feedback.csv")
        print(f"Loaded {len(df)} feedbacks from CSV")
        
        # Debug: Show CSV structure
        print(f"CSV Columns: {list(df.columns)}")
        print(f"First row sample: {df.iloc[0].to_dict() if len(df) > 0 else 'Empty'}\n")
        
        # Strip whitespace from column names
        df.columns = df.columns.str.strip()
        
        # Check for required columns
        required_cols = ['feedback_text']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            print(f"❌ ERROR: Missing required columns: {missing_cols}")
            print(f"   Available columns: {list(df.columns)}")
            
            # Try to auto-fix common issues
            if 'feedback' in df.columns or 'text' in df.columns:
                if 'feedback' in df.columns:
                    df.rename(columns={'feedback': 'feedback_text'}, inplace=True)
                elif 'text' in df.columns:
                    df.rename(columns={'text': 'feedback_text'}, inplace=True)
                print("   ✓ Fixed: Renamed feedback column")
            
            # Check again after fixes
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                print(f"\n❌ Still missing: {missing_cols}. Please fix your CSV.")
                return
        
        # Add 'id' column if it doesn't exist
        if 'id' not in df.columns:
            df['id'] = range(1, len(df) + 1)
            print("✓ Generated 'id' column (1 to n)")
        
        # Add 'source' column if it doesn't exist
        if 'source' not in df.columns:
            df['source'] = 'CSV'
            print("✓ Added default 'source' column (CSV)")
        
    except FileNotFoundError:
        print("ERROR: 'data/sample_feedback.csv' not found.")
        return
    except Exception as e:
        print(f"ERROR loading CSV: {e}")
        return
    
    feedbacks = df.to_dict("records")
    total_feedbacks = len(feedbacks)
    
    # 2. Use the exported function
    all_results = await process_feedbacks_async(feedbacks)

    end_time = time.time()
    total_time = end_time - start_time
    
    # 3. Save Results
    if all_results:
        results_df = pd.DataFrame(all_results)
        
        # Save to CSV (backup)
        output_path = "data/analyzed_feedback.csv"
        results_df.to_csv(output_path, index=False)
        print(f"✓ CSV backup saved to: {output_path}")
        
        # Save to SQLite (primary storage)
        save_to_database(results_df)
        
    else:
        print("\n⚠️  No results to save. Check errors above.")
    
    # 4. Summary
    print("\n" + "="*60)
    print("📊 ANALYSIS COMPLETE")
    print(f"   Total Feedbacks: {total_feedbacks}")
    print(f"   Successfully Analyzed: {len(all_results)}")
    print(f"   Success Rate: {len(all_results)/total_feedbacks*100:.1f}%")
    print(f"   Total Time: {total_time:.2f}s")
    if total_feedbacks > 0:
        print(f"   Average Time per Feedback: {total_time/total_feedbacks:.2f}s")
    print(f"   Database: {DB_PATH}")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())