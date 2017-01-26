#!/bin/bash

SWARM_DIR=/b/swarming
SWARM_URL="https://chromium-swarm.appspot.com/bot_code"
SWARM_ZIP=swarming_bot.zip

# Wait until this container has access to a device before starting the bot.
while [ ! -d /dev/bus/usb ]
do
  echo "Waiting for an available usb device..."
  sleep 10
done

mkdir -p $SWARM_DIR
/bin/chown chrome-bot:chrome-bot $SWARM_DIR
cd $SWARM_DIR
/bin/su -c "/usr/bin/curl -sSLOJ $SWARM_URL" chrome-bot

echo "Starting $SWARM_ZIP"
/bin/su -c "/usr/bin/python $SWARM_ZIP start_bot" chrome-bot
