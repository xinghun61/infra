# TODO(bpastene): Remove this file and use the Dockerfile in the parent dir.
FROM ubuntu:xenial

ENV DEBIAN_FRONTEND noninteractive
ENV CHROMIUM_REV e41aeaed051c8cc401e0bce2a6d57dcc330808e6

RUN /usr/bin/apt-get update
RUN /usr/bin/apt-get -y dist-upgrade
# parted needed by cros' flashing tool. See crbug.com/996792.
RUN /usr/bin/apt-get -y install lsb-release curl iputils-ping locales lsof \
      parted sshpass sudo udev usbutils wget

RUN echo 'ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true' \
      | /usr/bin/debconf-set-selections
RUN echo 'msttcorefonts msttcorefonts/defoma select note' \
      | /usr/bin/debconf-set-selections

RUN /usr/sbin/locale-gen en_US.UTF-8
RUN /usr/sbin/update-locale
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

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
RUN /usr/bin/find /var/lib/apt/lists /tmp /var/tmp /usr/share/info \
      /usr/share/lintian /usr/share/man -maxdepth 1 -mindepth 1 -exec rm -rf {} \;
RUN /usr/bin/find /usr/share/doc -depth -type f ! -name copyright -exec rm -rf {} \;
RUN /usr/bin/find /usr/share/doc -depth -empty -exec rm -rf {} \;

RUN /bin/mkdir /opt/swarming_bootstrap
ADD start_swarm_bot.sh /opt/swarming_bootstrap/start_swarm_bot.sh
# /sbin/shutdown is a symlink to /bin/systemctl, and ADDing a file at a symlink
# replaces the target of the symlink. So remove the symlink first before adding
# shutdown.sh so we don't end up replacing /bin/systemctl.
RUN /bin/rm /sbin/shutdown
ADD shutdown.sh /sbin/shutdown
RUN /bin/chmod 0755 /sbin/shutdown
RUN echo "%chrome-bot ALL = NOPASSWD: /sbin/shutdown" > /etc/sudoers.d/chrome-bot

CMD ["/bin/bash", "/opt/swarming_bootstrap/start_swarm_bot.sh"]
