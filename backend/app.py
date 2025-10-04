import os
import sqlite3
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from gemini_agent import process_feedbacks_async, build_prompt
from data_collectors import fetch_reddit_feedback, fetch_google_sheets_feedback
import google.generativeai as genai

load_dotenv()

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "feedback-prioritizer.vercel.app",
            "https://*.vercel.app"  # Allow all Vercel preview deployments
        ]
    }
})

# --- Configuration ---
DB_PATH = 'feedback.db'
SMTP_EMAIL = os.getenv('SMTP_EMAIL')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL', SMTP_EMAIL)
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SLACK_WEBHOOK = os.getenv('SLACK_WEBHOOK_URL')

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS feedback_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feedback_id INTEGER,
        feedback_text TEXT,
        source TEXT,  -- ADD THIS LINE
        sentiment TEXT,
        sentiment_score REAL,
        category TEXT,
        urgency_level TEXT,
        priority_score INTEGER,
        key_issue TEXT,
        suggested_action TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_db()
def init_sources_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS data_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reddit_subreddit TEXT,
        reddit_query TEXT,
        google_sheet_url TEXT,
        enabled BOOLEAN DEFAULT 1,
        last_synced TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_sources_table()  

# --- Helper Functions ---
def save_to_db(results, original_feedbacks):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    feedback_map = {f['id']: {'text': f['feedback_text'], 'source': f.get('source', 'CSV')} 
                    for f in original_feedbacks}
    
    for r in results:
        fb = feedback_map.get(r['id'], {'text': '', 'source': 'Unknown'})
        c.execute('''INSERT INTO feedback_analysis 
                    (feedback_id, feedback_text, source, sentiment, sentiment_score, category, 
                     urgency_level, priority_score, key_issue, suggested_action)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (r['id'], fb['text'], fb['source'], r['sentiment'], r['sentiment_score'],
                  r['category'], r['urgency_level'], r['priority_score'], 
                  r['key_issue'], r['suggested_action']))
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- Slack Function ---
def send_slack_alert(top_issues):
    """Send top priority issues to Slack"""
    if not SLACK_WEBHOOK:
        print("⚠️  Slack webhook not configured")
        return
    
    try:
        message = "🔥 *Weekly Top Priority Issues*\n\n"
        for issue in top_issues[:5]:
            urgency_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
            emoji = urgency_emoji.get(issue['urgency_level'], '⚪')
            message += f"{emoji} *{issue['key_issue']}* (Priority: {issue['priority_score']})\n"
            message += f"   Category: {issue['category']} | Action: {issue['suggested_action']}\n\n"
        
        response = requests.post(SLACK_WEBHOOK, json={"text": message})
        if response.status_code == 200:
            print("✅ Slack message sent")
        else:
            print(f"❌ Slack error: {response.status_code}")
    except Exception as e:
        print(f"❌ Slack error: {e}")

# --- Email Functions ---
def send_weekly_email():
    """Send weekly priority report via email"""
    if not all([SMTP_EMAIL, SMTP_PASSWORD, RECIPIENT_EMAIL]):
        print("⚠️  Email not configured. Skipping email send.")
        return
    
    try:
        conn = get_db_connection()
 
        week_ago = datetime.now() - timedelta(days=7)
        query = '''SELECT * FROM feedback_analysis 
                   WHERE created_at >= ? 
                   ORDER BY priority_score DESC LIMIT 10'''
        
        top_issues = conn.execute(query, (week_ago,)).fetchall()

        stats = conn.execute('''SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN urgency_level = 'critical' THEN 1 ELSE 0 END) as critical,
            SUM(CASE WHEN urgency_level = 'high' THEN 1 ELSE 0 END) as high,
            category, COUNT(*) as count
            FROM feedback_analysis 
            WHERE created_at >= ?
            GROUP BY category''', (week_ago,)).fetchall()
        
        conn.close()
        
        # Build HTML email
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background: #4F46E5; color: white; padding: 20px; }}
                .issue {{ border-left: 4px solid #EF4444; padding: 10px; margin: 10px 0; background: #FEE; }}
                .stats {{ background: #F3F4F6; padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Weekly Feedback Priority Report</h1>
                <p>{datetime.now().strftime('%B %d, %Y')}</p>
            </div>
            
            <div class="stats">
                <h2>📈 This Week's Stats</h2>
                <p><strong>Total Feedback:</strong> {len(top_issues)}</p>
            </div>
            
            <h2>🔥 Top 10 Priority Issues</h2>
        """
        
        for issue in top_issues:
            urgency_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
            html += f"""
            <div class="issue">
                <p><strong>{urgency_emoji.get(issue['urgency_level'], '⚪')} Priority: {issue['priority_score']}/100</strong></p>
                <p><strong>Category:</strong> {issue['category']}</p>
                <p><strong>Issue:</strong> {issue['key_issue']}</p>
                <p><strong>Action:</strong> {issue['suggested_action']}</p>
            </div>
            """
        
        html += """
            <p style="margin-top: 30px; color: #666;">
                View full dashboard at <a href="http://localhost:5000/dashboard">your dashboard</a>
            </p>
        </body>
        </html>
        """
        
        # Send email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Weekly Feedback Report - {datetime.now().strftime('%b %d, %Y')}"
        msg['From'] = SMTP_EMAIL
        msg['To'] = RECIPIENT_EMAIL
        
        msg.attach(MIMEText(html, 'html'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        
        print(f"✅ Weekly email sent to {RECIPIENT_EMAIL}")
        
        # Send to Slack
        send_slack_alert([dict(i) for i in top_issues])
        
    except Exception as e:
        print(f"❌ Email error: {e}")

# --- API Endpoints ---
@app.route('/')
def home():
    return jsonify({
        "message": "🚀 Customer Feedback Prioritizer API",
        "endpoints": {
            "POST /upload": "Upload CSV file for analysis",
            "GET /dashboard": "Get dashboard data (JSON)",
            "GET /feedback": "Get all feedback (paginated)",
            "GET /stats": "Get statistics",
            "GET /export": "Download analyzed data as CSV",
            "POST /send-email": "Manually trigger email report"
        }
    })

@app.route('/upload', methods=['POST'])
def upload_feedback():
    """Upload and analyze CSV file"""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400
    
    try:
        # Read and validate CSV
        df = pd.read_csv(file)
        df.columns = df.columns.str.strip()
        
        if 'id' not in df.columns:
            df['id'] = range(1, len(df) + 1)
        
        # Handle feedback_text column
        if 'feedback_text' not in df.columns:
            for col in ['feedback', 'text', 'comment', 'Feedback']:
                if col in df.columns:
                    df.rename(columns={col: 'feedback_text'}, inplace=True)
                    break
        
        if 'feedback_text' not in df.columns:
            return jsonify({"error": "No feedback text column found. Required: 'feedback_text'"}), 400
        
        # ✅ FIXED: Handle source column properly
        if 'source' not in df.columns:
            # If no source column, check for common variations
            for col in ['Source', 'platform', 'Platform', 'channel', 'Channel']:
                if col in df.columns:
                    df.rename(columns={col: 'source'}, inplace=True)
                    break
            
            # If still no source column, set default to 'CSV Upload'
            if 'source' not in df.columns:
                df['source'] = 'CSV Upload'
        
        # Convert to dict with source included
        feedbacks = df[['id', 'feedback_text', 'source']].to_dict('records')
        
        # Process using your gemini_agent.py
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(process_feedbacks_async(feedbacks))
        loop.close()
        
        if not results:
            return jsonify({"error": "Analysis failed. Check API key and quota."}), 500
        
        # Clear previous data before saving new analysis
        conn = sqlite3.connect(DB_PATH)
        conn.execute('DELETE FROM feedback_analysis')
        conn.commit()
        conn.close()
        print("🗑️  Cleared previous data")
        
        # Save to database
        save_to_db(results, feedbacks)
        
        # Send Slack alert for critical issues
        critical_issues = [r for r in results if r['urgency_level'] == 'critical']
        if critical_issues:
            send_slack_alert(critical_issues)
        
        return jsonify({
            "success": True,
            "message": f"Analyzed {len(results)} feedbacks successfully",
            "processed": len(results),
            "total": len(feedbacks)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/sources/configure', methods=['POST'])
def configure_sources():
    """Save data source configuration"""
    data = request.json
    
    reddit_subreddit = data.get('reddit_subreddit', '')
    reddit_query = data.get('reddit_query', '')
    google_sheet_url = data.get('google_sheet_url', '')
    
    if not any([reddit_subreddit, google_sheet_url]):
        return jsonify({"error": "At least one data source required"}), 400
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Delete old config (only one config allowed for now)
        c.execute('DELETE FROM data_sources')
        
        # Insert new config
        c.execute('''INSERT INTO data_sources 
                    (reddit_subreddit, reddit_query, google_sheet_url, enabled)
                    VALUES (?, ?, ?, 1)''',
                 (reddit_subreddit, reddit_query, google_sheet_url))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "message": "Data sources configured successfully"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/sources/get', methods=['GET'])
def get_sources():
    """Get current data source configuration"""
    conn = get_db_connection()
    source = conn.execute('SELECT * FROM data_sources WHERE enabled = 1 ORDER BY id DESC LIMIT 1').fetchone()
    conn.close()
    
    if source:
        return jsonify(dict(source))
    return jsonify({"configured": False})

def collect_and_analyze_weekly():
    """Fetch data from configured sources and analyze"""
    print("\n🔄 Starting weekly data collection...")
    
    try:
        # Get configured sources
        conn = get_db_connection()
        source_config = conn.execute('SELECT * FROM data_sources WHERE enabled = 1 LIMIT 1').fetchone()
        conn.close()
        
        if not source_config:
            print("⚠️  No data sources configured")
            return
        
        all_feedbacks = []
        
        # Fetch from Reddit
        if source_config['reddit_subreddit']:
            reddit_data = fetch_reddit_feedback(
                source_config['reddit_subreddit'],
                source_config['reddit_query'] or '',
                limit=50
            )
            all_feedbacks.extend(reddit_data)
        
        # Fetch from Google Sheets
        if source_config['google_sheet_url']:
            sheets_data = fetch_google_sheets_feedback(source_config['google_sheet_url'])
            all_feedbacks.extend(sheets_data)
        
        if not all_feedbacks:
            print("⚠️  No feedback collected")
            return
        
        # Assign unique IDs
        for idx, fb in enumerate(all_feedbacks):
            fb['id'] = idx + 1
        
        print(f"📊 Collected {len(all_feedbacks)} total feedbacks")
        
        # Analyze with Gemini
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(process_feedbacks_async(all_feedbacks))
        loop.close()
        
        if results:
            # Clear old data
            conn = sqlite3.connect(DB_PATH)
            conn.execute('DELETE FROM feedback_analysis')
            conn.commit()
            conn.close()
            
            # Save new results
            save_to_db(results, all_feedbacks)
            
            # Update last_synced timestamp
            conn = sqlite3.connect(DB_PATH)
            conn.execute('UPDATE data_sources SET last_synced = ? WHERE id = ?',
                        (datetime.now(), source_config['id']))
            conn.commit()
            conn.close()
            
            print(f"✅ Analyzed and saved {len(results)} feedbacks")
            
            # Send email report
            send_weekly_email()
        
    except Exception as e:
        print(f"❌ Weekly collection error: {e}")

@app.route('/test-collection', methods=['POST'])
def test_collection():
    """Manually trigger data collection for testing"""
    try:
        collect_and_analyze_weekly()
        return jsonify({"success": True, "message": "Collection triggered, check server logs"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/dashboard', methods=['GET'])
def get_dashboard():
    """Get dashboard data as JSON"""
    try:
        conn = get_db_connection()
        
        # Get all feedback
        feedbacks = conn.execute('''SELECT * FROM feedback_analysis 
                                   ORDER BY priority_score DESC, created_at DESC''').fetchall()
        
        feedback_list = [dict(row) for row in feedbacks]
        
        # Calculate stats
        total = len(feedback_list)
        stats = {
            "total_feedback": total,
            "by_urgency": {
                "critical": sum(1 for f in feedback_list if f['urgency_level'] == 'critical'),
                "high": sum(1 for f in feedback_list if f['urgency_level'] == 'high'),
                "medium": sum(1 for f in feedback_list if f['urgency_level'] == 'medium'),
                "low": sum(1 for f in feedback_list if f['urgency_level'] == 'low')
            },
            "by_category": {},
            "by_sentiment": {
                "positive": sum(1 for f in feedback_list if f['sentiment'] == 'positive'),
                "negative": sum(1 for f in feedback_list if f['sentiment'] == 'negative'),
                "neutral": sum(1 for f in feedback_list if f['sentiment'] == 'neutral')
            },
            "avg_priority_score": sum(f['priority_score'] for f in feedback_list) / total if total > 0 else 0
        }
        
        # Category breakdown
        for f in feedback_list:
            cat = f['category']
            stats['by_category'][cat] = stats['by_category'].get(cat, 0) + 1
        
        conn.close()
        
        return jsonify({
            "stats": stats,
            "feedbacks": feedback_list[:100],  # Return top 100 for performance
            "top_priority": feedback_list[:10]  # Top 10 critical issues
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/feedback', methods=['GET'])
def get_feedback():
    """Get paginated feedback"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    feedbacks = conn.execute('''SELECT * FROM feedback_analysis 
                               ORDER BY priority_score DESC 
                               LIMIT ? OFFSET ?''', (per_page, offset)).fetchall()
    
    total = conn.execute('SELECT COUNT(*) FROM feedback_analysis').fetchone()[0]
    conn.close()
    
    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": total,
        "data": [dict(row) for row in feedbacks]
    })

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get quick statistics"""
    conn = get_db_connection()
    
    stats = conn.execute('''SELECT 
        COUNT(*) as total,
        AVG(priority_score) as avg_priority,
        SUM(CASE WHEN urgency_level = 'critical' THEN 1 ELSE 0 END) as critical_count,
        SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as negative_count
        FROM feedback_analysis''').fetchone()
    
    conn.close()
    
    return jsonify(dict(stats))

@app.route('/export', methods=['GET'])
def export_data():
    """Export analyzed data as CSV"""
    conn = get_db_connection()
    df = pd.read_sql_query('SELECT * FROM feedback_analysis ORDER BY priority_score DESC', conn)
    conn.close()
    
    output_path = 'exports/feedback_export.csv'
    os.makedirs('exports', exist_ok=True)
    df.to_csv(output_path, index=False)
    
    return send_file(output_path, as_attachment=True, download_name=f'feedback_{datetime.now().strftime("%Y%m%d")}.csv')

@app.route('/send-email', methods=['POST'])
def trigger_email():
    """Manually trigger email report"""
    try:
        send_weekly_email()
        return jsonify({"success": True, "message": "Email and Slack alert sent successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Scheduler for Weekly Collection & Emails ---
scheduler = BackgroundScheduler()
scheduler.add_job(func=collect_and_analyze_weekly, trigger="cron", day_of_week='mon', hour=9)
scheduler.start()

@app.route('/chat', methods=['POST'])
def chat():
    """AI chatbot that queries database directly"""
    try:
        # Add logging to debug
        print("📨 Received chat request")
        
        data = request.json
        print(f"📝 Request data: {data}")
        
        question = data.get('question', '')
        
        if not question:
            return jsonify({"success": False, "error": "No question provided"}), 400
        
        print(f"❓ Question: {question}")
        
        # Query database directly
        conn = get_db_connection()
        
        # Get stats
        total_feedback = conn.execute('SELECT COUNT(*) FROM feedback_analysis').fetchone()[0]
        
        urgency_stats = conn.execute('''
            SELECT urgency_level, COUNT(*) as count 
            FROM feedback_analysis 
            GROUP BY urgency_level
        ''').fetchall()
        
        sentiment_stats = conn.execute('''
            SELECT sentiment, COUNT(*) as count 
            FROM feedback_analysis 
            GROUP BY sentiment
        ''').fetchall()
        
        category_stats = conn.execute('''
            SELECT category, COUNT(*) as count 
            FROM feedback_analysis 
            GROUP BY category
        ''').fetchall()
        
        source_stats = conn.execute('''
            SELECT source, COUNT(*) as count 
            FROM feedback_analysis 
            GROUP BY source
        ''').fetchall()
        
        top_issues = conn.execute('''
            SELECT key_issue, category, priority_score, urgency_level 
            FROM feedback_analysis 
            ORDER BY priority_score DESC 
            LIMIT 5
        ''').fetchall()
        
        avg_priority = conn.execute('SELECT AVG(priority_score) FROM feedback_analysis').fetchone()[0]
        
        conn.close()
        
        # Build context
        context = f"""You are a helpful dashboard assistant. Answer questions about this feedback data concisely and friendly.

Current Dashboard Stats:
- Total Feedback: {total_feedback}

Urgency Breakdown:
"""
        
        for row in urgency_stats:
            context += f"- {row['urgency_level'].capitalize()}: {row['count']}\n"
        
        context += "\nSentiment Breakdown:\n"
        for row in sentiment_stats:
            context += f"- {row['sentiment'].capitalize()}: {row['count']}\n"
        
        context += "\nCategory Breakdown:\n"
        for row in category_stats:
            context += f"- {row['category']}: {row['count']}\n"
        
        context += "\nSources:\n"
        for row in source_stats:
            context += f"- {row['source']}: {row['count']}\n"
        
        avg_priority_formatted = f"{avg_priority:.1f}" if avg_priority else "0"
        context += f"\nAverage Priority Score: {avg_priority_formatted}\n"
        
        if top_issues:
            context += "\nTop 5 Priority Issues:\n"
            for idx, issue in enumerate(top_issues, 1):
                context += f"{idx}. {issue['key_issue']} ({issue['category']}) - Priority: {issue['priority_score']}\n"
        
        print("🔧 Calling Gemini API...")
        
        # Call Gemini
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""{context}

User Question: {question}

Answer based on the dashboard data above. Be concise and helpful. Use numbers and be specific. If asked about trends or patterns, analyze the data provided."""
        
        response = model.generate_content(prompt)
        answer = response.text
        
        print(f"✅ Response generated: {answer[:100]}...")
        
        return jsonify({
            "success": True,
            "answer": answer
        })
        
    except Exception as e:
        print(f"❌ Chat error: {e}")
        import traceback
        traceback.print_exc()
        
        # Return more specific error
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to process your question"
        }), 500
# --- Run Server ---
if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 Customer Feedback Prioritizer Server")
    print("="*60)
    print("📍 Server: http://localhost:5000")
    print("📊 Dashboard: http://localhost:5000/dashboard")
    print("📧 Email: Scheduled every Monday at 9 AM")
    print("💬 Slack: Enabled" if SLACK_WEBHOOK else "💬 Slack: Not configured")
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)