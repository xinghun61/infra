# Commit Queue (CQ)

## What (is it)?

It's a service (aka a bot) that commits rietveld changes for you, instead of
you directly committing the change. We support a wide variety of projects
already and can support your project too (see [internal docs]).

For enabled projects, we display a CQ checkbox/button on Rietveld interface.

## How (does it work)?

The commit queue is not really a queue at the moment, since it processes the
changes out of order. This may be changed eventually. This means a CL can be
committed before another CL that was triggered much later. This can happen when
a try job is flaky.

### Current process for the user

1. Upload a review to rietveld where it gets reviewed and LGTM'ed.
1. One of:
    1. Check (select) the 'Commit' checkbox on a Rietveld issue, on the
       particular patchset that has been approved. Checking the checkbox is the
       only action required and there will be no immediate feedback in the form
       of messages, etc, to notify you that something has happened.
        1. Only the issue owner, someone at @chromium.org or @google.com can
           check the box.
        1. Yes, **non-Chromium committers are allowed** to use the commit queue
           but their LGTM (approval) on other issues is not accepted.
    1. At the command line, type `git cl set_commit`.
    1. Have a reviewer use 'Quick LGTM & CQ'.
1. Wait an hour. The current list of patches to be queued can be found at
   [Commit Queue Patches], while CQ progress can be tracked at the link posted
   by CQ on the CL (after some delay at which CQ checks for new CLs). The commit
   queue will wait automatically for the tree to reopen.
1. Wait for an email from commit-bot@chromium.org with success or failure.

### Why (is it broken)?

Please follow these general guidelines:

1. Please report issues to [chrome-troopers].
1. If you have a feature request, feel free to file a bug, use label
   Build-CommitQueue. Be sure to search for [current feature requests] first.

## Options

You may include the following options into the desription of your CL.

    COMMIT=false

If you are working on experimental code and do not want to risk accidentally
submitting it via the CQ, then you can mark it with `COMMIT=false`. The CQ will
immediately abandon the change if it contains this option. To dry run through
the CQ please use Rietveld's dry run feature.

    TBR=<username>

This stands for "to be reviewed". If a change has a TBR line with a valid
reviewer, the CQ will skip checks for LGTMs. See [guidelines] of when it's
acceptable to use this.

    NOPRESUBMIT=true

If you want to skip the presubmit check you can add this line and the commit
queue won't run the presubmit for your change. This should only be used when
there's a bug in the PRESUBMIT scripts. Please check that there's a bug filed
against the bad script, and if there isn't, file one.

    NOTRY=true

This should only be used for reverts to make the tree green, since it skips try
bots and might therefore break the tree. You shouldn't use this otherwise.

    NOTREECHECKS=true

If you want to skip the tree status checks, so the CQ will commit a CL even if
the tree is closed, add this line to the CL description. Obviously this is
strongly discouraged, since the tree is closed for a reason. However, in rare
cases this is acceptable, primarily to fix build breakages (i.e., your CL will
help in reopening the tree).

    NO_DEPENDENCY_CHECKS=true

The CQ rejects patchsets with open dependencies. An open dependency exists when
a CL depends on another CL that is not yet closed. You can skip this check with
this keyword.

    CQ_INCLUDE_TRYBOTS=<trybots>

This flag allows you to specify some additional bots to run for this CL, in
addition to the default bots. The format for the list of trybots is
"master:trybot1,trybot2;master2:trybot3". This feature only works for recipe
based bots right now.

## FAQ

### Is the CQ broken?

Take a look at
https://codereview.chromium.org/search?closed=3&commit=2&limit=100&order=modified.
If there are issues older than ~4 hours, they could probably be stuck. Note
that the Commit Queue could be stuck only for some issues but not all of them.
In case of doubt, please contact [chrome-troopers].

### The CQ seems hung

Is the tree open? It commits 4 CLs every 8 minutes, so a maximum rate of 30
commits per hour.

### Please Help! I just want to ask on irc!

Please report issues to [chrome-troopers].

### My patch failed to apply

See the [Try Server FAQ].

### What about LKGR?

