# LUCI Migration app

contact: luci-eng@

LUCI Migration app tracks migration of Buildbot builders to LUCI.
It knows masters and builders that need to be migrated, and for each builder
it evaulates correctness and performance.

## How to migrate a Chromium try-builder to LUCI

All Chromium builders are defined in `luci.chromium.try` bucket in
chromium's [cr-buildbucket.cfg] config.

Migration procedure:

1.  Go to the luci-migration page for the builder you want to migrate,
    for example
    https://luci-migration.appspot.com/masters/tryserver.chromium.linux/builders/chromium_presubmit
1.  Assign the "Tracking bug" to yourself and mark it as Started.
    Update other labels/attributes as needed.
1.  Change the "Experiment percentage" to 10% (second tick).
    The app will start scheduling completed Buildbot builds onto LUCI for
    10% of CLs.

    If access is denied, contact luci-eng@.
    The access is controlled by
    [luci-migration-writers group](https://chrome-infra-auth.appspot.com/auth/groups/luci-migration-writers).
1.  Wait.
    Check the page later to see the most recent report.
1.  Read the analysis report.
    The builder is likely to have <100% correctness.
    Each "false failure" means Buildbot build(s) succeeded for the patchset,
    but LUCI ones did not.
    Click on Failures and identify causes.
1.  Fix the causes and wait for another report.
    Ensure that failures with the same causes do not happen again.
1.  Repeat the process until correctness is 100%, or the only false failures
    are flakes.
    In case of a status change (not WAI -> WAI, or vice-versa), the app will post a comment on the bug.

[cr-buildbucket.cfg]: https://chromium.googlesource.com/chromium/src/+/infra/config/cr-buildbucket.cfg
