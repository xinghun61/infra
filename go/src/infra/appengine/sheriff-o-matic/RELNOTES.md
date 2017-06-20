# Release Notes sheriff-o-matic 2017-06-20

- 7 commits, 3 bugs affected since 41148d3 (2017-06-13T23:18:55Z)
- 2 Authors:
  - renjietang@google.com
  - seanmccullough@chromium.org

## Changes in this release

- [[som] Fix checkbox styling on CrOS](https://chromium-review.googlesource.com/541539) (seanmccullough@chromium.org)
- [[infra frontend testing] move wct.go runner into infra/tools/wct](https://chromium-review.googlesource.com/540068) (seanmccullough@chromium.org)
- [[som] For CrOS, don't append .milo for GETs to /api/v1/alerts/gardener](https://chromium-review.googlesource.com/538981) (seanmccullough@chromium.org)
- [[som] Add server-side handler for updating layout test expectations.](https://chromium-review.googlesource.com/538039) (seanmccullough@chromium.org)
- [[som]add diff intepretation representated by color and +/- sign](https://chromium-review.googlesource.com/531624) (renjietang@google.com)
- [[som] test expectation edit form changes](https://chromium-review.googlesource.com/537142) (seanmccullough@chromium.org)
- [[som] add -persist flag to keep wct.go running after tests complete.](https://chromium-review.googlesource.com/537145) (seanmccullough@chromium.org)

## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/413053](https://crbug.com/413053)
  -  [https://crbug.com/603982](https://crbug.com/603982)
  -  [https://crbug.com/732624](https://crbug.com/732624)

# Release Notes sheriff-o-matic 2017-06-13

- 18 commits, 10 bugs affected since 5cb2ae6 (2017-06-06T22:22:23Z)
- 4 Authors:
  - seanmccullough@chromium.org
  - zhangtiff@google.com
  - renjietang@google.com
  - martiniss@chromium.org

## Changes in this release

- [[som] Increase frequency of chromium.perf cron analyzer runs](https://chromium-review.googlesource.com/534653) (seanmccullough@chromium.org)
- [[som] Default chromium.perf to use the GAE cron analyzer alerts.](https://chromium-review.googlesource.com/533639) (seanmccullough@chromium.org)
- [[som] Add a stripped-down WCT test runner for running in CI.](https://chromium-review.googlesource.com/529988) (seanmccullough@chromium.org)
- [SoM: Make all top level sections collapsible.](https://chromium-review.googlesource.com/530032) (zhangtiff@google.com)
- [[som] Truncate GAE version strings to 35 chars.](https://chromium-review.googlesource.com/531734) (seanmccullough@chromium.org)
- [SoM: Make infra failures/other alert sections collapsible and refactored alert categories into a separate element.](https://chromium-review.googlesource.com/529966) (zhangtiff@google.com)
- [add note about eval env.py](https://chromium-review.googlesource.com/529667) (seanmccullough@chromium.org)
- [SoM: Move alert opened/closed state from annotations to som-alert-item.](https://chromium-review.googlesource.com/527934) (zhangtiff@google.com)
- [SoM: Load trees directly into som-app instead of through AJAX.](https://chromium-review.googlesource.com/528419) (zhangtiff@google.com)
- [[som]fix typo in timezone](https://chromium-review.googlesource.com/528230) (renjietang@google.com)
- [created a function that computes the elapsed time since last update instead of showing the absolute UTC time.](https://chromium-review.googlesource.com/516464) (renjietang@google.com)
- [[som] Add LayoutTest expectation editing form.](https://chromium-review.googlesource.com/528058) (seanmccullough@chromium.org)
- [[som] Strip unused fields from Build messages, add cromium.perf to cron](https://chromium-review.googlesource.com/526476) (seanmccullough@chromium.org)
- [SoM: Make linked bugs show status.](https://chromium-review.googlesource.com/527662) (zhangtiff@google.com)
- [[som] fix make devserver to not generate the vulcanized index file.](https://chromium-review.googlesource.com/527418) (seanmccullough@chromium.org)
- [SoM: Add bulk annotation actions.](https://chromium-review.googlesource.com/524026) (zhangtiff@google.com)
- [[som] update Makefile, README.md for new frontend/backend split](https://chromium-review.googlesource.com/527514) (seanmccullough@chromium.org)
- [AD: Only count infra failures for bot affinity](https://chromium-review.googlesource.com/527310) (martiniss@chromium.org)


## Bugs updated, by author
- martiniss@chromium.org:
  -  [https://crbug.com/730004](https://crbug.com/730004)

- seanmccullough@chromium.org:
  -  [https://crbug.com/413053](https://crbug.com/413053)
  -  [https://crbug.com/603982](https://crbug.com/603982)
  -  [https://crbug.com/689284](https://crbug.com/689284)

- zhangtiff@google.com:
  -  [https://crbug.com/717713](https://crbug.com/717713)
  -  [https://crbug.com/717717](https://crbug.com/717717)
  -  [https://crbug.com/718127](https://crbug.com/718127)
  -  [https://crbug.com/725237](https://crbug.com/725237)
  -  [https://crbug.com/730315](https://crbug.com/730315)
  -  [https://crbug.com/730319](https://crbug.com/730319)

# Release Notes sheriff-o-matic 2017-06-06

- 7 commits, 1 bugs affected since 98ca199 (2017-05-30T23:02:13Z)
- 2 Authors:
  - zhangtiff@google.com
  - seanmccullough@chromium.org

## Changes in this release

- [SoM: Polish grouped alert view slightly.](https://chromium-review.googlesource.com/508041) (zhangtiff@google.com)
- [[som] fix typo](https://chromium-review.googlesource.com/524995) (seanmccullough@chromium.org)
- [[som] Update README.md for new deployment instructions.](https://chromium-review.googlesource.com/524294) (seanmccullough@chromium.org)
- [[som] adjust tsmon metric names to be less ambiguous](https://chromium-review.googlesource.com/524262) (seanmccullough@chromium.org)
- [[som] Split analyzer cron jobs into their own backend service.](https://chromium-review.googlesource.com/520625) (seanmccullough@chromium.org)
- [SoM: Fix gitignore for som-app.vulcanized.html](https://chromium-review.googlesource.com/519648) (zhangtiff@google.com)
- [[som] whitelist isolate server for alert links](https://chromium-review.googlesource.com/526333) (seanmccullough@chromium.org)

## Bugs updated, by author
- zhangtiff@google.com:
  -  [https://crbug.com/723793](https://crbug.com/723793)

# Release Notes sheriff-o-matic 2017-05-30

- 8 commits, 5 bugs affected since c9de2ca (2017-05-23T22:50:56Z)
- 3 Authors:
  - seanmccullough@chromium.org
  - zhangtiff@google.com
  - renjietang@google.com

## Changes in this release

- [[som] Add tsmon metrics for number of alerts generated by cron tasks.](https://chromium-review.googlesource.com/517968) (seanmccullough@chromium.org)
- [[som] Switch android trees to use GAE cron tasks instead of a-d alerts.](https://chromium-review.googlesource.com/517908) (seanmccullough@chromium.org)
- [SoM: Add more labels to file bug link.](https://chromium-review.googlesource.com/517422) (zhangtiff@google.com)
- [[som] Split GAE app into minimal frontend and sibling go packages.](https://chromium-review.googlesource.com/513244) (seanmccullough@chromium.org)
- [SoM: Refactor som-app by separating out alert logic.](https://chromium-review.googlesource.com/513382) (zhangtiff@google.com)
- [Added the time that the bug was last updated to be shown in the bug queue.](https://chromium-review.googlesource.com/514433) (renjietang@google.com)
- [[som] Fix gatekeeper tree config merging](https://chromium-review.googlesource.com/513498) (seanmccullough@chromium.org)
- [[som] update README.md](https://chromium-review.googlesource.com/513479) (seanmccullough@chromium.org)


## Bugs updated, by author
- renjietang@google.com:
  -  [https://crbug.com/671702](https://crbug.com/671702)

- seanmccullough@chromium.org:
  -  [https://crbug.com/670122](https://crbug.com/670122)
  -  [https://crbug.com/689284](https://crbug.com/689284)

- zhangtiff@google.com:
  -  [https://crbug.com/717717](https://crbug.com/717717)
  -  [https://crbug.com/724466](https://crbug.com/724466)

# Release Notes sheriff-o-matic 2017-05-23

- 15 commits, 10 bugs affected since 626f893 (2017-05-18T18:40:34Z)
- 4 Authors:
  - seanmccullough@chromium.org
  - martiniss@chromium.org
  - zhangtiff@google.com
  - renjietang@google.com

## Changes in this release

- [test test](https://chromium-review.googlesource.com/511742) (renjietang@google.com)
- [[som] cleanup: remove "pubsub" related stuff since we abandonded it.](https://chromium-review.googlesource.com/511167) (seanmccullough@chromium.org)
- [[som] Frontend for layout test expectations list.](https://chromium-review.googlesource.com/509912) (seanmccullough@chromium.org)
- [SOM: Add a staging banner](https://chromium-review.googlesource.com/508217) (martiniss@chromium.org)
- [[som] Add http handlers for fetching list of layout test expectations.](https://chromium-review.googlesource.com/508817) (seanmccullough@chromium.org)
- [SoM: Make autocollapsing alerts on annotation changes more strategic.](https://chromium-review.googlesource.com/508234) (zhangtiff@google.com)
- [SoM: Add check/uncheck all to group/ungroup modal.](https://chromium-review.googlesource.com/508094) (zhangtiff@google.com)
- [SoM: Start removing paper elements and adjust styling.](https://chromium-review.googlesource.com/506615) (zhangtiff@google.com)
- [SoM: Remove animation from collapsing/expanding alerts + misc polish.](https://chromium-review.googlesource.com/506456) (zhangtiff@google.com)
- [SoM: Polish swarming bot headers, simplify CSS, remove animation from iron-collapse.](https://chromium-review.googlesource.com/505218) (zhangtiff@google.com)
- [SoM: Fix alerts and bug queue flakily persisting between tree switches.](https://chromium-review.googlesource.com/493835) (zhangtiff@google.com)
- [SoM: Trim spaces on linked bug.](https://chromium-review.googlesource.com/506568) (zhangtiff@google.com)
- [AD: fix bot affinity detection](https://chromium-review.googlesource.com/509974) (martiniss@chromium.org)
- [AD: Ignore "Failure reason" step](https://chromium-review.googlesource.com/508283) (martiniss@chromium.org)
- [[som] alter memcache client to fail open on errors during a cache miss.](https://chromium-review.googlesource.com/513046) (seanmccullough@chromium.org)


## Bugs updated, by author
- martiniss@chromium.org:
  -  [https://crbug.com/723682](https://crbug.com/723682)

- seanmccullough@chromium.org:
  -  [https://crbug.com/603982](https://crbug.com/603982)

- zhangtiff@google.com:
  -  [https://crbug.com/697984](https://crbug.com/697984)
  -  [https://crbug.com/712816](https://crbug.com/712816)
  -  [https://crbug.com/718129](https://crbug.com/718129)
  -  [https://crbug.com/719740](https://crbug.com/719740)
  -  [https://crbug.com/720021](https://crbug.com/720021)
  -  [https://crbug.com/720079](https://crbug.com/720079)
  -  [https://crbug.com/720084](https://crbug.com/720084)
  -  [https://crbug.com/723791](https://crbug.com/723791)

# Release Notes sheriff-o-matic 2017-05-09

- 4 commits, 3 bugs affected since 886ce0f (2017-05-02T20:53:49Z)
- 3 Authors:
  - davidriley@chromium.org
  - seanmccullough@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [[som] Add Chrome OS alert-level notes.](https://chromium-review.googlesource.com/501328) (davidriley@chromium.org)
- [[som] Hide master restart notices for /gardener](https://chromium-review.googlesource.com/500568) (seanmccullough@chromium.org)
- [SoM: Change compact view option into collapse alerts by default.](https://chromium-review.googlesource.com/490693) (zhangtiff@google.com)
- [SoM: Update release notes.](https://chromium-review.googlesource.com/494166) (zhangtiff@google.com)


## Bugs updated, by author
- davidriley@chromium.org:
  -  [https://crbug.com/717673](https://crbug.com/717673)

- seanmccullough@chromium.org:
  -  [https://crbug.com/719616](https://crbug.com/719616)

- zhangtiff@google.com:
  -  [https://crbug.com/712085](https://crbug.com/712085)

# Release Notes sheriff-o-matic 2017-05-02

- 11 commits, 5 bugs affected since 6009331 (2017-04-25T22:31:34Z)
- 3 Authors:
  - davidriley@chromium.org
  - seanmccullough@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [[som] Fix Infra-DX feedback link params](https://chromium-review.googlesource.com/493368) (seanmccullough@chromium.org)
- [[som] Fix https->http for go/ links.](https://chromium-review.googlesource.com/492547) (seanmccullough@chromium.org)
- [[som] Switch iOS alerts over to cron-generated by default.](https://chromium-review.googlesource.com/492526) (seanmccullough@chromium.org)
- [SoM: Add confirmation to removing bugs.](https://chromium-review.googlesource.com/490710) (zhangtiff@google.com)
- [[som] Disable the chromium.perf cron tasks, since they 500 too much.](https://chromium-review.googlesource.com/487090) (seanmccullough@chromium.org)
- [SoM: Add information about a snooze to alert title.](https://chromium-review.googlesource.com/489470) (zhangtiff@google.com)
- [SoM: Add file bug link to the header.](https://chromium-review.googlesource.com/489422) (zhangtiff@google.com)
- [[som] Limit number of alerts autoresolved at once.](https://chromium-review.googlesource.com/487733) (davidriley@chromium.org)
- [SoM: Add collapse/expand all to bug queue.](https://chromium-review.googlesource.com/488131) (zhangtiff@google.com)
- [[som] Change alert date format to be more explicit.](https://chromium-review.googlesource.com/488165) (davidriley@chromium.org)
- [Revert "Revert "[som] Add support for grouping of Chrome OS alerts.""](https://chromium-review.googlesource.com/488124) (davidriley@chromium.org)


## Bugs updated, by author
- davidriley@chromium.org:
  -  [https://crbug.com/693641](https://crbug.com/693641)

- seanmccullough@chromium.org:
  -  [https://crbug.com/712421](https://crbug.com/712421)

- zhangtiff@google.com:
  -  [https://crbug.com/712817](https://crbug.com/712817)
  -  [https://crbug.com/712820](https://crbug.com/712820)
  -  [https://crbug.com/713234](https://crbug.com/713234)


# Release Notes sheriff-o-matic 2017-04-25

- 11 commits, 0 bugs affected since 791981d (2017-04-17T23:27:06Z)
- 5 Authors:
  - seanmccullough@chromium.org
  - zhangtiff@google.com
  - vadimsh@chromium.org
  - chanli@chromium.org
  - davidriley@chromium.org

## Changes in this release

- [Revert "[som] Add support for grouping of Chrome OS alerts."](https://chromium-review.googlesource.com/487086) (davidriley@chromium.org)
- [[som] Add support for grouping of Chrome OS alerts.](https://chromium-review.googlesource.com/464387) (davidriley@chromium.org)
- [[som] Add gerrit instance settings to tree configs/admin page](https://chromium-review.googlesource.com/484629) (seanmccullough@chromium.org)
- [SoM: Update README with more information on deployment.](https://chromium-review.googlesource.com/484799) (zhangtiff@google.com)
- [[som] Add basic geritt support for creating CLs](https://chromium-review.googlesource.com/483969) (seanmccullough@chromium.org)
- [[som] Add gerrit project settings to tree configs/admin page](https://chromium-review.googlesource.com/483386) (seanmccullough@chromium.org)
- [Roll luci-go DEPS.](https://chromium-review.googlesource.com/482576) (vadimsh@chromium.org)
- [SoM: Change sidebar menus to use submenus.](https://chromium-review.googlesource.com/479753) (zhangtiff@google.com)
- [[Som-Findit] Display a less obtrusive message when Findit doesn't have results for an alert.](https://chromium-review.googlesource.com/481881) (chanli@chromium.org)
- [SoM: Tweak header styling.](https://chromium-review.googlesource.com/482422) (zhangtiff@google.com)
- [Replace hiding alerts with bug with autosnoozing on link bug.](https://chromium-review.googlesource.com/482419) (zhangtiff@google.com)

# Release Notes sheriff-o-matic 2017-04-17

- 11 commits, 0 bugs affected since fa87fb4 (2017-04-11T22:38:25Z)
- 4 Authors:
  - vadimsh@chromium.org
  - zhangtiff@google.com
  - seanmccullough@chromium.org
  - martiniss@google.com

## Changes in this release

- [[som] Add corp trees to gatekeeper configs checked by /analyze.](https://chromium-review.googlesource.com/479567) (seanmccullough@chromium.org)
- [SOM: Add option to hide alerts with bugs](https://chromium-review.googlesource.com/476076) (martiniss@google.com)
- [[relnotes] check logs of multiple git dirs](https://chromium-review.googlesource.com/478811) (seanmccullough@chromium.org)
- [SOM: Refresh annotations less often](https://chromium-review.googlesource.com/477114) (martiniss@google.com)
- [SOM: De-dup ids we request from monorail.](https://chromium-review.googlesource.com/477503) (martiniss@google.com)
- [SOM: Cancel new contexts](https://chromium-review.googlesource.com/477119) (martiniss@google.com)
- [SOM: Add ability to collapse tree list](https://chromium-review.googlesource.com/476113) (martiniss@google.com)
- [SOM: Make single builder failure not have any text](https://chromium-review.googlesource.com/475125) (martiniss@google.com)
- [Roll luci/luci-go and luci/gae DEPS.](https://chromium-review.googlesource.com/475048) (vadimsh@chromium.org)
- [SoM: Update release notes.](https://chromium-review.googlesource.com/475088) (zhangtiff@google.com)
- [[som] Trust is_unexpected in test result logs.](https://chromium-review.googlesource.com/478056) (seanmccullough@chromium.org)

## Bugs update, by author
- seanmccullough@chromium.org
  -  [https://crbug.com/711733](https://crbug.com/711733)

# Release Notes sheriff-o-matic 2017-04-11

- 6 commits, 0 bugs affected since 6c97eaf (2017-04-03T21:36:11Z)
- 5 Authors:
  - martiniss@google.com
  - vadimsh@chromium.org
  - seanmccullough@chromium.org
  - chanli@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [AD: Count number of failures](https://chromium-review.googlesource.com/474168) (martiniss@google.com)
- [Move wct.yaml and sheriff-o-matic.yaml outside of build/packages/*.](https://chromium-review.googlesource.com/472146) (vadimsh@chromium.org)
- [[som] Clearly lable primary and secondary troopers.](https://chromium-review.googlesource.com/470327) (seanmccullough@chromium.org)
- [[SoM-Findit] Explicitly show 'Not supported by Findit' for not supported failures.](https://chromium-review.googlesource.com/466547) (chanli@chromium.org)
- [SoM: Make tree status show when tree is open as well.](https://chromium-review.googlesource.com/467911) (zhangtiff@google.com)
- [[som] update RELNOTEs.md for latest push](https://chromium-review.googlesource.com/466690) (seanmccullough@chromium.org)


# Release Notes sheriff-o-matic 2017-04-03

- 6 commits, 1 bugs affected since 6a90299 ()
- 5 Authors:
  - seanmccullough@chromium.org
  - martiniss@google.com
  - zhangtiff@google.com
  - chanli@chromium.org
  - mcgreevy@chromium.org

## Changes in this release

- [[som] fix deploy](https://chromium-review.googlesource.com/466687) (seanmccullough@chromium.org)
- [AD: Fix test results](https://chromium-review.googlesource.com/465513) (martiniss@google.com)
- [SoM: Make test type in Flakiness Dashboard URL not hardcoded.](https://chromium-review.googlesource.com/464071) (zhangtiff@google.com)
- [[som] Make un-sheriffable alerts more obviously so.](https://chromium-review.googlesource.com/462362) (seanmccullough@chromium.org)
- [[SoM-Findit] Only display Findit result for chromium tree and add findit link to running analyses.](https://chromium-review.googlesource.com/462359) (chanli@chromium.org)
- [When deciding whether to hide webkit tests, treat webkit_layout_tests as equivalent to webkit_tests](https://chromium-review.googlesource.com/461845) (mcgreevy@chromium.org)

## Bugs updated, by author
- mcgreevy@chromium.org:
  -  [https://crbug.com/706192](https://crbug.com/706192)

# Release Notes sheriff-o-matic 2017-03-28

- 5 commits, 3 bugs affected since d6d192f (2017-03-21T23:16:56Z)
- 3 Authors:
  - chanli@chromium.org
  - seanmccullough@chromium.org
  - davidriley@chromium.org

## Changes in this release

- [[som] Default /chromium to use the new GAE cron alerts instead of A-D](https://chromium-review.googlesource.com/459081) (seanmccullough@chromium.org)
- [[som] Add Gardener PFQ severities.](https://chromium-review.googlesource.com/459066) (davidriley@chromium.org)
- [[SoM-Findit] Fix mismatch message name.](https://chromium-review.googlesource.com/458588) (chanli@chromium.org)
- [[SoM-Findit] Sort alerts to display the ones with Findit results on top.](https://chromium-review.googlesource.com/457440) (chanli@chromium.org)
- [[som] make ?useMilo=1 work with /trooper](https://chromium-review.googlesource.com/457858) (seanmccullough@chromium.org)


## Bugs updated, by author
- chanli@chromium.org:
  -  [https://crbug.com/703368](https://crbug.com/703368)
  -  [https://crbug.com/704604](https://crbug.com/704604)

- davidriley@chromium.org:
  -  [https://crbug.com/704321](https://crbug.com/704321)


# Release Notes sheriff-o-matic 2017-03-21

- 5 commits, 2 bugs affected since c0759a0 (2017-03-14T22:01:58Z)
- 4 Authors:
  - chanli@chromium.org
  - seanmccullough@chromium.org
  - zhangtiff@google.com
  - davidriley@chromium.org

## Changes in this release

- [[SoM-Findit] Modify color of Findit result message.](https://chromium-review.googlesource.com/456765) (chanli@chromium.org)
- [[som] Authenticate requests to luci-milo](https://chromium-review.googlesource.com/456769) (seanmccullough@chromium.org)
- [SoM: Move bug queue to the top again.](https://chromium-review.googlesource.com/456768) (zhangtiff@google.com)
- [[som] Do not linkify Chrome OS links.](https://chromium-review.googlesource.com/456737) (davidriley@chromium.org)
- [[SoM-Findit] Add reverting CL to Findit results on Sheriff-o-Matic.](https://chromium-review.googlesource.com/453985) (chanli@chromium.org)


## Bugs updated, by author
- chanli@chromium.org:
  -  [https://crbug.com/700636](https://crbug.com/700636)

- davidriley@chromium.org:
  -  [https://crbug.com/702291](https://crbug.com/702291)

# Release Notes sheriff-o-matic 2017-03-14

- 3 commits, 2 bugs affected since 007a419 (2017-03-01T00:26:34Z)
- 3 Authors:
  - seanmccullough@chromium.org
  - martiniss@google.com
  - zhangtiff@google.com

## Changes in this release

- [[som] Add tsmon metrics to track bug queue length](https://chromium-review.googlesource.com/452719) (seanmccullough@chromium.org)
- [SOM: Add app engine cache client](https://chromium-review.googlesource.com/449019) (martiniss@google.com)
- [SoM: Show when comments are in flight.](https://chromium-review.googlesource.com/448099) (zhangtiff@google.com)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/700099](https://crbug.com/700099)

- zhangtiff@google.com:
  -  [https://crbug.com/696847](https://crbug.com/696847)


# Release Notes sheriff-o-matic 2017-02-28

- 5 commits, 4 bugs affected since e6b225b (2017-02-08T01:26:19Z)
- 4 Authors:
  - davidriley@chromium.org
  - sergiyb@chromium.org
  - chanli@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [SoM: Make feedback button appear in dev.](https://chromium-review.googlesource.com/447782) (zhangtiff@google.com)
- [SoM: add count of alerts in each category](https://chromium-review.googlesource.com/447356) (davidriley@chromium.org)
- [Update HTTP-references to test-results to use HTTPS](https://chromium-review.googlesource.com/444749) (sergiyb@chromium.org)
- [[SoM-Findit] Add Findit info on SoM page.](https://chromium-review.googlesource.com/442065) (chanli@chromium.org)
- [SoM: Move bug queue to bottom except for troopers + CSS/HTML cleanup](https://chromium-review.googlesource.com/439429) (zhangtiff@google.com)


## Bugs updated, by author
- chanli@chromium.org:
  -  [https://crbug.com/682314](https://crbug.com/682314)

- davidriley@chromium.org:
  -  [https://crbug.com/693654](https://crbug.com/693654)

- sergiyb@chromium.org:
  -  [https://crbug.com/664583](https://crbug.com/664583)

- zhangtiff@google.com:
  -  [https://crbug.com/669254](https://crbug.com/669254)


# Release Notes sheriff-o-matic 2017-02-07

- 5 commits, 2 bugs affected since 1955610 (2017-02-01T00:21:28Z)
- 3 Authors:
  - zhangtiff@google.com
  - seanmccullough@chromium.org
  - martiniss@google.com

## Changes in this release

- [SoM: Inline JavaScript when vulcanizing.](https://chromium-review.googlesource.com/437659) (zhangtiff@google.com)
- [[som] automatically diff cron and alerts-dispatcher alerts json.](https://chromium-review.googlesource.com/435511) (seanmccullough@chromium.org)
- [[som] don't check for chromeos master restarts](https://chromium-review.googlesource.com/435504) (seanmccullough@chromium.org)
- [SoM: Fix failing som-drawer test.](https://chromium-review.googlesource.com/435444) (zhangtiff@google.com)
- [SOM: New release](https://chromium-review.googlesource.com/435422) (martiniss@google.com)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/686154](https://crbug.com/686154)

- zhangtiff@google.com:
  -  [https://crbug.com/674205](https://crbug.com/674205)


# Release Notes sheriff-o-matic 2017-01-31

- 10 commits, 9 bugs affected since 7886237 (2017-01-25T00:23:35Z)
- 3 Authors:
  - martiniss@chromium.org
  - davidriley@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [SoM: Add offline builders to /trooper.](https://chromium-review.googlesource.com/435481) (zhangtiff@google.com)
- [SoM: Hide old comments.](https://chromium-review.googlesource.com/434862) (zhangtiff@google.com)
- [SoM: Make marked-element open links in new window.](https://chromium-review.googlesource.com/434961) (zhangtiff@google.com)
- [SoM: Fix flaky go test.](https://chromium-review.googlesource.com/434543) (zhangtiff@google.com)
- [SoM: Make dates in the sidebar shorter and more readable.](https://chromium-review.googlesource.com/433464) (zhangtiff@google.com)
- [SoM: Add bug priority category headers + more whitespace adjustments.](https://chromium-review.googlesource.com/433819) (zhangtiff@google.com)
- [SOM: Sort alerts by number of builders affected](https://chromium-review.googlesource.com/433363) (martiniss@chromium.org)
- [SoM: Remove failure type from autogenerated comment.](https://chromium-review.googlesource.com/433325) (zhangtiff@google.com)
- [SoM: Adjustments to paddings/margins + Made comments modal bigger.](https://chromium-review.googlesource.com/433107) (zhangtiff@google.com)
- [[som] Add support for Chrome OS alerts.](https://chromium-review.googlesource.com/431598) (davidriley@chromium.org)


## Bugs updated, by author
- davidriley@chromium.org:
  -  [https://crbug.com/639901](https://crbug.com/639901)

- zhangtiff@google.com:
  -  [https://crbug.com/637006](https://crbug.com/637006)
  -  [https://crbug.com/658781](https://crbug.com/658781)
  -  [https://crbug.com/669254](https://crbug.com/669254)
  -  [https://crbug.com/682042](https://crbug.com/682042)
  -  [https://crbug.com/684199](https://crbug.com/684199)
  -  [https://crbug.com/684744](https://crbug.com/684744)
  -  [https://crbug.com/685736](https://crbug.com/685736)
  -  [https://crbug.com/686053](https://crbug.com/686053)

# Release Notes sheriff-o-matic 2017-01-24

- 6 commits, 1 bugs affected since a427d6d (2017-01-17T23:08:47Z)
- 2 Authors:
  - zhangtiff@google.com
  - seanmccullough@chromium.org

## Changes in this release

- [SoM: Adjust trooper queue to load unstale data after loading cached data.](https://chromium-review.googlesource.com/431839) (zhangtiff@google.com)
- [[som] increase instance size to f4 so analyzer crons can run.](https://chromium-review.googlesource.com/431096) (seanmccullough@chromium.org)
- [[som] add useMilo url param to optionally display cron-generated alerts.](https://chromium-review.googlesource.com/431054) (seanmccullough@chromium.org)
- [SoM: Fix polylint errors and removed unused Bower dependencies.](https://chromium-review.googlesource.com/430895) (zhangtiff@google.com)
- [SoM: Removed unused imports.](https://chromium-review.googlesource.com/430260) (zhangtiff@google.com)
- [[som] re-enable cron jobs to run the analyzers for our trees.](https://chromium-review.googlesource.com/428354) (seanmccullough@chromium.org)

## Bugs updated, by author
- zhangtiff@google.com:
  -  [https://crbug.com/683253](https://crbug.com/683253)

# Release Notes sheriff-o-matic 2017-01-17

- 6 commits, 2 bugs affected since ffb69b1 (2017-01-12T19:35:06Z)
- 2 Authors:
  - zhangtiff@google.com
  - seanmccullough@chromium.org

## Changes in this release

- [SoM: Add make format to makefile.](https://chromium-review.googlesource.com/428904) (zhangtiff@google.com)
- [SoM: Delete som-formatted-text and replace with marked-element's](https://chromium-review.googlesource.com/428391) (zhangtiff@google.com)
- [SoM: Highlight comments link when there's a comment](https://chromium-review.googlesource.com/428305) (zhangtiff@google.com)
- [SoM: Move elements into their own subdirectories.](https://chromium-review.googlesource.com/427414) (zhangtiff@google.com)
- [[som] analyze each master in a separate goroutine](https://chromium-review.googlesource.com/427960) (seanmccullough@chromium.org)
- [[som] auth POSTs to alerts for crying out loud](https://chromium-review.googlesource.com/427256) (seanmccullough@chromium.org)

## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/680607](https://crbug.com/680607)

- zhangtiff@google.com:
  -  [https://crbug.com/674660](https://crbug.com/674660)

# Release Notes sheriff-o-matic 2017-01-10

- 8 commits, 3 bugs affected since a32145c (2016-12-21T01:59:25Z)
- 3 Authors:
  - martiniss@chromium.org
  - seanmccullough@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [[som] disable analyzer cron jobs so we can deploy today](https://chromium-review.googlesource.com/426779) (seanmccullough@chromium.org)
- [[som] create a new relnotes Make target](https://chromium-review.googlesource.com/425873) (seanmccullough@chromium.org)
- [[som] proposal: split js from .html files, use clang-format](https://chromium-review.googlesource.com/424333) (seanmccullough@chromium.org)
- [SoM: Make lastUpdated PST/PDT and add relative time.](https://chromium-review.googlesource.com/423199) (zhangtiff@google.com)
- [SoM: Minor UI tweaks.](https://chromium-review.googlesource.com/425840) (zhangtiff@google.com)
- [SOM: Change link bug to link or file bug](https://chromium-review.googlesource.com/424224) (martiniss@chromium.org)
- [[som] Add cron tasks, actually store alerts from analyzer running in SoM](https://chromium-review.googlesource.com/422993) (seanmccullough@chromium.org)
- [[som] update RELNOTES.md for weekly push](https://chromium-review.googlesource.com/422928) (seanmccullough@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/675688](https://crbug.com/675688)

- zhangtiff@google.com:
  -  [https://crbug.com/427715](https://crbug.com/427715)
  -  [https://crbug.com/658781](https://crbug.com/658781)

# Release Notes sheriff-o-matic 2016-12-20

- 9 commits, 5 bugs affected since ead1512 (2016-12-13)
- 4 Authors:
  - zhangtiff@google.com
  - seanmccullough@chromium.org
  - philwright@chromium.org
  - martiniss@chromium.org

## Changes in this release

- [[som, a-d] Move gitiles client code from som into infra/monitoring/client](https://chromium-review.googlesource.com/422477) (seanmccullough@chromium.org)
- [Pushing latest version of SoM as part of PRR deploy and rollback test](https://chromium-review.googlesource.com/422607) (philwright@chromium.org)
- [SOM: Add null check to UI](https://chromium-review.googlesource.com/420807) (martiniss@chromium.org)
- [SOM: Add memcache to rev range redirects](https://chromium-review.googlesource.com/416233) (martiniss@chromium.org)
- [SoM: Fix test for computing sheriffs and change to use mocked timers.](https://chromium-review.googlesource.com/420309) (zhangtiff@google.com)
- [SoM: Fix trooper navigation bug.](https://chromium-review.googlesource.com/419707) (zhangtiff@google.com)
- [[som] fix som-annotation-tests](https://chromium-review.googlesource.com/419788) (seanmccullough@chromium.org)
- [[som] Add recipe for running WCT tests for sheriff-o-matic](https://chromium-review.googlesource.com/418058) (seanmccullough@chromium.org)
- [[som] Repair some test cases in som-drawer-test.html](https://chromium-review.googlesource.com/419786) (seanmccullough@chromium.org)


## Bugs updated, by author
- martiniss@chromium.org:
  -  [https://crbug.com/673979](https://crbug.com/673979)

- philwright@chromium.org:
  -  [https://crbug.com/630455](https://crbug.com/630455)

- seanmccullough@chromium.org:
  -  [https://crbug.com/413053](https://crbug.com/413053)
  -  [https://crbug.com/674205](https://crbug.com/674205)

- zhangtiff@google.com:
  -  [https://crbug.com/673969](https://crbug.com/673969)
  -  [https://crbug.com/674205](https://crbug.com/674205)

# Release Notes sheriff-o-matic 2016-12-13

- 13 commits, 8 bugs affected since 30d0695 (2016-12-07T00:42:54Z)
- 3 Authors:
  - zhangtiff@google.com
  - seanmccullough@chromium.org
  - martiniss@chromium.org

## Changes in this release

- [SoM: Fix getting owned trooper bugs + make trooper page title count based on trooper queue.](https://chromium-review.googlesource.com/419778) (zhangtiff@google.com)
- [SoM: Fix trooper timestamp.](https://chromium-review.googlesource.com/419118) (zhangtiff@google.com)
- [SoM: Make lastUpdated time update properly on tree switch.](https://chromium-review.googlesource.com/419098) (zhangtiff@google.com)
- [[som] Pubsub support: read gatekeeper configs from gitiles.](https://chromium-review.googlesource.com/418411) (seanmccullough@chromium.org)
- [SOM: Fix bug queue missing dependency in computed property](https://chromium-review.googlesource.com/419137) (martiniss@chromium.org)
- [SoM: Move swarming bots above alerts and show them only on the trooper page.](https://chromium-review.googlesource.com/417134) (zhangtiff@google.com)
- [SoM: Update haveNoBugs for bug queue + misc fixes.](https://chromium-review.googlesource.com/418700) (zhangtiff@google.com)
- [SoM: Add bug summary to linked bug labels.](https://chromium-review.googlesource.com/416299) (zhangtiff@google.com)
- [[som] Show internal master restarts on /trooper page](https://chromium-review.googlesource.com/418475) (seanmccullough@chromium.org)
- [SoM: Enable caching for trooper queue by getting bugs in two steps.](https://chromium-review.googlesource.com/417106) (zhangtiff@google.com)
- [[som] Update WCT dependency](https://chromium-review.googlesource.com/417065) (seanmccullough@chromium.org)
- [SoM: Change pulling sheriffs to account for timezones.](https://chromium-review.googlesource.com/417405) (zhangtiff@google.com)
- [SoM: Update release notes.](https://chromium-review.googlesource.com/417399) (zhangtiff@google.com)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/413053](https://crbug.com/413053)
  -  [https://crbug.com/658270](https://crbug.com/658270)
  -  [https://crbug.com/672265](https://crbug.com/672265)

- zhangtiff@google.com:
  -  [https://crbug.com/637006](https://crbug.com/637006)
  -  [https://crbug.com/639396](https://crbug.com/639396)
  -  [https://crbug.com/649220](https://crbug.com/649220)
  -  [https://crbug.com/666169](https://crbug.com/666169)
  -  [https://crbug.com/672974](https://crbug.com/672974)

# Release Notes sheriff-o-matic 2016-12-06

- 7 commits, 3 bugs affected since 6131c01 (2016-11-29T23:49:37Z)
- 3 Authors:
  - zhangtiff@google.com
  - martiniss@chromium.org
  - seanmccullough@chromium.org

## Changes in this release

- [SoM: Display current trooper and sheriffs on sidebar.](https://chromium-review.googlesource.com/416506) (zhangtiff@google.com)
- [SOM: redirect to original page when asked to login](https://chromium-review.googlesource.com/416372) (martiniss@chromium.org)
- [[som] set window.xsrfToken when running vulcanized](https://chromium-review.googlesource.com/414577) (seanmccullough@chromium.org)
- [[som] Fix syntax error in som-annotations-test.](https://chromium-review.googlesource.com/415268) (seanmccullough@chromium.org)
- [SoM: Improve bug queue labels](https://chromium-review.googlesource.com/414990) (zhangtiff@google.com)
- [[som] Fix broken behavior/test in <som-rev-range>.](https://chromium-review.googlesource.com/415265) (seanmccullough@chromium.org)
- [[som] Fix som-alert-item test](https://chromium-review.googlesource.com/415364) (seanmccullough@chromium.org)


## Bugs updated, by author
- martiniss@chromium.org:
  -  [https://crbug.com/662283](https://crbug.com/662283)

- seanmccullough@chromium.org:
  -  [https://crbug.com/669987](https://crbug.com/669987)

- zhangtiff@google.com:
  -  [https://crbug.com/666169](https://crbug.com/666169)


# Release Notes sheriff-o-matic 2016-11-29

- 9 commits, 6 bugs affected since 663ee6b (2016-11-23T00:29:41.000Z)
- 4 Authors:
  - seanmccullough@chromium.org
  - zhangtiff@google.com
  - martiniss@chromium.org
  - sergiyb@chromium.org

## Changes in this release

- [[som] Display dead and quarantined swarming bots on /trooper](https://chromium-review.googlesource.com/414570) (seanmccullough@chromium.org)
- [[som] Show all pending and recent master restarts on /trooper](https://chromium-review.googlesource.com/414231) (seanmccullough@chromium.org)
- [SoM: Make severity sections for alerts stay in place.](https://chromium-review.googlesource.com/414525) (zhangtiff@google.com)
- [[som] UI for master restart notice](https://chromium-review.googlesource.com/414564) (seanmccullough@chromium.org)
- [SOM: Refresh xsrf token on post error](https://chromium-review.googlesource.com/414428) (martiniss@chromium.org)
- [SoM: Fix trooper bug query.](https://chromium-review.googlesource.com/414291) (zhangtiff@google.com)
- [[som] server-side support for displaying master restarts](https://chromium-review.googlesource.com/413906) (seanmccullough@chromium.org)
- [Add info about contributing to infra to SoM help page](https://chromium-review.googlesource.com/412785) (sergiyb@chromium.org)
- [SoM: Updated release notes for 11/22](https://chromium-review.googlesource.com/413550) (zhangtiff@google.com)


## Bugs updated, by author
- martiniss@chromium.org:
  -  [https://crbug.com/665617](https://crbug.com/665617)

- seanmccullough@chromium.org:
  -  [https://crbug.com/665708](https://crbug.com/665708)
  -  [https://crbug.com/666084](https://crbug.com/666084)

- sergiyb@chromium.org:
  -  [https://crbug.com/659855](https://crbug.com/659855)

- zhangtiff@google.com:
  -  [https://crbug.com/637006](https://crbug.com/637006)
  -  [https://crbug.com/667985](https://crbug.com/667985)

# Release Notes sheriff-o-matic 2016-11-22

- 5 commits, 1 bugs affected since 3a10459 (2016-11-16T00:11:55.000Z)
- 3 Authors:
  - zhangtiff@google.com
  - martiniss@chromium.org
  - seanmccullough@chromium.org

## Changes in this release

- [SOM: UI tweaks](https://chromium-review.googlesource.com/409615) (martiniss@chromium.org)
- [SOM: Fix `make test` after go files moved.](https://chromium-review.googlesource.com/413666) (martiniss@chromium.org)
- [[som] Split main.go into multiple files.](https://chromium-review.googlesource.com/412904) (seanmccullough@chromium.org)
- [SoM: Make alert count visible in page title.](https://chromium-review.googlesource.com/412302) (zhangtiff@google.com)
- [SoM: Format comments to link URLs and emails.](https://chromium-review.googlesource.com/412148) (zhangtiff@google.com)

## Bugs updated, by author
- zhangtiff@google.com:
  -  [https://crbug.com/464757](https://crbug.com/464757)

# Release Notes sheriff-o-matic 2016-11-15

- 13 commits, 8 bugs affected since a528c38 (2016-10-31T23:41:05.000Z)
- 4 Authors:
  - seanmccullough@chromium.org
  - zhangtiff@google.com
  - martiniss@chromium.org
  - chanli@google.com

## Changes in this release

- [[som] Add an option to render links pointing to Milo for builds](https://chromium-review.googlesource.com/411920) (seanmccullough@chromium.org)
- [SoM: Sort alerts based on bugs.](https://chromium-review.googlesource.com/411357) (zhangtiff@google.com)
- [SoM: Fix collapse/expand all.](https://chromium-review.googlesource.com/411456) (zhangtiff@google.com)
- [SoM: Add bug queue labels to filed bugs.](https://chromium-review.googlesource.com/411262) (zhangtiff@google.com)
- [SoM: Polish for trooper tab.](https://chromium-review.googlesource.com/410038) (zhangtiff@google.com)
- [SoM: Autofocus on comments box.](https://chromium-review.googlesource.com/410242) (zhangtiff@google.com)
- [SoM: Fix frontend tests.](https://chromium-review.googlesource.com/406487) (zhangtiff@google.com)
- [SOM: Bump timeout when talking to monorail](https://chromium-review.googlesource.com/409633) (martiniss@chromium.org)
- [[som] prep to generate alerts feed from pubsub persistent store](https://chromium-review.googlesource.com/405781) (seanmccullough@chromium.org)
- [SoM: Set up server for trooper tab.](https://chromium-review.googlesource.com/406681) (zhangtiff@google.com)
- [[Findit] change the how-to page for findit to go link.](https://chromium-review.googlesource.com/407558) (chanli@google.com)
- [SoM: Update help page to include comments.](https://chromium-review.googlesource.com/407610) (zhangtiff@google.com)
- [Update relnotes for SOM](https://chromium-review.googlesource.com/405827) (martiniss@chromium.org)

## Bugs updated, by author
- martiniss@chromium.org:
  -  [https://crbug.com/655234](https://crbug.com/655234)

- seanmccullough@chromium.org:
  -  [https://crbug.com/655286](https://crbug.com/655286)
  -  [https://crbug.com/655296](https://crbug.com/655296)

- zhangtiff@google.com:
  -  [https://crbug.com/637006](https://crbug.com/637006)
  -  [https://crbug.com/651736](https://crbug.com/651736)
  -  [https://crbug.com/663772](https://crbug.com/663772)
  -  [https://crbug.com/664169](https://crbug.com/664169)
  -  [https://crbug.com/664596](https://crbug.com/664596)

# Release Notes sheriff-o-matic 2016-10-31

- 7 commits, 3 bugs affected since 4f461df (2016-10-24T22:38:54.000Z)
- 5 Authors:
  - zhangtiff@google.com
  - chanli@google.com
  - seanmccullough@chromium.org
  - sergiyb@chromium.org
  - martiniss@chromium.org

## Changes in this release

- [SoM: Make bug queue labels more general + some setup for Trooper tab.](https://chromium-review.googlesource.com/404938) (zhangtiff@google.com)
- [[Som-Findit-integration] Quick fix to make sure the tests are displayed.](https://chromium-review.googlesource.com/404501) (chanli@google.com)
- [[Som-Findit integration] Add more information from Findit to SoM](https://chromium-review.googlesource.com/402014) (chanli@google.com)
- [[som] pubsub alerts: persist alerts using LUCI's datastore wrapper.](https://chromium-review.googlesource.com/400558) (seanmccullough@chromium.org)
- [SoM: More information in the bug queue and sorting by priority.](https://chromium-review.googlesource.com/403454) (zhangtiff@google.com)
- [Add instructions to install vulcanize into README.md](https://codereview.chromium.org/2451653002) (sergiyb@chromium.org)
- [Updated release notes](https://chromium-review.googlesource.com/402248) (martiniss@chromium.org)


## Bugs updated, by author
- chanli@google.com:
  -  [https://crbug.com/655234](https://crbug.com/655234)
- seanmccullough@chromium.org:
  -  [https://crbug.com/655286](https://crbug.com/655286)
- zhangtiff@google.com:
  -  [https://crbug.com/637006](https://crbug.com/637006)

# Release Notes sheriff-o-matic 2016-10-24

- 4 commits, 0 bugs affected since 413e1cd (2016-10-20T23:13:42.000Z)
- 3 Authors:
  - seanmccullough@chromium.org
  - martiniss@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [SOM: Remove stale alert severity](https://chromium-review.googlesource.com/401992) (martiniss@chromium.org)
- [SOM: Fix alert severity titles](https://chromium-review.googlesource.com/401989) (martiniss@chromium.org)
- [SoM: Updated release notes](https://chromium-review.googlesource.com/401011) (zhangtiff@google.com)
- [[som] docs: make the deployment section have it's own header.](https://chromium-review.googlesource.com/401418) (seanmccullough@chromium.org)

# Release Notes sheriff-o-matic 2016-10-20

- 14 commits, 7 bugs affected since c4f0ecc (2016-10-12T00:11:55.000Z)
- 3 Authors:
  - zhangtiff@google.com
  - seanmccullough@chromium.org
  - martiniss@chromium.org

## Changes in this release

- [SoM: Add user back to som-annotations](https://chromium-review.googlesource.com/400843) (zhangtiff@google.com)
- [[som] Actually parse the AlertsSummary posted by a-d to /alerts, return errors](https://chromium-review.googlesource.com/400092) (seanmccullough@chromium.org)
- [SoM: Only delete your own comments.](https://chromium-review.googlesource.com/400017) (zhangtiff@google.com)
- [SoM: Make annotations appear on the examine page again.](https://chromium-review.googlesource.com/400619) (zhangtiff@google.com)
- [SoM: Add comment feature.](https://chromium-review.googlesource.com/397898) (zhangtiff@google.com)
- [[som] Fix pubsub push handler to log errors and return OK](https://chromium-review.googlesource.com/397916) (seanmccullough@chromium.org)
- [SoM: Make annotations work for stale masters.](https://chromium-review.googlesource.com/398320) (zhangtiff@google.com)
- [[som] add milo pubsub push subscriber endpoint](https://chromium-review.googlesource.com/396958) (seanmccullough@chromium.org)
- [[som] add domain verification file.](https://chromium-review.googlesource.com/396940) (seanmccullough@chromium.org)
- [SoM: More responsive tweaks.](https://chromium-review.googlesource.com/396499) (zhangtiff@google.com)
- [SoM: Some edits to the admin page and Playbook linking.](https://chromium-review.googlesource.com/395028) (zhangtiff@google.com)
- [SOM: Make tests mock window.fetch](https://chromium-review.googlesource.com/394008) (martiniss@chromium.org)
- [[som] PRR work: get test coverage to 80%](https://chromium-review.googlesource.com/395086) (seanmccullough@chromium.org)
- [Bumping prod version](https://chromium-review.googlesource.com/394867) (martiniss@chromium.org)


## Bugs updated, by author
- martiniss@chromium.org:
  -  [https://crbug.com/651497](https://crbug.com/651497)

- seanmccullough@chromium.org:
  -  [https://crbug.com/630455](https://crbug.com/630455)
  -  [https://crbug.com/655286](https://crbug.com/655286)

- zhangtiff@google.com:
  -  [https://crbug.com/449694](https://crbug.com/449694)
  -  [https://crbug.com/634397](https://crbug.com/634397)
  -  [https://crbug.com/647362](https://crbug.com/647362)
  -  [https://crbug.com/657172](https://crbug.com/657172)


# Release Notes sheriff-o-matic 2016-10-06

- 4 commits, 1 bugs affected since d872a7c 2016-10-03T16:51:20.000Z
- 3 Authors:
  - seanmccullough@chromium.org
  - martiniss@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [[som] Add RELNOTES.md instructions to README.md](https://chromium-review.googlesource.com/394886) (seanmccullough@chromium.org)
- [SOM: Collapse alerts, sort by title](https://chromium-review.googlesource.com/388860) (martiniss@chromium.org)
- [SoM: Improve help page.](https://chromium-review.googlesource.com/393267) (zhangtiff@google.com)
- [[som] Add release notes for today's push](https://chromium-review.googlesource.com/391750) (seanmccullough@chromium.org)


## Bugs updated since, by author
- zhangtiff@google.com:
  -  [https://crbug.com/637340](https://crbug.com/637340)

# Sheriff-o-Matic Release Notes 2016-10-03

- 7 commits, 2 bugs affected since 2016-09-22
- 5 Authors:
  - zhangtiff@google.com
  - seanmccullough@chromium.org
  - dsansome@chromium.org
  - zhangtiff@chromium.org
  - martiniss@chromium.org

## Changes in this release

- [SoM: Small responsive tweaks.](https://chromium-review.googlesource.com/391153) (zhangtiff@google.com)
- [[som] Update cron url to remove trailing slash](https://chromium-review.googlesource.com/389516) (seanmccullough@chromium.org)
- [Update uses of tsmon to pass MetricMetadata by pointer.](https://chromium-review.googlesource.com/387427) (dsansome@chromium.org)
- [SoM: Reliable -> Consistent Failures.](https://chromium-review.googlesource.com/388877) (zhangtiff@chromium.org)
- [SOM: Fix production or staging detection](https://chromium-review.googlesource.com/388675) (martiniss@chromium.org)
- [SOM: fix template typo](https://chromium-review.googlesource.com/388632) (martiniss@chromium.org)
- [SOM: Small tweaks for production](https://chromium-review.googlesource.com/388532) (martiniss@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org
  - [https://crbug.com/650358](https://crbug.com/650358)
- zhangtiff@google.com
  - [https://crbug.com/647362](https://crbug.com/647362)
