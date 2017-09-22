# cr-audit-commits

cr-audit-commits is a GAE go app inteneded to verify that automated accounts
with permissions to create and land changes in the chromium repositories adhere
to a set of defined policies.

The original purpose of this app is to ensure that the Findit's service account
is not abused to land changes other than pure reverts of culprits of compile
failures created by Findit itself.

It has been designed to be extensible, so that it is easy to monitor other
repositories and other service accounts.

At the moment, in order to decide whether a policy has been broken, the
application has access to the commit's information as exposed by gitiles, the
originating changelist information as exposed by gerrit and information from
the continuous integration system, i.e. chromium's main waterfall.

In case a violation is detected, the system is designed to file monorail issue
with a customizable component and set of labels.

Further details can be read at [this design doc](go/commit-audit-app)
