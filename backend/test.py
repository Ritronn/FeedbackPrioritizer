import sqlite3
conn = sqlite3.connect('feedback.db')
result = conn.execute('SELECT reddit_subreddit, reddit_query FROM data_sources ORDER BY id DESC LIMIT 1').fetchone()
print(f"Subreddit: {result[0]}, Query: {result[1]}")
conn.close()