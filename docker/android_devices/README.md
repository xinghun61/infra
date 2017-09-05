The files here are used to build a docker image suitable for sandboxing a USB
device into its own execution environment, in which a swarming bot is running.
More information is at [go/one-device-swarming](http://go/one-device-swarming)


The docker image
--------------------------
The `build.sh` script will create a local image named `android_docker` tagged
with the date and time of creation. The image itself is simply an Ubuntu
flavor (xenial as of writing this) with a number of packages and utilities
installed, mainly via chromium's [install_build_deps.sh](https://chromium.googlesource.com/chromium/src/+/master/build/install-build-deps.sh).
When launched as a container, this image is configured to run the
[start_swarm_bot.sh](https://chromium.googlesource.com/infra/infra/+/master/docker/android_devices/start_swarm_bot.sh)
script here which fetches and runs the bot code of the swarming server pointed
to by the `$SWARM_URL` env var. Note that running the image locally on a
developer workstation is unsupported.

### Automatic image building
Everyday at 8am PST, a builder on the internal.infra.cron waterfall builds a
fresh version of the image. This [builder](https://uberchromegw.corp.google.com/i/internal.infra.cron/builders/android-docker-image-builder)
essentially runs `./build.sh` and uploads the resultant image to a docker
[container registry](https://docs.docker.com/registry/). The registry, hosted
by gcloud, is located at
[chromium-container-registry](https://console.cloud.google.com/gcr/images/chromium-container-registry/GLOBAL/android_docker).

### Bumping src-rev for install-build-deps.sh
Many of the packages and dependencies needed to build and test chromium are
installed via the [install_build_deps.sh](https://chromium.googlesource.com/chromium/src/+/master/build/install-build-deps.sh)
script in src. If the image is missing a dependency, chances are its src pin is
out of date. To update it, simply change the pin located
[here](https://cs.chromium.org/chromium/infra/docker/android_devices/Dockerfile?rcl=ca6275d670533aaf5303bd2c785cb7366fbe3193&l=4)
and rebuild.

### Shutting container down from within
Because a swarming bot may trigger a reboot of the bot at any time (see
[docs](https://cs.chromium.org/chromium/infra/luci/appengine/swarming/doc/Magic-Values.md?rcl=8b90cdd97f8f088bcba2fa376ce49d9863b48902&l=65)),
it should also be able to shut its container down from within. By conventional
means, that's impossible; a container has no access to the docker engine
running outside of it. Nor can it run many of the utilities in `/sbin/` since
the hardware layer of the machine is not available to the container. However,
because a swarming bot uses the `/sbin/shutdown` executable to reboot, this
file is replaced with our own bash script here
([shutdown.sh](https://chromium.googlesource.com/infra/infra/+/master/docker/android_devices/shutdown.sh))
that simply sends SIGUSR1 to `init` (pid 1). For a container, `init` is whatever
command the container was configured to run (as opposed to actual `/sbin/init`).
In our case, this is [start_swarm_bot.sh](https://chromium.googlesource.com/infra/infra/+/master/docker/android_devices/start_swarm_bot.sh),
which conveniently traps SIGUSR1 at the very beginning and exits upon catching
it. Consequently, running `/sbin/shutdown` from within a container will cause
the container to immediately shutdown.


Image deployment
--------------------------
Image deployment is done via puppet. When a new image needs to be rolled out,
grab the image name in the step-text of the "Push image" step on the
[image-building bot](https://uberchromegw.corp.google.com/i/internal.infra.cron/builders/android-docker-image-builder).
It should look like android_docker:$date. (The bot runs once a day, but you can
manually trigger a build if you don't want to wait.) To deploy, update the
image pins in puppet for [canary bots](https://chrome-internal.googlesource.com/infra/puppet/+/78f1ba25470edf4256e5862d7b9c3eb1fba9dcad/puppetm/opt/puppet/conf/nodes.yaml#718),
followed by [stable bots](https://chrome-internal.googlesource.com/infra/puppet/+/78f1ba25470edf4256e5862d7b9c3eb1fba9dcad/puppetm/opt/puppet/conf/nodes.yaml#777).
The canary pin affects bots on [chromium-swarm-dev](https://chromium-swarm-dev.appspot.com),
which the android testers on the [chromium.swarm](https://build.chromium.org/p/chromium.swarm/builders)
waterfall run tests against. If the canary has been updated, the bots look fine,
and the tests haven't regressed, you can proceed to update the stable pin.
(Note that it may take several hours for the image pin update to propagate. It's
advised to wait at least a day to update stable after updating canary.)

Launching the containers
------------------------
On the bots, container launching and managing is controlled via the python
service [here](https://chromium.googlesource.com/infra/infra/+/master/infra/services/android_docker/).
The service has two modes of invocation:
* launch: Ensures every locally connected android device has a running
          container. Will gracefully tear down containers that are too old or
          reboot the host. Called every 5 minutes via cron.
* add_device: Give's a device's container access to its device. Called every
              time a device appears/reappears on the system via udev.

More information can be found [here](https://chromium.googlesource.com/infra/infra/+/master/infra/services/android_docker/README.md).
