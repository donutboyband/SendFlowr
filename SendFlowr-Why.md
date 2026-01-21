# Why SendFlowr 

SendFlowr is a technical project focused on figuring out the best time to send emails to each person, using real event data and a lot of moving parts. Most email tools just pick a "best hour" based on simple stats for aggregating users into "engagement blocks", but that misses a lot of nuance in how people actually behave.

SendFlowr tries to:
- Tracks user activity from webhook integrations at a minute-by-minute level, not just by the hour or day
- Builds probability curves for engagement based on real events (opens, clicks, site visits, etc.)
- Updates its predictions in real time as new data comes in
- Handles identity resolution by stitching together emails, phone numbers, and various platform IDs
- Uses Kafka for real-time event streaming and ClickHouse for fast analytics
- Connects multiple services (Python, C#, databases) with Docker Compose
- Uses ML to predict latency per-platform (to calculate a "trigger offset" to land an email at an exact moment)
