import sqlite3

conn = sqlite3.connect('feedback.db')
conn.execute('ALTER TABLE feedback_analysis ADD COLUMN source TEXT')
conn.execute('ALTER TABLE feedback_analysis ADD COLUMN timestamp TEXT')
conn.commit()
conn.close()
print("Done")