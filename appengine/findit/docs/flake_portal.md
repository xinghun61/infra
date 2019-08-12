# Flake Portal

[Flake portal] is the **entry point to Chromium flakes and related information**.
* Use the [Flakes] page to view all on-going flakes ranked by their negative
 impacts, search for a flaky test, or filter flakes by binary, builder, component, etc.
* Use the [Report] page to assess overall flakiness states for the code area
 represented by a crbug component.
* Use the [Analysis] page to look for flake culprits and verify flake fixes.

Flake Portal UI: [https://analysis.chromium.org/p/chromium/flake-portal]

Table of contents:
* [Flakes](#flakes)
  * [Term Definitions](#term-definitions)
  * [Group Similar Flaky Tests on UI](#group-similar-flaky-tests-on-UI)
  * [Rank Flaky Tests](#rank-flaky-tests)
  * [Search Flaky Tests](#search-flaky-tests)
  * [Workflow](#workflow)
  * [Bug Filing Criteria](#bug-filing-criteria)
* [Report](#report)
* [Analysis](#analysis)
* [Contacts](#contacts)
* [FAQ](#faq)

## Flakes
The [Flakes] page ranks on-going flakes from CQ and CI in last 7 days by their
 negative impacts. Open bugs (either filed by Findit or by
 developers/sheriffs/other automatic tools) are linked to each flake.

### Term Definitions
**Flaky tests**. Any test that failed nondeterministically is a flaky test.
 For types of flaky tests, see below.

**Flake types**. Within [Flakes], flake types are defined by the negative impact of a flaky run.
* **CQ false rejection**, a test failure that causes a retried build or even
causes a CL to be **incorrectly** rejected by [CQ].
* **CQ step level retry**, a test failure that causes additional 'retry with
patch' and/or 'retry shards with patch' steps.
* **CQ hidden flake**, a passed test that were retried 2+ times by the test-runner.
 The first run and the first retry failed, while a later retry passed. This is
  to filter out noises caused by cpu/gpu/etc resource starvation due to parallel
   test execution by the test runner.
* **CI failed step flake**, a test failure that causes a test step failure on a CI waterfall build.

### Group Similar Flaky Tests on UI
The [Flakes] page groups similar flaky tests to avoid duplications, using the following criteria:
* gtests with different parameters.

 ![Example of gtests with different parameters]
* webkit_layout_tests with different queries.

 ![Example of webkit layout tests with different queries]

### Rank Flaky Tests
Detected flakes are ranked by a **unified score** by their negative impacts.

The score for CQ flakes is calculated based on impacted CLs and weights of each flake type.
The score for CI flakes is calculated based on occurrences and weights of each flake type, since CL concept is not relevant.
The weights are heuritically chosen numbers which should be proportional to the negative impact of each types.

Score = Sum(CQ flake type weight * impacted CLs) + Sum(CI flake type weight * occurrences)

![Flake Score Example]

### Search Flaky Tests
* Searching by **test name** for a specific flaky test is supported, without time limit.

![Search Flake Example]

* Tag-based filtering for flaky tests in last past 7 days is also supported.
  * You may search flakes with arbitrary combination of the above supported tags.
 But at least one "==" filter should be included. And the search results will only include flakes that:
    * match ALL "==" filters
    * do NOT match ANY "!=" fliters

| Tag | Example |
|-----|---------|
| binary | [binary==content_browsertests] matches tests in steps with content_browsertests as isolate target.|
| builder | [builder==win7_chromium_rel_ng] matches tests that occurred in the builder win7_chromium_rel_ng.|
| component | [component==Blink>Accessibility] matches tests whose directory's [OWNERS] file has Blink>Accessibility as COMPONENT. Tests in sub-components are **not** included.|
| directory | [directory==base/] matches tests whose test files are in base/ directory.|
| master | [master==tryserver.chromium.android] matches tests that occurred in the master tryserver.chromium.android.|
| parent_component | [parent_component==Blink>Accessibility] matches tests whose component is Blink>Accessibility or a sub-component of Blink>Accessibility.|
| source | [source==base/hash_unittest.cc] matches tests defined in the source file base/hash_unittest.cc. |
| step | [step==content_browsertests (with patch)]|
| suite | In Findit, suite is the smallest group of tests that are defined in the same file or directory, with some special cases.|
||[suite==GCMConnectionHandlerImplTest] matches gtest GCMConnectionHandlerImplTest.*|
||[suite==FullscreenVideoTest] matches Java tests *.FullscreenVideoTest#test.*|
||[suite==third_party/blink/web_tests/fast/events] matches Blink layout tests fast/events/*|
||[suite==webgl_conformance_tests] matches Telemetry-based gpu tests gpu_tests.webgl_conformance_integration_test.*|
| test_type | [test_type==content_browsertests] matches tests in steps with content_browsertests as their step name if removing suffixes like "(with patch)".|
| watchlist | [watchlist==accessibility] matches tests whose source files match the accessibility watchlist in src/WATCHLISTS. |


![Filter Flakes Example]

### Workflow
#### For CQ flakes
* It leverages existing data sources for CQ ([cq_raw]), completed builds
 ([completed_builds]) and test results ([test_results]) BigQuery tables.
* Cron jobs that execute [SQL queries] run once every 30 minutes to detect flaky tests and store the results.
  * The query for cq hidden flakes is executed every 2 hours.

#### For CI flakes
When a test step fails on a CI waterfall build, [Findit] runs a deflake swarming
 task to differentiate consistent test failures and flakes. The identified flakes will then show here.

#### After flakes are detected
Occurrences of the same tests are aggregated and presented in following forms:
  * Manage [pre-analysis bugs]:
    * Automatically file a bug. Or
    * Automatically comment on an existing bug.
  * Show on the [Flakes] page.
  * Automatically trigger culprit analysis in [Analysis].

### Bug Filing Criteria
To avoid noise, a flake bug is filed on Monorail only if all the following requirements are met:
* At least 3 unreported CQ false rejection or cq step level retry occurrences impacting different
 CLs within the past 24 hours.
* Any bug can only be created or updated at most once within any 24 hours window.
* At most 30 bugs can be created or updated automatically within any 24 hours window.

Additionally, flaky tests could be grouped so that each group can have the same bug.
 Flaky tests will be grouped together if:
* They have the same test-type,
* They have failed in exactly the same builds in the past 24 hours.

## Report
The [Report] page reports weekly flakiness states of Chrome Browser project and
 breakdown by each crbug component.

Report is generated every Monday 12:00AM PST for data of last week.

It reports the following states:
* **Flaky Tests**. Count of tests of a component with flake occurrences in last week.
* **Flake Bugs**. Count of flake bugs linked to the flaky tests.
* **New Bugs**. Count of flake bugs linked to the flaky tests that were newly created in last week.
* **False Rejects**. Count of CLs with CQ build retry (retries) on a patch or an
 equivalent patchsets because of any of the flaky tests in last week. Should be a sub-set of impacted CLs.
* **Impacted CLs**. Count of CLs that have been impacted by any of the flaky tests in last week.
* **Flake Occurrences**. Count of occurrences of all flaky tests in last week.

Project view shows aggregated flakiness data and top flake components with the
 most flakes or highest negative impacts. To look for a particular component,
 please use the search field on top of the page.

![Project Report]

Component view shows
* flake trend over time

![Component Report]
* The most negatively-impactful on-going flakes of each component.

![Top Flakes in Component]

## Analysis
[Analysis] reruns each flaky test many times through commits backwards, until:
* Finds the commit that added the flaky test or made the test become flaky,
 then this commit should be the culprit.
* has checked 5000 commits but without useful findings.

[Analysis] takes actions on the culprit commit:
* Manage [post-analysis bug]:
   * Automatically file a bug if no bug attached to the flake.
   * Automatically comment on an existing bug.

![Analysis Bug]
* Post a comment on the culprit's code review.

![Analysis Comment]
* Auto revert the culprit if the culprit added the flaky test.

[Analysis] supports verifying a flake fix is working by re-analyzing the flake at tip of tree.

![Analyze Tip-of-tree]

## Contacts
### Reporting problems
For any breakage report and feature requests, please [file a bug].
### Mailing list
For questions and general discussions, please use [findit group].
## FAQ
### What's the difference between Flake Portal and the
[Legacy Flakniness Dashboard](https://test-results.appspot.com/dashboards/flakiness_dashboard.html)?
+ Flake Portal is flake centric, use it if you have questions about **flakes**.
  + What're being flaky? How flaky are they? - Use [Flakes].
  + Why are they flaky? Has my change fixed the flaky test? - Use [Analysis].
  + What's the flakiness state of my component? - Use [Report].
+ For full test history, use the [Legacy Flakiness Dashboard].

[Analysis]: https://findit-for-me.appspot.com/p/chromium/flake-portal/analysis
[Analysis Bug]: images/flake_analysis_bug.png
[Analysis Comment]: images/flake_analysis_comment.png
[Analyze Tip-of-tree]: images/analyze_tip_of_tree.png
[binary==content_browsertests]: https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=binary::content_browsertests
[builder==win7_chromium_rel_ng]: https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=builder::win7_chromium_rel_ng
[completed_builds]: https://bigquery.cloud.google.com/table/cr-buildbucket:raw.completed_builds_prod?tab=details
[component==Blink>Accessibility]: https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=component::Blink>Accessibility
[Component Report]: images/component_report.png
[CQ]: https://chrome-internal.googlesource.com/infra/infra_internal/+/master/infra_internal/services/cq/README.md
[cq_raw]: https://bigquery.cloud.google.com/table/chrome-infra-events:raw_events.cq
[directory==base/]: https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=directory::base/
[Example of gtests with different parameters]: images/gtests_with_different_parameters.png
[Example of webkit layout tests with different queries]: images/webkit_layout_tests_with_different_queries.png
[external/wpt/IndexedDB/interleaved-cursors-large.html]: https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=test::external/wpt/IndexedDB/interleaved-cursors-large.html
[file a bug]: https://bugs.chromium.org/p/chromium/issues/entry?components=Infra%3ETest%3EFlakiness
[Filter Flakes Example]: images/filter_flakes.png
[Findit]: https://analysis.chromium.org
[findit group]: https://groups.google.com/a/chromium.org/forum/?pli=1#!forum/findit
[Flake portal]: https://analysis.chromium.org/p/chromium/flake-portal
[Flake Score Example]: images/flake_score.png
[Flakes]: https://analysis.chromium.org/p/chromium/flake-portal/flakes
[https://analysis.chromium.org/p/chromium/flake-portal]: https://analysis.chromium.org/p/chromium/flake-portal
[Legacy Flakiness Dashboard]: https://test-results.appspot.com/dashboards/flakiness_dashboard.html
[master==tryserver.chromium.android]: https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=master::tryserver.chromium.android
[OWNERS]: https://cs.chromium.org/chromium/src/third_party/blink/renderer/modules/accessibility/OWNERS?q=COMPONENT
[parent_component==Blink>Accessibility]: https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=parent_component::Blink>Accessibility
[post-analysis bug]: https://bugs.chromium.org/p/chromium/issues/list?can=2&q=test-findit-analyzed&colspec=ID+Pri+M+Stars+ReleaseBlock+Component+Status+Owner+Summary+OS+Modified&x=m&y=releaseblock&cells=ids
[pre-analysis bugs]: https://bugs.chromium.org/p/chromium/issues/list?can=2&q=test-findit-detected&colspec=ID+Pri+M+Stars+ReleaseBlock+Component+Status+Owner+Summary+OS+Modified&x=m&y=releaseblock&cells=ids
[Project Report]: images/project_report.png
[Report]: https://findit-for-me.appspot.com/p/chromium/flake-portal/report
[Search Flake Example]: images/search_flake.png
[source==base/hash_unittest.cc]: https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=source::base/hash_unittest.cc
[SQL queries]: https://cs.chromium.org/chromium/infra/appengine/findit/services/flake_detection/
[step==content_browsertests (with patch)]: https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=content_browsertests (with patch)
[suite==FullscreenVideoTest]: https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=suite::FullscreenVideoTest
[suite==GCMConnectionHandlerImplTest]:  https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=suite::GCMConnectionHandlerImplTest
[suite==third_party/blink/web_tests/fast/events]: https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=suite::third_party/blink/web_tests/fast/events
[suite==webgl_conformance_tests]: https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=suite::webgl_conformance_tests
[test_results]: https://bigquery.cloud.google.com/table/test-results-hrd:events.test_results
[test_type==content_browsertests]: https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=test_type::content_browsertests
[Top Flakes in Component]: images/top_flakes_component.png
[watchlist==accessibility]: https://analysis.chromium.org/p/chromium/flake-portal/flakes?flake_filter=watchlist::accessibility
