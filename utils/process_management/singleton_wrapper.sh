#!/bin/bash
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

###
# A program wrapper that disallows multiple instances of the given program.
#
# It can optionally send email alerts about unintended instance conflicts.
#
# Sample Usage:
#
# No alerts, just prevent multiple instances:
# ./singleton_wrapper.sh sleep 10
#
# Default alerts - stderr output, 10 minute instance timeout:
# ALERT_ON_LOCKED=1 ./singleton_wrapper.sh sleep 10
#
# Email alerts on every instance conflict (no timeout):
# ALERT_EMAIL_RCPTS=chrome-troopers@google.com ALERT_ON_LOCKED=1 \
#   ALERT_THROTTLE=0 ./singleton_wrapper.sh sleep 10
###

# Trigger an alert when there is an existing program instance.
# If set to 0, alerts will be disabled. Disabling is useful for watchdog
# cronjobs, which expect the program to be running and just want to restart it
# if it dies.
ALERT_ON_LOCKED=${ALERT_ON_LOCKED:-0}

# Number of seconds to allow a program to be locked before printing an alert.
# This can be used to prevent frequently run cronjobs from sending alert emails
# on every run, in case it's OK for previous instances to "spill over".
ALERT_THROTTLE=${ALERT_THROTTLE:-600}

# Use internal email mechanism to send alerts to the given list of recipients.
# If not set, alerts are printed on stderr. Setting this allows nicer formatting
# of alert messages when run from cronjobs, instead of defaulting to cron's
# boilerplate emails.
ALERT_EMAIL_RCPTS=${ALERT_EMAIL_RCPTS:-}

# A unique identifier for the program being run.
# The default is to use the first argument of the wrapped command, but if that's
# not reasonably unique (e.g. 'python foo.py' would use 'python'), then a
# PROGRAM_NAME should be specified such that it's less likely to conflict with
# the lock files of other wrapped programs (e.g. 'foo.py' would be better).
PROGRAM_NAME="${PROGRAM_NAME:-$1}"


if [ -z "$1" ]; then
  echo "ERROR: Please specify a program to wrap."
  exit 1
fi

LOCKFILE=/var/run/lock/"$LOGNAME.$PROGRAM_NAME"
(
  flock -n -x 200
  if [ $? != 0 ]; then
    if [ "$ALERT_ON_LOCKED" != "0" ]; then
      SENDMAIL=$(which sendmail)
      NOWTIME=$(date +"%s")
      LOCKTIME=$(stat -c %Y "$LOCKFILE")
      DIFFTIME=$(($NOWTIME - $LOCKTIME))
      if [ "$DIFFTIME" -gt "$ALERT_THROTTLE" ]; then
        PID=$(cat "$LOCKFILE")
        MSG="WARNING: Cannot execute '$@'\n"
        MSG+="Previous instance [$PID] has been "
        MSG+="running for $DIFFTIME seconds."
        if [ -n "$ALERT_EMAIL_RCPTS" ] && [ -n "$SENDMAIL" ]; then
          SENDER=$LOGNAME@$(hostname -f)
(
cat <<!
From: $SENDER
To: $ALERT_EMAIL_RCPTS
Subject: Locked Process on $HOSTNAME: $@ [pid $PID]

$(echo -e "$MSG")
!
) | $SENDMAIL -t -f $SENDER
        else
          echo -e "$MSG" >&2
        fi
        exit 2  # previous instance, alert triggered
      fi
      exit 1  # previous instance, not timed out, no alert
    fi
    exit 0  # previous instance, no alert (not an error)
  fi  # no previous isntance

  # Run the wrapped program.
  "$@" &
  # Store the program PID in the lock file for alert message.
  echo -n $! > "$LOCKFILE"
  # Wait for the program to exit.
  wait

  # Truncate the lock file to clear the PID for the next run.
  >"$LOCKFILE"

# Use >> to prevent changes to the lock file modification time on unsuccessful
# runs, which would otherwise throw off the DIFFTIME calculations.
) 200>>"$LOCKFILE"
