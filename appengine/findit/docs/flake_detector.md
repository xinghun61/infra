# Findit Flake Detector

Findit’s Flake Detector is a service that consumes CQ (presubmit) data , runs
analysis against it to detect flaky tests, and presents the flakes to the
end-users in multiple forms. The previous solution for this was
[Chromium-try-flakes], however, and this solution acts as a better replacement.
Flake Detector is in parity of critical features with Chromium-try-flakes, and
only supports the Chromium project as of now.

### Flake Detector UI: [https://findit-for-me.appspot.com/ranked-flakes]

Table of contents:

- [Term Definitions](#term-definitions)
- [Workflow](#workflow)
- [Bug Filing Criteria](#bug-filing-criteria)
- [Contacts](#contacts)
- [FAQ](#faq)

## Term Definitions
Within Flake Detector, a flaky test is defined to be a test failure that could
cause a CL to be **incorrectly** rejected by [CQ].

**Equivalent patchsets**. If two patchsets meet the following requirements, then
they are considered to be equivalent:
* They are associated with the same CL.
* They have no diffs on Gerrit: for example, one patch is a trivial rebase or
  commit-messsage-edit on top of the other.

**Equivalent builds**. If two builds meet the following requirements, then they
are considered equivalent:
* The patchsets that they are associated with are equivalent.
* They have the same master name and builder name.

**Flaky builds**. If two equivalent builds generate different results, one
success and one failure, then the failed one is a flaky build.

**Flaky test steps**. Any failed test step in a flaky build is a flaky step only
if it has a matching failed (retry with patch) step, otherwise it means that
either the test failures are caused by bugs on tip of tree or they're not the
culprits that caused the build to fail.

**Flaky tests**. Any test that failed in the (retry with patch) step is a flaky
test.

## Workflow
1. It leverages existing data sources for CQ ([cq_raw]), completed builds
   ([completed_builds_BETA]) and test results ([test_results]) BigQuery tables.
2. It runs cron jobs that execute a [SQL query] once every 10 minutes to detect
   flaky tests and store the results.
3. It analyzes the results by aggregating occurrences of the same tests and
   present them in following forms:
   * Automatically [file bugs].
   * [Ranked flaky tests].
   * Trigger culprit analysis using [Flake Analyzer] service.

## Group Similar Flaky Tests
When Flake Detector presents flaky tests to end-users, similar flaky tests are
grouped together to avoid duplications, and it uses the following criteria:
* gtests with different parameters.

  ![Example of gtests with different parameters]
* webkit_layout_tests with different queries.

  ![Example of webkit layout tests with different queries]

## Bug Filing Criteria
To avoid being noisy, a flaky test is only reported to Monorail if all the
following requirements are met:
* At least 3 unreported flake occurrences that are associated with different CLs
  within the past 24 hours.
* Any bug can only be created or updated at most once within any 24 hours
  window.
* At most 30 bugs can be created or updated within any 24 hours window.

## Contacts

### Reporting problems
For any breakage report and feature requests, please [file a bug].

### Mailing list
For questions and general discussions, please use [findit group].

## FAQ

### Why deprecate Chromium-try-flake?
There are mainly 3 reasons:
1. The API of the underlying key service ([Chromium-cq-status]) is going to be
   deprecated. [crbug.com/859430]
2. Chromium-try-flakes itself is hard to maintain now, and the Findit Flake
   Detector is a much cleaner solution and will be actively maintained and
   supported by Findit team.
3. Findit team plans to integrate Flake Detector and [Flake Analyzer] more
   closely with each other.

### What’s new in Flake Detector comparing to Chromium-try-flakes?
* Flaky tests with similar step names and test names are merged together for
  better bug management. For example, same binary run with different command
  line arguments, gtests with different parameters and webkit_layout_tests with
  different queries.
* Flaky tests are ranked by number of total occurrences to highlight the top
  flaky ones.
* List of occurrences for a flaky tests are grouped by builders for better
  visualization.

### Does Flake Detector support projects other than Chromium?
Because Flake Detector relies on ‘without patch’ steps in the recipe to
differentiate a flake failure from a consistent failure caused by a bug in tip
of tree, it currently only supports projects that use chromium_trybot recipe.

Supports for projects that don’t use chromium_trybot recipe could be added
later, please follow [crbug.com/840831].

[CQ]: https://chrome-internal.googlesource.com/infra/infra_internal/+/master/infra_internal/services/cq/README.md
[https://findit-for-me.appspot.com/ranked-flakes]: https://findit-for-me.appspot.com/ranked-flakes
[Chromium-try-flakes]: https://chromium-try-flakes.appspot.com/
[cq_raw]: https://bigquery.cloud.google.com/table/chrome-infra-events:raw_events.cq
[completed_builds_BETA]: https://bigquery.cloud.google.com/table/cr-buildbucket:builds.completed_BETA?tab=details
[test_results]: https://bigquery.cloud.google.com/table/test-results-hrd:events.test_results
[SQL query]: https://cs.chromium.org/chromium/infra/appengine/findit/services/flake_detection/flaky_tests.cq_false_rejection.sql
[file bugs]: https://bugs.chromium.org/p/chromium/issues/list?can=2&q=test-findit-detected&colspec=ID+Pri+M+Stars+ReleaseBlock+Component+Status+Owner+Summary+OS+Modified&x=m&y=releaseblock&cells=ids
[Ranked flaky tests]: https://findit-for-me.appspot.com/ranked-flakes
[Flake Analyzer]: https://findit-for-me.appspot.com/waterfall/list-flakes
[Example of gtests with different parameters]: images/gtests_with_different_parameters.png
[Example of webkit layout tests with different queries]: images/webkit_layout_tests_with_different_queries.png
[file a bug]: https://bugs.chromium.org/p/chromium/issues/entry?components=Tools%3ETest%3EFindIt%3EFlakiness
[findit group]: https://groups.google.com/a/chromium.org/forum/?pli=1#!forum/findit
[Chromium-cq-status]: http://chromium-cq-status.appspot.com/
[crbug.com/859430]: https://crbug.com/859430
[crbug.com/840831]: https://crbug.com/840831
