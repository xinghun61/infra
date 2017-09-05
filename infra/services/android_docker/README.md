The script here is used to manage the containers on android swarming bots.
By design, it's stateless and event-driven. It has two modes of execution:
* `launch`: Ensures every locally connected android device has a running
          container. On the bots, it's called every 5 minutes via cron.
* `add_device`: Gives a device's container access to its device. Called every
              time a device appears/reappears on the system via udev.

It's intended to be run in conjucture with the android_docker container image.
More information on the image can be found [here](https://chromium.googlesource.com/infra/infra/+/master/docker/android_devices/README.md).


Launching the containers
--------------------------
Every 5 minutes, this script is invoked with the `launch` argument. This is
how the containers get spawned, shut down, and cleaned up. Essentially, it does
the following:
* Gracefully shutdowns each container if container uptime is too high (default
4 hours) or host uptime is too high (default 24 hours).
* Scans the USB bus for any connected android device and creates a container
for each one.


Adding a device to a container
--------------------------
On linux, docker limits containers to their set of resources via
[cgroups](https://www.kernel.org/doc/Documentation/cgroup-v1/devices.txt)
(e.g. memory, network, etc.) Since cgroups extend support for
[devices](https://www.kernel.org/doc/Documentation/cgroup-v1/devices.txt),
we can leverage this to add an android device to a container. This is done via
adding the device's descriptor to the container's cgroup and creating a
[device node](https://linux.die.net/man/8/makedev) in the container's /dev
filesystem. All of this is done when invoking the script with the `add_device`
argument.

Everytime a device reboots or resets, it momentarily dissapears from the host.
When this happens, many things that uniquely identify the device change. This
includes its [major and minor numbers](http://www.makelinux.net/ldd3/chp-3-sect-2)
and its [dev and bus numbers](http://www.makelinux.net/ldd3/chp-13-sect-2).
Consequently, we need to re-add a device to its container everytime this
happens. [udev](https://www.kernel.org/pub/linux/utils/kernel/hotplug/udev/udev.html)
allows us to do this by running `add_device` everytime an android device
appears on the host.


Gracefully shutting down a container
--------------------------
To preform various forms of maintenance, the script here gracefully shuts down
containers and, by association, the swarming bot running inside them. This is
done by sending SIGTERM to the swarming bot process. This alerts the swarming
bot that it should quit at the next available opportunity (ie: not during a
test.)
In order to fetch the pid of the swarming bot, the script runs `lsof` on the
[swarming.lck](https://cs.chromium.org/chromium/infra/luci/appengine/swarming/doc/Bot.md?rcl=8b90cdd97f8f088bcba2fa376ce49d9863b48902&l=305)
file.


Fetching the docker image
--------------------------
When a new container is launched with an image that is missing
on a bot's local cache, it pulls it from the specified container registry. By
default, this is the gcloud registry [chromium-container-registry](https://console.cloud.google.com/gcr/images/chromium-container-registry/GLOBAL/android_docker).
It authenticates with the registry before downloading by using the specified
credentials file (default is
/creds/service_accounts/service-account-container_registry_puller.json)


File locking
--------------------------
To avoid multiple simultaneous invocations of this service from stepping
on itself (there are a few race conditions exposed when a misbehaving device is
constantly connecting/disconnecting), parts of the script are wrapped in a mutex
via a flock. The logic that's protected includes:
* scanning the USB bus (wrapped in a global flock)
* any container interaction (wrapped in a device-specific flock)


Getting device list
--------------------------
py-libusb is used to fetch a list of locally connected devices, which is part
of infra's [virtual env](https://chromium.googlesource.com/infra/infra/+/6446cbcd46452cf657e67bd7a45e9f0a97b0f5c8/bootstrap/deps.pyl#209).
This library wraps the [libusb system lib](http://www.libusb.org/) and provides
methods for fetching information about USB devices.


Deploying the script
--------------------------
The script and its dependencies are deployed as a CIPD package via puppet. The
package (infra/android_docker/$platform) is continously built on this
[bot](https://build.chromium.org/p/chromium.infra/builders/infra-continuous-precise-64).
Puppet deploys it to the relevant bots at
[these revisions](https://chrome-internal.googlesource.com/infra/puppet/+/78f1ba25470edf4256e5862d7b9c3eb1fba9dcad/puppetm/etc/puppet/hieradata/cipd.yaml#387).
The canary pin affects bots on [chromium-swarm-dev](https://chromium-swarm-dev.appspot.com),
which the android testers on the [chromium.swarm](https://build.chromium.org/p/chromium.swarm/builders)
waterfall run tests against. If the canary has been updated, the bots look fine,
and the tests haven't regressed, you can proceed to update the stable pin.

The call sites of the script are also defined in puppet:
* [cron](https://chrome-internal.googlesource.com/infra/puppet/+/78f1ba25470edf4256e5862d7b9c3eb1fba9dcad/puppetm/etc/puppet/modules/chrome_infra/templates/setup/docker/android/android_docker_cron.sh.erb)
* [udev](https://chrome-internal.googlesource.com/infra/puppet/+/78f1ba25470edf4256e5862d7b9c3eb1fba9dcad/puppetm/etc/puppet/modules/chrome_infra/files/setup/docker/android/android_docker_udev)
