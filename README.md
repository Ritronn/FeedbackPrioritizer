# Customer Feedback Prioritizer

An AI-powered system that helps product teams automatically analyze, categorize, and prioritize customer feedback from multiple sources, delivering actionable insights through an interactive dashboard and automated weekly reports.

## Problem Statement

Product teams receive thousands of feedback entries from surveys, in-app feedback, social media, and support tickets. Manually sorting through this data to identify critical issues is time-consuming and often leads to important feedback being overlooked.

**This system solves that by:**
- Automatically analyzing feedback using AI (Gemini 2.0 Flash)
- Categorizing by urgency (critical/high/medium/low) and impact
- Highlighting top pain points with suggested actions
- Delivering prioritized reports weekly via Slack and Email

## Core Features

### 1. CSV Upload & Analysis
- Upload CSV files containing customer feedback from any source
- AI-powered analysis categorizes each entry by:
  - Sentiment (positive/negative/neutral)
  - Category (Bug/Feature Request/UX Issue/Performance/Pricing/Other)
  - Urgency Level (critical/high/medium/low)
  - Priority Score (0-100)
- View detailed analysis on interactive dashboard
- Manually trigger Slack/Email reports

### 2. Automated Multi-Source Data Collection
**Supported Sources:**
- **Reddit**: Collect feedback from specific subreddits using keyword search
- **Google Sheets**: Import feedback from Google Forms responses

**How it works:**
- Configure data sources through the API
- System automatically collects feedback weekly (every Monday at 9 AM)
- AI analyzes and prioritizes all collected feedback
- Automated reports sent via Slack and Email

### 3. AI-Powered Dashboard Chatbot
- Ask questions about your feedback data in natural language
- Powered by Gemini 2.0 Flash
- Example queries:
  - "How many total feedbacks do we have?"
  - "What are the top 3 critical issues?"
  - "Show me sentiment breakdown"
  - "What's the average priority score?"

## Tech Stack

### Backend
- **Flask** - REST API server
- **SQLite** - Database for storing analyzed feedback
- **Gemini 2.5 Flash** - AI analysis and chatbot
- **APScheduler** - Weekly automated tasks
- **SendGrid** - Email delivery
- **Slack Webhooks** - Instant notifications

### Frontend
- **React** - Interactive dashboard UI
- **Chart.js / Recharts** - Data visualizations

### Data Collection
- **PRAW** - Reddit API integration
- **gspread** - Google Sheets API integration

## Installation

### Prerequisites
- Python 3.8+
- Node.js 16+
- Gemini API Key
- SendGrid API Key (for email)
- Slack Webhook URL (for notifications)

### Backend Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd feedback-prioritizer/backend
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```env
# AI Configuration
GEMINI_API_KEY=your_gemini_api_key

# Email Configuration (SendGrid)
SENDGRID_API_KEY=your_sendgrid_api_key
SENDER_EMAIL=verified_sender@yourdomain.com
RECIPIENT_EMAIL=team@company.com

# Slack Configuration
SLACK_WEBHOOK_URL=your_slack_webhook_url

# Reddit API (Optional)
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=your_app_name


# Server Configuration
PORT=5000

```

5. Run the server:
```bash
python app.py
```

Server will start at `http://localhost:5000`

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd ../frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create `.env` file:
```env
REACT_APP_API_URL=http://localhost:5000
```

4. Start development server:
```bash
npm start
```

Frontend will open at `http://localhost:3000`

## Key API Endpoints

#### Upload CSV
```http
POST /upload
```
Upload CSV file for AI analysis

#### Get Dashboard Data
```http
GET /dashboard
```
Returns all feedback statistics and top priority issues

## CSV Format

Your CSV file should have these columns:

| Column | Required | Description |
|--------|----------|-------------|
| `id` | No (auto-generated) | Unique identifier |
| `feedback_text` | Yes | The actual feedback content |
| `source` | No (defaults to "CSV Upload") | Source of feedback (e.g., "Survey", "Twitter") |

**Example CSV:**
```csv
id,feedback_text,source
1,"The app crashes when I try to export data",Support Ticket
2,"Love the new dark mode feature!",In-App Survey
3,"Please add bulk editing capability",Feature Request Form
```

## Automated Weekly Reports

The system automatically:
1. Collects feedback from configured sources (Reddit, Google Sheets)
2. Analyzes with Gemini AI
3. Sends reports every Monday at 9 AM

**Report includes:**
- Top 10 priority issues
- Category breakdown
- Urgency statistics
- Suggested actions

## Priority Scoring Rules

The AI uses these guidelines:
- **80-100**: Critical bugs with negative sentiment
- **60-79**: High impact issues blocking users
- **40-59**: UX improvements and feature requests
- **0-39**: Minor issues and positive feedback

## Database Schema

### feedback_analysis table
```sql
CREATE TABLE feedback_analysis (
    id INTEGER PRIMARY KEY,
    feedback_id INTEGER,
    feedback_text TEXT,
    source TEXT,
    sentiment TEXT,
    sentiment_score REAL,
    category TEXT,
    urgency_level TEXT,
    priority_score INTEGER,
    key_issue TEXT,
    suggested_action TEXT,
    created_at TIMESTAMP
);
```

### data_sources table
```sql
CREATE TABLE data_sources (
    id INTEGER PRIMARY KEY,
    reddit_subreddit TEXT,
    reddit_query TEXT,
    google_sheet_url TEXT,
    enabled BOOLEAN,
    last_synced TIMESTAMP,
    created_at TIMESTAMP
);
```

## Deployment

### Railway Deployment

1. Create a Railway account
2. Create new project from GitHub repo
3. Add environment variables in Railway dashboard
4. Add a volume for persistent storage at `/data`
5. Deploy

Railway will automatically:
- Install dependencies from `requirements.txt`
- Run `app.py`
- Provide a public URL

## Project Structure
```
feedback-prioritizer/
├── backend/
│   ├── app.py              # Flask server
│   ├── gemini_agent.py     # AI analysis logic
│   ├── data_collectors.py  # Reddit/Sheets integration
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── App.js
│   │   └── index.js
│   ├── package.json
│   └── .env
└── README.md
```

## Roadmap

- [ ] Add more data sources (Twitter, Discord, Zendesk)
- [ ] Sentiment trend analysis over time
- [ ] Custom priority scoring rules
- [ ] Multi-language support
- [ ] Integration with Jira/Linear for ticket creation
- [ ] Real-time notifications for critical issues
