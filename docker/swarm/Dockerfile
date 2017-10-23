FROM ubuntu:trusty

ENV DEBIAN_FRONTEND noninteractive

RUN /usr/bin/apt-get update
RUN /usr/bin/apt-get -y dist-upgrade
RUN /usr/bin/apt-get -y install curl
RUN /usr/bin/apt-get -y install sudo
RUN /usr/bin/apt-get -y install python

# Cleanup to shrink image sizes.
RUN /usr/bin/find /var/lib/apt/lists /tmp /var/tmp /usr/share/info \
    /usr/share/lintian /usr/share/man -maxdepth 1 -mindepth 1 -exec rm -rf {} \;
RUN /usr/bin/find /usr/share/doc -depth -type f ! -name copyright -exec rm -rf {} \;
RUN /usr/bin/find /usr/share/doc -depth -empty -exec rm -rf {} \;

RUN /bin/mkdir /opt/swarming_bootstrap
ADD start_swarm_bot.sh /opt/swarming_bootstrap/start_swarm_bot.sh
ADD shutdown.sh /sbin/shutdown
RUN /bin/chmod 0755 /sbin/shutdown
RUN echo "%chrome-bot ALL = NOPASSWD: /sbin/shutdown" > /etc/sudoers.d/chrome-bot

CMD ["/bin/bash", "/opt/swarming_bootstrap/start_swarm_bot.sh"]
