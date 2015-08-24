# Buildbot

Runs builds and tests. Enables Chromium CI and tryserver.

*   Locations
    *   Chromium: [master.chromium.win], [master.tryserver.chromium.linux], etc
    *   v8: [master.client.v8], [master.tryserver.v8], etc
    *   [go/chrome-infra-mastermap] for the full list
*   [External documentation](http://docs.buildbot.net/0.8.4p1/)
    *   Note that Chrome Infra uses a
        [modified](https://chromium.googlesource.com/chromium/tools/build/+log/master/third_party/buildbot_8_4p1)
        version of buildbot 0.8.4p1.
*   Safe to use for internal projects: yes
*   Owner: infra-dev@chromium.org, chrome-infrastructure-team@google.com

## Configuration

Master configurations are stored in
[build/masters/](https://chromium.googlesource.com/chromium/tools/build/+/master/masters/)
and [build_internal/masters/](https://chrome-internal.googlesource.com/chrome/tools/build/+/master/masters/)

New masters are typically configured using [builders.pyl](builders.pyl.md).

Build/test scripts are written using [recipes](../../recipes.md).

## Security

Groups of buildbot masters are isolated from each other by VLANs.
Buildbot masters and slaves within the same VLAN have network access to each
other.

## Limitations

* Buildbot does not scale with the number of builds, slaves or amount of build
  logs.
* Buildbot master has to be restarted on every configuration change.

## See also

* [go/botmap]: list of all build slaves.
* [FAQ](faq.md)
* [builders.pyl](builders.pyl.md): simpler builder configuration
* [Infra steps in the builds](steps.md)

[master.chromium.win]: https://build.chromium.org/p/chromium.win
[master.tryserver.chromium.linux]: https://build.chromium.org/p/tryserver.chromium.linux
[master.client.v8]: https://build.chromium.org/p/client.v8
[master.tryserver.v8]: https://build.chromium.org/p/tryserver.v8
[go/chrome-infra-mastermap]: http://go/chrome-infra-mastermap
[go/botmap]: http://go/botmap
