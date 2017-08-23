FROM ubuntu:xenial

ENV DEBIAN_FRONTEND noninteractive
ENV CHROMIUM_REV e41aeaed051c8cc401e0bce2a6d57dcc330808e6

RUN /usr/bin/apt-get update
RUN /usr/bin/apt-get -y dist-upgrade
RUN /usr/bin/apt-get -y install wget
RUN /usr/bin/apt-get -y install curl
RUN /usr/bin/apt-get -y install usbutils
RUN /usr/bin/apt-get -y install lsb-release
RUN /usr/bin/apt-get -y install sudo
RUN /usr/bin/apt-get -y install lsof

RUN echo 'ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true' \
      | /usr/bin/debconf-set-selections
RUN echo 'msttcorefonts msttcorefonts/defoma select note' \
      | /usr/bin/debconf-set-selections

RUN /bin/mkdir /tmp/setup-deps
RUN /usr/bin/wget -O- \
      "https://chromium.googlesource.com/chromium/src/+/${CHROMIUM_REV}/build/install-build-deps.sh?format=TEXT" \
        | /usr/bin/base64 -d \
        > /tmp/setup-deps/install-build-deps.sh
RUN /usr/bin/wget -O- \
      "https://chromium.googlesource.com/chromium/src/+/${CHROMIUM_REV}/build/install-build-deps-android.sh?format=TEXT" \
        | /usr/bin/base64 -d \
        > /tmp/setup-deps/install-build-deps-android.sh
RUN /bin/chmod a+x /tmp/setup-deps/install-build-deps*.sh
# This runs install-build-deps.sh as well.
RUN /bin/bash -x /tmp/setup-deps/install-build-deps-android.sh

# Cleanup to shrink image sizes.
RUN /usr/bin/find /var/lib/apt/lists /tmp /var/tmp /var/cache/man \
      /usr/share/groff /usr/share/info /usr/share/lintian  \
      /usr/share/man -maxdepth 1 -mindepth 1 -exec rm -rf {} \;
RUN /usr/bin/find /usr/share/doc -depth -type f ! -name copyright -exec rm -rf {} \;
RUN /usr/bin/find /usr/share/doc -depth -empty -exec rm -rf {} \;

RUN /bin/mkdir /opt/swarming_bootstrap
ADD start_swarm_bot.sh /opt/swarming_bootstrap/start_swarm_bot.sh
ADD shutdown.sh /sbin/shutdown
RUN /bin/chmod 0755 /sbin/shutdown
RUN echo "%chrome-bot ALL = NOPASSWD: /sbin/shutdown" > /etc/sudoers.d/chrome-bot

CMD ["/bin/bash", "/opt/swarming_bootstrap/start_swarm_bot.sh"]
