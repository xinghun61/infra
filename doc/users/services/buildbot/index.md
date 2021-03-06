# Buildbot

> **Buildbot end of life date is March 1, 2019**. As of [March 1](buildbot_eol.md), all Chromium/Chrome builds hosted on [chromium.org](https://www.chromium.org) will be running on LUCI.

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

For BuildBot-related issues, please contact an infrastructure team member. To
request BuildBot restarts or maintenance, file a trooper bug at
[g.co/bugatrooper](http://g.co/bugatrooper).

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

## Draining

Prior to restarting BuildBot, it is a good practice to drain it first. Draining
a BuildBot master instructs it to refrain from scheduling new builds, but allows
it to complete any currently-scheduled builds.

Masters are typically drained by
[master_manager](https://chromium.googlesource.com/infra/infra/+/master/infra/tools/master_manager)
during its restart cycle. First, a master will be drained in an effort to allow
existing builds to terminate. If all current builds finish, or if a cutoff
threshold has been exceeded, `master_manager` will restart the master. When it
comes back up, any builds that were accumulated during the previous drain will
now be candidate for scheduling, and the master will operate normally.

While a BuildBot master is draining, it may appear to be slow or broken. This is
an expected behavior if the master is undergoing a restart procedure. Some
masters will explicitly note when they are being drained. To determine if a
BuildBot master is being drained, visit its `/json/accepting_builds?as_text=1`
endpoint.

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
