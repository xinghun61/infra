# Welcome to LUCI!

<!-- This document is linked from "LUCI" chip in Gerrit-Buildbucket integration.
https://chromium.googlesource.com/infra/gerrit-plugins/buildbucket/+/master/src/main/resources/static/cr-build-block.html
For some users, this is the very first LUCI documentation they see.
-->

LUCI is a replacement for Buildbot that runs primarily on
the Google Cloud Platform and is designed to scale well for large projects.

## Current Status

**As of March 1, 2019, LUCI will become the sole service supporting
Chrome/Chromium builds.** For more information, see [Buildbot End of
Life](buildbot/buildbot_eol.md).

LUCI is currently being deployed over the Chromium project. All users
should start seeing LUCI being used over Buildbot builders over time.

All Chromium developers should already be using the new LUCI UI
([ci.chromium.org](https://ci.chromium.org)). The views will continue to look the
same once LUCI builders are switched to production. Sheriff-O-Matic,
Gatekeeper, and Findit build integrations will all work as intended. The
main differences to expect are:

* CQ try builders will show a LUCI tag in the Code Review UI. See
  [below](#How-do-I-know-a-build-was-run-on-LUCI) for details.
* LUCI builder pages will have a different URL path. See [UI
  tour](https://chromium.googlesource.com/chromium/src/+/master/docs/tour_of_luci_ui.md#builder-page)
  for details.
* LUCI build pages will have a different URL path. See
  [UI tour](https://chromium.googlesource.com/chromium/src/+/master/docs/tour_of_luci_ui.md#build-results-page)
  for details.
* When the switch is made, build numbers will be incremented
  by approximately +10 to separate Buildbot and LUCI
  builds.
* Blamelist limitation between first LUCI and last
  Buildbot builds. See
  [above](#What-limitations-does-the-migration-have) for
  details.

## How do I know a build was run on LUCI?

Builds on LUCI use a different URL path that
starts with `/p/chromium/builders/…`
If the build is still running on Buildbot,
"buildbot" will still be part of the URL path. Also, in
the Code Review UI, try-builders on Buildbot is shown
with a "Buildbot" tag. The default with no tag represents
a LUCI build.

![LUCI chip in Gerrit](../../images/luci_chip.png)

In some cases, builds on LUCI can also have the
following URL
`ci.chromium.org/p/chromium/builds/b<buildbucket_build_id>`.
This occurs when the build does not have a build number
which should not occur for any Chromium build

## Frequently Asked Questions

A FAQ that details user expectations for the LUCI migration is
available under [LUCI Builder Migration - FAQ](https://chromium.googlesource.com/chromium/src/+/master/docs/luci_migration_faq.md)

## Feedback

Enjoy LUCI! We're really interested in your feedback so please
don't hesitate to send it whether good or bad.

* Use the __feedback button__ ![LUCI Feedback](../../images/LUCI-Feedback-Icon.png
"Feedback")
on a LUCI page.
* __File a migration bug__ using the following
[template](https://bugs.chromium.org/p/chromium/issues/entry?labels=LUCI-Backlog,LUCI-Migrations&summary=[LUCI-Migration-Bug]%20Enter%20an%20one-line%20summary&components=Infra>Platform&cc=efoo@chromium.org,estaab@chromium.org,nodir@chromium.org&description=Please%20use%20this%20to%20template%20to%20file%20a%20bug%20into%20LUCI%20backlog.%20%20%0A%0AReminder%20to%20include%20the%20following%3A%0A-%20Description%20of%20issue%0A-%20Priority%0A-%20Is%20this%20a%20blocker...%0A-%20What%20builder%20is%20this%20bug%20blocking).
* __File a feature request__ using the following
[template](https://bugs.chromium.org/p/chromium/issues/entry?labels=LUCI-Backlog&summary=[LUCI-Feedback]%20Enter%20an%20one-line%20summary&components=Infra>Platform&cc=efoo@chromium.org,estaab@chromium.org,nodir@chromium.org&description=Please%20use%20this%20to%20template%20to%20file%20a%20feature%20request%20into%20LUCI%20backlog.%20%20%0A%0AReminder%20to%20include%20the%20following%3A%0A-%20Description%0A-%20Why%20this%20feature%20is%20needed).
* To __share your feedback__, please fill out this [short
survey](https://goo.gl/forms/YPO6XCQ3q47r00iw2).
* __Ask a question__ using [IRC under the #chromium](https://www.chromium.org/developers/irc) channel.

We are extremely interested in bugs where results from BuildBot and LUCI
differ.
