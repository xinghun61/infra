# cr-audit-commits

## What is this app?

cr-audit-commits is a GAE go app intended to verify that changes landed in the
git repositories monitored, comply with certain policies. E.g. Timely code
review approvals, automated rolls only modify allowed files, automated reverts
always identify a valid CI failure, release branch merges have correct
approvals, etc.

## What can it do?

Monitor a ref in a git repo continuously, apply custom rules to relevant commits
to decide if they comply with policies, issue notifications (bug filing, email
sending) if a violation is detected.

At the moment, in order to decide whether a policy has been broken, the
application has access to the commit's information as exposed by gitiles, the
originating changelist information as exposed by gerrit and information from
the continuous integration system, i.e. chromium's main waterfall.

## How does it work?

### Scheduler

A [Scheduler][Scheduler] cron job periodically runs and it iterates over the
configured repositories defined in the [RuleMap][RuleMap], it resolves any
dynamic refs and creates datastore entries for any monitored repos that do not
have it yet (i.e. for the first run after a repo has been added to the
configuration or when a dynamic ref changes) It then schedules audit tasks for
each monitored repository.

### Audit Task

The [audit task][audit task] is a TaskQueue task that does the following
* Requests a log from gitiles since the last known commit,
* Each commit is checked with a function defined by the ruleset to see if the
  commit is relevant and needs to be audited [matches]
* Creates a [datastore entry][Relevant Commit] for each new commit that needs
  to be audited.
* Updates the datastore entry for the repo with the newest LastKnownCommit.
* [Scans the datastore][Perform Scheduled Audits]to get the commits that have
  not yet been audited.
  * A [pool of worker goroutines][Worker Pool] are started and a job for
    auditing each commit will be sent to this pool.
    * Each worker will then take one job, and execute each of the
      [rules](#how-rules-work) for that commit, determine the status of the
      commit based on the result of the rules and send it back to the main
      goroutine.
    * If any of the rules cannot be decided e.g. due to a failure in another
      service, the current approach is for the rule to panic and for the worker
      to recover, increment the number of retries attempted for the commit and
      move on. There is a [bug][Bug to stop using panics] to change this to
      regular golang error handling.
  * The main routine then saves the statuses of all the audited commits in a
    a [single batch][Batch Update] to the datastore.
  * After this, the  task [scans the datastore][Notifier] for all the commits
    that need a notification to be sent, sends the notification, and saves a
    notification state to the datastore (E.g. to avoid repeated notifications
    for the same reason if for example the task issuing the notification times
    out).

### How Rules Work

[Rules][Rule type] are functions (wrapped as a method of an empty struct) that
decide whether a given commit complies with a given policy.

Rules receive some information about the repo being audited, and the information
about the commit to audit, as well a set of clients initialized and ready to
talk to external services (such as monorail) that may be needed to determine if
the commit complies with policy.

Rules are expected to return a [RuleResult][Rule Result].

For ownership and organization, it is expected that related rules live together
in a separate file. E.g. [`tbr_rules.go`][tbr rules]

### Notifications

Each RuleSet is responsible for providing a notification function,
that will be called with each commit that has failed an audit (or has been
determined that needs to issue a notification for some other reason that may not
be a policy violation).

Details can be seen at [notification.go][notification]


## Extending the app

This is an [example CL][extending] that adds support for a repository.


### Deployment procedure

1. Check out the revision to deploy,
1. Sync dependencies with `gclient sync`
1. Verify unit-tests run successfully with `go test` from the [app
    directory][app directory]
1. Use [this script][gae py script] `gae.py upload` to deploy a new version.
1. Use `gae.py switch` to make the new version default. Or use the web console.
1. Wait for the next run of the cron job (or [manually trigger][cron job] it)
   and examine the [logs][logs] for any unexpected failures.

### Known Issues

See [bug queue][bug queue]

[Audit Task]: https://cs.chromium.org/chromium/infra/go/src/infra/appengine/cr-audit-commits/app/auditor.go?rcl=f1ba458bda5f6cc5066e2bbcc0d95204f7c5093a&l=35
[Scheduler]: https://cs.chromium.org/chromium/infra/go/src/infra/appengine/cr-audit-commits/app/scheduler.go
[RuleMap]: https://cs.chromium.org/chromium/infra/go/src/infra/appengine/cr-audit-commits/app/rules_config.go?rcl=b5178615d3a566ca282829d80e19d2d932fce63d&l=88
[Matches]: https://cs.chromium.org/chromium/infra/go/src/infra/appengine/cr-audit-commits/app/rules_config.go?rcl=b5178615d3a566ca282829d80e19d2d932fce63d&l=252
[Relevant Commit]: https://cs.chromium.org/chromium/infra/go/src/infra/appengine/cr-audit-commits/app/model.go?rcl=b5178615d3a566ca282829d80e19d2d932fce63d&l=142
[Perform Scheduled Audits]: https://cs.chromium.org/chromium/infra/go/src/infra/appengine/cr-audit-commits/app/audit_worker.go?rcl=b5178615d3a566ca282829d80e19d2d932fce63d&l=55
[Worker Pool]: https://cs.chromium.org/chromium/infra/go/src/infra/appengine/cr-audit-commits/app/audit_worker.go?rcl=b5178615d3a566ca282829d80e19d2d932fce63d&l=98
[Batch Update]: https://cs.chromium.org/chromium/infra/go/src/infra/appengine/cr-audit-commits/app/auditor.go?rcl=b5178615d3a566ca282829d80e19d2d932fce63d&l=225
[Bug to stop using panics]: http://crbug.com/978167
[Notifier]: https://cs.chromium.org/chromium/infra/go/src/infra/appengine/cr-audit-commits/app/auditor.go?rcl=b5178615d3a566ca282829d80e19d2d932fce63d&l=273
[app directory]: https://cs.chromium.org/chromium/infra/go/src/infra/appengine/cr-audit-commits/app/
[gae py script]: https://cs.chromium.org/chromium/infra/luci/appengine/components/tools/gae.py
[cron job]: http://console.cloud.google.com/appengine/cronjobs?project=cr-audit-commits
[logs]: http://console.cloud.google.com/logs/viewer?project=cr-audit-commits
[bug queue]: https://bugs.chromium.org/p/chromium/issues/list?q=component%3AInfra%3EAudit%20&can=2
[Rule type]: https://cs.chromium.org/chromium/infra/go/src/infra/appengine/cr-audit-commits/app/rules_config.go?rcl=b5178615d3a566ca282829d80e19d2d932fce63d&l=294
[Rule Result]: https://cs.chromium.org/chromium/infra/go/src/infra/appengine/cr-audit-commits/app/model.go?rcl=b5178615d3a566ca282829d80e19d2d932fce63d&l=197
[notification]: https://cs.chromium.org/chromium/infra/go/src/infra/appengine/cr-audit-commits/app/notification.go?rcl=b5178615d3a566ca282829d80e19d2d932fce63d&l=37
[tbr rules]: https://cs.chromium.org/chromium/infra/go/src/infra/appengine/cr-audit-commits/app/tbr_rules.go
[extending]: https://chromium-review.googlesource.com/c/infra/infra/+/1681281