The Commit Queue has never known, used or cared about LKGR. It always uses
HEAD, the tip of tree.

### What's my position on the queue?

The CLs are processed out of order, so it's not because another is "before"
yours that means it'll be committed before yours. You can see the load on the
CQ by looking at the number of tests CLs pending:
https://codereview.chromium.org/search?closed=3&commit=2&limit=1000&order=modified

### Sending a TBR patch fast

You can't wait for review? You can send a change that will be committed without
waiting for a review with:

    git fetch origin
    git new-branch work_fast
    # Quick, write your fix.
    echo "A copy is available for 100000$USD upon request." >> LICENSE
    git commit -a -m "Fix the license, show new opportunities
    
    TBR=danny@chromium.org"
    git cl upload --send-mail -c

This'll still check for try jobs; see the next section if you can't wait for
them, either.

The important part is to have **TBR**=foo@chromium.org in the CL description.

* `--send-mail` sends an email right away.
* `-c` sets the commit bit right away, short for `--use-commit-queue`.
* `--cc joe@chromium.org,hppo@chromium.org` to cc more people instead of
  putting everyone as reviewer.

Now, did you know there's `git cl help upload`?

### Sending CL through CQ without committing (dry run)

To dry run through the CQ please use Rietveld's [dry run] feature.

### Picking custom trybots

See the `CQ_INCLUDE_TRYBOTS` option, above.

### Try job results aren't showing up consistently on Rietveld

If you never had a HTTP 500 on GAE, chances are that [you will][gae-500].

### Binary files?

Yes, binary files are supported by try jobs as well as CQ now!

### My CL has a bazillion files, will it blend?

The CQ was able to commit a CL with 838 files so it is technically possible:
https://codereview.chromium.org/12261012/. The likelihood of the CQ failing
increases exponentially with the number of files in the CL.

### Moving, renaming or copying files

Was implemented in [bug 125984] and [bug 125983]. If the diff on Rietveld
doesn't look right, use the `--similarity` (defaults to 50%) and disable/enable
file copy with `--find-copies`/`--no-find-copies`. For more help please run:

    git cl help
    man git diff

### Are CQ users required to be around when the patch is landed?

In general, no, as the CQ can land at any time (including very long time), and
any breaking patches can be kicked about by the sheriff. After all, that's the
job of the sheriff. You will get an email when the CQ commits, so you can jump
on your nearest laptop if necessary.

If you expect your patch to be hard to revert, is touching several files and
directories or move files around, you may want to stay around in case there is
an incremental build failure or something hard to diagnose.

Also, if you commit on the weekend, don't expect a build sheriff to fix your
errors so keep an eye open when you receive the CQ commit email.

### What determines the set of tests and targets the try bots run?

This is controlled by a config file cq.cfg (e.g.
[config for chromium][chromium-cq-cfg]). Also see [this document][analyze-step]
for details on the analyze step.

[internal docs]: https://chrome-internal.googlesource.com/infra/infra_internal/+/master/doc/commit_queue.md
[Commit Queue Patches]: https://codereview.chromium.org/search?closed=3&commit=2
[chrome-troopers]: https://chromium.googlesource.com/infra/infra/+/master/doc/users/contacting_troopers.md
[current feature requests]: https://code.google.com/p/chromium/issues/list?q=label:Build-CommitQueue
[guidelines]: http://www.chromium.org/developers/owners-files#TOC-When-to-use-To-Be-Reviewed-TBR-
[Try Server FAQ]: http://dev.chromium.org/developers/testing/try-server-usage
[dry run]: https://groups.google.com/a/chromium.org/forum/#!topic/chromium-dev/G5-X0_tfmok
[gae-500]: http://code.google.com/status/appengine
[bug 125984]: https://code.google.com/p/chromium/issues/detail?id=125984
[bug 125983]: https://code.google.com/p/chromium/issues/detail?id=125983
[chromium-cq-cfg]: https://chromium.googlesource.com/chromium/src/+/master/infra/config/cq.cfg
[analyze-step]: http://dev.chromium.org/developers/testing/commit-queue/chromium_trybot-json
