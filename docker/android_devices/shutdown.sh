#!/bin/bash

# This script replaces /sbin/shutdown in the container which allows it to
# actually shutdown the contianer. It does this by sending SIGTERM to pid 1,
# which conveniently is the start_swarm_bot.sh script that explicitly traps that
# signal and exits.

kill -s SIGUSR1 1
