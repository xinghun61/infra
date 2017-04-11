#!/bin/bash -x

trap "exit 10" SIGUSR1

SWARM_DIR=/b/swarming
SWARM_ZIP=swarming_bot.zip

DEPOT_TOOLS_DIR=/b/depot_tools
DEPOT_TOOLS_URL="https://chromium.googlesource.com/chromium/tools/depot_tools.git"
DEPOT_TOOLS_REV="da3a29e13e816459234b0b08ed1059300bae46dd"

# Wait until this container has access to a device before starting the bot.
START=$(/bin/date +%s)
TIMEOUT=$((60*5))
while [ ! -d /dev/bus/usb ]
do
  now=$(/bin/date +%s)
  if [[ $((now-START)) -gt $TIMEOUT ]]; then
    echo "Timed out while waiting for an available device. Quitting early." 1>&2
    exit 1
  else
    echo "Waiting for an available usb device..."
    sleep 10
  fi
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
rm -rf swarming_bot*.zip
/bin/su -c "/usr/bin/curl -sSLOJ $SWARM_URL" chrome-bot

echo "Starting $SWARM_ZIP"
# Run the swarming bot in the background, and immediately wait for it. This
# allows the signal trapping to actually work.
/bin/su -c "/usr/bin/python $SWARM_ZIP start_bot" chrome-bot &
wait %1
exit $?
