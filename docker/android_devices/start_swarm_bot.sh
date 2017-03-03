#!/bin/bash -x

SWARM_DIR=/b/swarming
SWARM_URL="https://chromium-swarm.appspot.com/bot_code"
SWARM_ZIP=swarming_bot.zip

DEPOT_TOOLS_DIR=/b/depot_tools
DEPOT_TOOLS_URL="https://chromium.googlesource.com/chromium/tools/depot_tools.git"
DEPOT_TOOLS_REV="da3a29e13e816459234b0b08ed1059300bae46dd"

# Wait until this container has access to a device before starting the bot.
while [ ! -d /dev/bus/usb ]
do
  echo "Waiting for an available usb device..."
  sleep 10
done

# Some chromium tests need depot tools.
mkdir -p $DEPOT_TOOLS_DIR
/bin/chown chrome-bot:chrome-bot $DEPOT_TOOLS_DIR
/bin/su -c "cd $DEPOT_TOOLS_DIR && \
            /usr/bin/git init && \
            /usr/bin/git remote add origin $DEPOT_TOOLS_URL ; \
            /usr/bin/git fetch origin $DEPOT_TOOLS_REV && \
            /usr/bin/git reset --hard FETCH_HEAD" chrome-bot

mkdir -p $SWARM_DIR
/bin/chown chrome-bot:chrome-bot $SWARM_DIR
cd $SWARM_DIR
/bin/su -c "/usr/bin/curl -sSLOJ $SWARM_URL" chrome-bot

echo "Starting $SWARM_ZIP"
/bin/su -c "/usr/bin/python $SWARM_ZIP start_bot" chrome-bot
