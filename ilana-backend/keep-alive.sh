#!/bin/bash
# Keep Render service alive by pinging every 10 minutes
while true; do
  curl -s https://ilanalabs-add-in.onrender.com/health > /dev/null
  echo "$(date): Pinged health endpoint"
  sleep 600  # 10 minutes
done
