# Gunicorn configuration for DigitalWill on Render
# Gunicorn automatically reads this file if present in the project root.

# Increase timeout so Gmail SMTP email sending doesn't get cut off
# Default is 30s — Gmail SMTP on cloud hosts can take 20-40s
timeout = 120

# Keep workers at 1 on Render free tier (512MB RAM limit)
workers = 1

# Use a single thread per worker — sufficient for this app
threads = 2
