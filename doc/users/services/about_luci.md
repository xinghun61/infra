# Welcome to LUCI!

<!-- This document is linked from "LUCI" chip in Gerrit-Buildbucket integration.
https://chromium.googlesource.com/infra/gerrit-plugins/buildbucket/+/master/src/main/resources/static/cr-build-block.html
For some users, this is the very first LUCI documentation they see.
-->

LUCI is a replacement for Buildbot that runs primarily on
the Google Cloud Platform and is designed to scale well for large projects.

## Current Status

LUCI is under heavy development and being slowly rolled out in phases.
Opting into the LUCI beta means a subset of your CQ builders will run on LUCI.

You'll know it's a LUCI builder because it will show a LUCI chip in Gerrit:

![LUCI chip in Gerrit](../../images/luci_chip.png)

## Interested in joining the beta?

If you're interested in getting an early preview of LUCI for your CQ jobs,
please sign up on [this](https://goo.gl/forms/vN44OtarVRD1HZ8r2) form!

Don't worry, if you're in the beta and there is a problem,
there is an easy way to bypass LUCI.

### Bypassing LUCI

You can have your CL switch back to using Buildbot builders
by adding to your CL [description footer](https://chromium-review.googlesource.com/c/chromium/src/+/541299/4..5//COMMIT_MSG)

```
No-Equivalent-Builders: true
```

## Feedback

Enjoy LUCI! We're really interested in your feedback so please
don't hesitate to send it whether good or bad via [email](luci-eng@google.com)
or [on the bug tracker](https://bugs.chromium.org/p/chromium/issues/entry?labels=LUCI-ClosedBeta-Bug&components=Infra%3EPlatform&summary=%5BLUCI-Beta-Bug%5D%20Enter%20an%20one-line%20summary&cc=nodir@chromium.org,%20estaab@chromium.org,%20efoo@chromium.org&description=Please%20use%20this%20to%20template%20to%20describe%20the%20issue%20you%20are%20encountering%20with%20LUCI.%0A%0AInclude%20the%20following%20information%20in%20this%20bug%3A%0A-%20Problem%2FBug%0A-%20Relevant%20LUCI%20builder%0A-%20Links%20%28i.e.%20links%20to%20a%20failing%20CL%29%0A-%20Expected%20outcome%0A%0AIn%20addition%2C%20please%20clearly%20specify%20the%20priority%2Fseverity%20of%20your%20issue.%20).

We are extremely interested in bugs where results from BuildBot and LUCI
differ.
