# Release Notes sheriff-o-matic 2016-12-19

- 7 commits, 4 bugs affected since ead1512 (2016-12-14T00:33:37Z)
- 3 Authors:
  - martiniss@chromium.org
  - zhangtiff@google.com
  - seanmccullough@chromium.org

## Changes in this release

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
