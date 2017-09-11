# LUCI

<!-- This document is linked from "LUCI" chip in Gerrit-Buildbucket integration.
https://chromium.googlesource.com/infra/gerrit-plugins/buildbucket/+/master/src/main/resources/static/cr-build-block.html
For some users, this is the very first LUCI documentation they see.
-->

LUCI is a Buildbot replacement.
Unlike monolithic single-threaded Buildbot, it is a distributed system
consisting of a few cloud services.
The core, build dispatch to bots, is based by Swarming.

As of September 2017, LUCI is under heavy development and being slowly
rolled out, builder by builder, first to dogfooders and then the rest of
Chromium.

If you have questions, please contact luci-eng@google.com, or
infra-dev@chromium.org with estaab@chromium.org and nodir@chromium.org CCed.
Please file issues using
[this template](https://bugs.chromium.org/p/chromium/issues/entry?labels=luci&components=Infra%3EPlatform&summary=&comment=).
