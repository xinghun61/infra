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
infra-dev@chromium.org with estaab@chromium.org, efoo@chromium.org and nodir@chromium.org CCed.

**Dogfood users:** If for some reason any of the LUCI builders fails and you
suspect it's an issue with LUCI and would pass on Buildbot, please file a bug using
[bug template](https://bugs.chromium.org/p/chromium/issues/entry?labels=LUCI-ClosedBeta-Bug&components=Infra%3EPlatform&summary=%5BLUCI-Beta-Bug%5D%20Enter%20an%20one-line%20summary&cc=nodir@chromium.org,%20estaab@chromium.org,%20efoo@chromium.org&description=Please%20use%20this%20to%20template%20to%20describe%20the%20issue%20you%20are%20encountering%20with%20LUCI.%0A%0AInclude%20the%20following%20information%20in%20this%20bug%3A%0A-%20Problem%2FBug%0A-%20Relevant%20LUCI%20builder%0A-%20Links%20i.e.%20links%20to%20a%20failing%20CL%0A-%20Expected%20outcome%0A%0AIn%20addition%2C%20please%20clearly%20specify%20the%20priority%2Fseverity%20of%20your%20issue.%20).
We're really interested in your feedback so please don't hesitate to send
along any feedback whether it's good or bad via email or file for an feature
improvement or request using
[feedback template](https://bugs.chromium.org/p/chromium/issues/entry?labels=LUCI-ClosedBeta-Feedback&components=Infra%3EPlatform&summary=%5BLUCI-Beta-Feedback%5D%20Enter%20an%20one-line%20summary&cc=nodir@chromium.org,%20estaab@chromium.org,%20efoo@chromium.org&description=Please%20use%20this%20to%20template%20to%20share%20your%20feedback.%20Do%20not%20hesitate%20whether%20it%27s%20good%20or%20bad.%0A%0AThank%20you!).
