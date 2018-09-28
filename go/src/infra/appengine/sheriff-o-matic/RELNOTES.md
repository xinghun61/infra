
# Release Notes sheriff-o-matic 2018-09-28

- 3 commits, 2 bugs affected since 1c7d773 (2018-08-10T22:22:49Z)
- 3 Authors:
  - jbudorick@chromium.org
  - benjhayden@chromium.org
  - nodir@google.com

## Changes in this release

- [Simplify usage of wct.go](https://chromium-review.googlesource.com/1220591) (benjhayden@chromium.org)
- [[monorail] Remove InsertIssueRequest.ProjectID](https://chromium-review.googlesource.com/1232510) (nodir@google.com)
- [sheriff-o-matic: implement support for gatekeeper categories.](https://chromium-review.googlesource.com/1184235) (jbudorick@chromium.org)


## Bugs updated, by author
- jbudorick@chromium.org:
  -  [https://crbug.com/815006](https://crbug.com/815006)

- nodir@google.com:
  -  [https://crbug.com/882074](https://crbug.com/882074)

# Release Notes sheriff-o-matic 2018-08-10

- 2 commits, 0 bugs affected since be4350e (2018-07-25T23:10:09Z)
- 1 Authors:
  - seanmccullough@chromium.org

## Changes in this release

- [[som] Remove hard-coded builder configs, read json from gitiles.](https://chromium-review.googlesource.com/1170308) (seanmccullough@chromium.org)
- [[som] Update RELNOTES.md for release](https://chromium-review.googlesource.com/1150763) (seanmccullough@chromium.org)

# Release Notes sheriff-o-matic 2018-07-25

- 2 commits, 2 bugs affected since 7f4c64d (2018-07-18T21:05:34Z)
- 2 Authors:
  - kbr@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [SoM: Fix inline bug filing.](https://chromium-review.googlesource.com/1147755) (zhangtiff@google.com)
- [Fix mac10.13_retina_blink_rel trybot.](https://chromium-review.googlesource.com/1142619) (kbr@chromium.org)


## Bugs updated, by author
- kbr@chromium.org:
  -  [https://crbug.com/863070](https://crbug.com/863070)

- zhangtiff@google.com:
  -  [https://crbug.com/865456](https://crbug.com/865456)

# Release Notes sheriff-o-matic 2018-07-18

- 6 commits, 5 bugs affected since 49dc059 (2018-05-25T22:58:49Z)
- 6 Authors:
  - stgao@chromium.org
  - zhangtiff@google.com
  - seanmccullough@chromium.org
  - kbr@chromium.org
  - tandrii@chromium.org
  - jbudorick@chromium.org

## Changes in this release

- [Rename Blink Retina 10.12 bot to 10.13.](https://chromium-review.googlesource.com/1137058) (kbr@chromium.org)
- [monorail go lib: regenerate and fix with newest protobuf.](https://chromium-review.googlesource.com/1123769) (tandrii@chromium.org)
- [Fix som handling of gatekeeper glob-based exclusions.](https://chromium-review.googlesource.com/1119106) (jbudorick@chromium.org)
- [[SoM] Fix url to Findit.](https://chromium-review.googlesource.com/1119537) (stgao@chromium.org)
- [SoM: Replace paper-select-menu with plain browser select widget.](https://chromium-review.googlesource.com/1069679) (zhangtiff@google.com)
- [[som] update RELNOTES.md for Friday push](https://chromium-review.googlesource.com/1074193) (seanmccullough@chromium.org)


## Bugs updated, by author
- jbudorick@chromium.org:
  -  [https://crbug.com/815006](https://crbug.com/815006)

- kbr@chromium.org:
  -  [https://crbug.com/863070](https://crbug.com/863070)

- stgao@chromium.org:
  -  [https://crbug.com/857600](https://crbug.com/857600)

- tandrii@chromium.org:
  -  [https://crbug.com/859707](https://crbug.com/859707)

- zhangtiff@google.com:
  -  [https://crbug.com/841281](https://crbug.com/841281)

# Release Notes sheriff-o-matic 2018-05-25

- 1 commits, 1 bugs affected since fc95abd ()
- 1 Authors:
  - seanmccullough@chromium.org

## Changes in this release

- [[som] Only attempt to attach artifacts to test failures for perf.](https://chromium-review.googlesource.com/1072452) (seanmccullough@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/846562](https://crbug.com/846562)


# Release Notes sheriff-o-matic 2018-05-22

- 4 commits, 2 bugs affected since b14fa24 (2018-05-15T21:15:39Z)
- 2 Authors:
  - zhangtiff@google.com
  - seanmccullough@chromium.org

## Changes in this release

- [SoM: Fix refreshing.](https://chromium-review.googlesource.com/1069549) (zhangtiff@google.com)
- [[som] Remove unnecessary text.](https://chromium-review.googlesource.com/1067025) (seanmccullough@chromium.org)
- [[som] Server-side pieces to render perf test artifacts.](https://chromium-review.googlesource.com/1066819) (seanmccullough@chromium.org)
- [[som] Modify the UI to render artifact elements if present in tests.](https://chromium-review.googlesource.com/1062955) (seanmccullough@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/772212](https://crbug.com/772212)

- zhangtiff@google.com:
  -  [https://crbug.com/845476](https://crbug.com/845476)


# Release Notes sheriff-o-matic 2018-05-15

- 2 commits, 1 bugs affected since fbf9fe3 (2018-05-04T17:09:12Z)
- 1 Authors:
  - seanmccullough@chromium.org

## Changes in this release

- [[wct tester] Replace inlined MONKEYPATCH js with an included script.](https://chromium-review.googlesource.com/1055672) (seanmccullough@chromium.org)
- [[som] Ensure commit positions are sorted before linking to rev range.](https://chromium-review.googlesource.com/1055602) (seanmccullough@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/841472](https://crbug.com/841472)


# Release Notes sheriff-o-matic 2018-05-04

- 4 commits, 2 bugs affected since 7475df8 ()
- 2 Authors:
  - zhangtiff@google.com
  - seanmccullough@chromium.org

## Changes in this release

- [[som] Update bower package locks](https://chromium-review.googlesource.com/1040111) (seanmccullough@chromium.org)
- [[som] Update RELNOTES.md for release.](https://chromium-review.googlesource.com/1039781) (seanmccullough@chromium.org)
- [[som] Handle unexpected PASSes correctly. Do no alert on them.](https://chromium-review.googlesource.com/1036466) (seanmccullough@chromium.org)
- [SoM: Update release notes.](https://chromium-review.googlesource.com/1026932) (zhangtiff@google.com)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/838252](https://crbug.com/838252)
  -  [https://crbug.com/838960](https://crbug.com/838960)


# Release Notes sheriff-o-matic 2018-04-24

- 4 commits, 2 bugs affected since ff8691c (2018-04-04T21:38:55Z)
- 2 Authors:
  - seanmccullough@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [[som] Make WCT tests pass again.](https://chromium-review.googlesource.com/1024235) (seanmccullough@chromium.org)
- [SoM: Delete trooper page.](https://chromium-review.googlesource.com/1018528) (zhangtiff@google.com)
- [SoM: Fix most broken milo links.](https://chromium-review.googlesource.com/1017900) (zhangtiff@google.com)
- [[som] Update frontend/Makefile and wct.go](https://chromium-review.googlesource.com/1014501) (seanmccullough@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/824898](https://crbug.com/824898)

- zhangtiff@google.com:
  -  [https://crbug.com/822024](https://crbug.com/822024)


# Release Notes sheriff-o-matic 2018-04-04

- 3 commits, 1 bugs affected since 7753375 (2018-04-03T19:56:19Z)
- 1 Authors:
  - seanmccullough@chromium.org

## Changes in this release

- [[som] Check ungrouped alerts after doing a bulk ungroup.](https://chromium-review.googlesource.com/996182) (seanmccullough@chromium.org)
- [[som] Add bulk ungroup feature.](https://chromium-review.googlesource.com/994258) (seanmccullough@chromium.org)
- [[som] Make buttons hide when hidden](https://chromium-review.googlesource.com/994113) (seanmccullough@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/783360](https://crbug.com/783360)

# Release Notes sheriff-o-matic 2018-04-03

- 3 commits, 1 bugs affected since  (2018-03-15)
- 2 Authors:
  - zhangtiff@google.com
  - seanmccullough@chromium.org

## Changes in this release

- [[som] TA/DA: add client-side event logging for the editor form.](https://chromium-review.googlesource.com/992774) (seanmccullough@chromium.org)
- [[som] TA/DA: Move gerrit calls to js in the browser.](https://chromium-review.googlesource.com/987210) (seanmccullough@chromium.org)
- [SoM: Update release notes](https://chromium-review.googlesource.com/964905) (zhangtiff@google.com)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/819407](https://crbug.com/819407)


# Release Notes sheriff-o-matic 2018-03-15

- 8 commits, 7 bugs affected since 13c7c43 (2018-02-14T00:47:52Z)
- 3 Authors:
  - zhangtiff@google.com
  - martiniss@chromium.org
  - seanmccullough@chromium.org

## Changes in this release

- [SoM: create annotation migration.](https://chromium-review.googlesource.com/961801) (zhangtiff@google.com)
- [Rename "WebKit Mac10.11 (retina)" to "WebKit Mac10.12 (retina)"](https://chromium-review.googlesource.com/953213) (martiniss@chromium.org)
- [[som] Fix unexpected test failure identification](https://chromium-review.googlesource.com/956967) (seanmccullough@chromium.org)
- [[som] Lock bower, npm dependencies](https://chromium-review.googlesource.com/938757) (seanmccullough@chromium.org)
- [SoM: Split annotations by tree.](https://chromium-review.googlesource.com/930329) (zhangtiff@google.com)
- [SoM: Clean up bug filing and add label:infra-troopers to bugs filed from infra failures.](https://chromium-review.googlesource.com/924801) (zhangtiff@google.com)
- [[som] Fix broken file bug button.](https://chromium-review.googlesource.com/919688) (seanmccullough@chromium.org)
- [[som] deflake expectations parser tests](https://chromium-review.googlesource.com/916806) (seanmccullough@chromium.org)


## Bugs updated, by author
- martiniss@chromium.org:
  -  [https://crbug.com/818524](https://crbug.com/818524)

- seanmccullough@chromium.org:
  -  [https://crbug.com/812403](https://crbug.com/812403)
  -  [https://crbug.com/819853](https://crbug.com/819853)

- zhangtiff@google.com:
  -  [https://crbug.com/784529](https://crbug.com/784529)
  -  [https://crbug.com/796664](https://crbug.com/796664)
  -  [https://crbug.com/809803](https://crbug.com/809803)
  -  [https://crbug.com/809805](https://crbug.com/809805)

# Release Notes sheriff-o-matic 2018-02-13

- 1 commits, 1 bugs affected since 9cb5283 (2018-02-09T21:55:37Z)
- 1 Authors:
  - tandrii@chromium.org

## Changes in this release

- [SoM: remove chromium.sandbox master.](https://chromium-review.googlesource.com/912763) (tandrii@chromium.org)


## Bugs updated, by author
- tandrii@chromium.org:
  -  [https://crbug.com/810606](https://crbug.com/810606)

# Release Notes sheriff-o-matic 2018-02-09

- 4 commits, 3 bugs affected since 57f45c5 (2018-02-06T23:44:05Z)
- 1 Authors:
  - seanmccullough@chromium.org

## Changes in this release

- [[som] Increase RPC deadlines](https://chromium-review.googlesource.com/912350) (seanmccullough@chromium.org)
- [[som] rm unused code](https://chromium-review.googlesource.com/912228) (seanmccullough@chromium.org)
- [[som, wct.go] Adjustments for running frontend/Make's wct target.](https://chromium-review.googlesource.com/905506) (seanmccullough@chromium.org)
- [[som] Fix some FE unit tests.](https://chromium-review.googlesource.com/905743) (seanmccullough@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/413053](https://crbug.com/413053)
  -  [https://crbug.com/810362](https://crbug.com/810362)
  -  [https://crbug.com/810823](https://crbug.com/810823)

# Release Notes sheriff-o-matic 2018-02-06

- 5 commits, 3 bugs affected since 3ad142a (2018-01-31T17:46:25Z)
- 3 Authors:
  - iannucci@chromium.org
  - seanmccullough@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [SoM: Add autosuggested labels back.](https://chromium-review.googlesource.com/905231) (zhangtiff@google.com)
- [SoM: Update ChOpsUI version.](https://chromium-review.googlesource.com/905582) (zhangtiff@google.com)
- [Roll luci-go.](https://chromium-review.googlesource.com/905064) (iannucci@chromium.org)
- [[som] Add monitoring metrics for alert *groups*](https://chromium-review.googlesource.com/896166) (seanmccullough@chromium.org)
- [[som] Update RELNOTES.md](https://chromium-review.googlesource.com/894901) (seanmccullough@chromium.org)


## Bugs updated, by author
- iannucci@chromium.org:
  -  [https://crbug.com/809645](https://crbug.com/809645)

- seanmccullough@chromium.org:
  -  [https://crbug.com/807344](https://crbug.com/807344)

- zhangtiff@google.com:
  -  [https://crbug.com/809064](https://crbug.com/809064)


# Release Notes sheriff-o-matic 2018-01-31

- 2 commits, 2 bugs affected since 715ed81 (2018-01-16T23:57:49Z)
- 2 Authors:
  - seanmccullough@chromium.org
  - maruel@chromium.org

## Changes in this release

- [[som] Increase client RPC timeouts to 1 minute](https://chromium-review.googlesource.com/895412) (seanmccullough@chromium.org)
- [sheriff-o-matic: update Swarming API calls to go through webapp2 adaptor](https://chromium-review.googlesource.com/882682) (maruel@chromium.org)


## Bugs updated, by author
- maruel@chromium.org:
  -  [https://crbug.com/805076](https://crbug.com/805076)

- seanmccullough@chromium.org:
  -  [https://crbug.com/806700](https://crbug.com/806700)

# Release Notes sheriff-o-matic 2018-01-16

- 2 commits, 2 bugs affected since 6dcee01 (2018-01-09T22:17:27Z)
- 2 Authors:
  - iannucci@chromium.org
  - katthomas@google.com

## Changes in this release

- [Roll luci-go [9 commits]](https://chromium-review.googlesource.com/866210) (iannucci@chromium.org)
- [[eventupload] complete move to luci](https://chromium-review.googlesource.com/862253) (katthomas@google.com)


## Bugs updated, by author
- iannucci@chromium.org:
  -  [https://crbug.com/800662](https://crbug.com/800662)

- katthomas@google.com:
  -  [https://crbug.com/798430](https://crbug.com/798430)

# Release Notes sheriff-o-matic 2018-01-09

- 3 commits, 2 bugs affected since 05c64a3 (2018-01-04T17:09:23Z)
- 1 Authors:
  - seanmccullough@chromium.org

## Changes in this release

- [[som] Get rid of messages.TestResults and custom parsing logic.](https://chromium-review.googlesource.com/855598) (seanmccullough@chromium.org)
- [[som] Add messages.AlertTestFailure and set it when appropriate.](https://chromium-review.googlesource.com/854955) (seanmccullough@chromium.org)
- [[som] Fix test result parsing for secondsSinceEpoch.](https://chromium-review.googlesource.com/852523) (seanmccullough@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/701839](https://crbug.com/701839)
  -  [https://crbug.com/799079](https://crbug.com/799079)


# Release Notes sheriff-o-matic 2018-01-04

- 2 commits, 1 bugs affected since 7a3650e (2017-12-19T21:07:05Z)
- 1 Authors:
  - seanmccullough@chromium.org

## Changes in this release

- [[som] Now actually use the new "unkept" tree configs](https://chromium-review.googlesource.com/843067) (seanmccullough@chromium.org)
- [[som] Add a separate gatekeeper "config" for trees that don't use gk.](https://chromium-review.googlesource.com/843044) (seanmccullough@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/796442](https://crbug.com/796442)


# Release Notes sheriff-o-matic 2017-12-19

- 7 commits, 4 bugs affected since 5c8bea6 (2017-12-12T22:10:38Z)
- 3 Authors:
  - mcgreevy@chromium.org
  - seanmccullough@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [Roll infra/go/src/go.chromium.org/luci (14 commits)](https://chromium-review.googlesource.com/832587) (mcgreevy@chromium.org)
- [[som] Handle some badly formed test results cases more gracefully.](https://chromium-review.googlesource.com/833994) (seanmccullough@chromium.org)
- [[som] Add analyzer cron for chromium.gpu.fyi](https://chromium-review.googlesource.com/833992) (seanmccullough@chromium.org)
- [[som] Replace *all* dots with underscores when mapping tree name to prop](https://chromium-review.googlesource.com/833212) (seanmccullough@chromium.org)
- [[som] Show commit positions instead of short hashes in rev range.](https://chromium-review.googlesource.com/831109) (seanmccullough@chromium.org)
- [ChOpsUI: Rename prefix to chops-.](https://chromium-review.googlesource.com/828469) (zhangtiff@google.com)
- [[som] have staging hit findit staging.](https://chromium-review.googlesource.com/827670) (seanmccullough@chromium.org)


## Bugs updated, by author
- mcgreevy@chromium.org:
  -  [https://crbug.com/794425](https://crbug.com/794425)

- seanmccullough@chromium.org:
  -  [https://crbug.com/666140](https://crbug.com/666140)
  -  [https://crbug.com/786764](https://crbug.com/786764)
  -  [https://crbug.com/792347](https://crbug.com/792347)


# Release Notes sheriff-o-matic 2017-12-12

- 10 commits, 7 bugs affected since 6c327c1 (2017-12-05T00:09:03Z)
- 2 Authors:
  - seanmccullough@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [[som] Add test result history fetching to the analyzer.](https://chromium-review.googlesource.com/821191) (seanmccullough@chromium.org)
- [[som] Separate alert links into "Useful" and less prominent "All"](https://chromium-review.googlesource.com/818626) (seanmccullough@chromium.org)
- [[som] Add support for using test run history from test-results server](https://chromium-review.googlesource.com/817495) (seanmccullough@chromium.org)
- [[som] Some tweaks to render test results embedded in alerts.](https://chromium-review.googlesource.com/817658) (seanmccullough@chromium.org)
- [[som] Stop splitting test failures into one alert per test failure.](https://chromium-review.googlesource.com/815940) (seanmccullough@chromium.org)
- [[som] Make a separate client services init for staging/prod](https://chromium-review.googlesource.com/812455) (seanmccullough@chromium.org)
- [SoM: Add crdx-header to SoM.](https://chromium-review.googlesource.com/812545) (zhangtiff@google.com)
- [SoM: Restore custom labels per-tree to bug filing.](https://chromium-review.googlesource.com/809510) (zhangtiff@google.com)
- [SoM: Make file bug dialog scrollable.](https://chromium-review.googlesource.com/809625) (zhangtiff@google.com)
- [SoM: Update on-call links.](https://chromium-review.googlesource.com/809926) (zhangtiff@google.com)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/739864](https://crbug.com/739864)
  -  [https://crbug.com/757630](https://crbug.com/757630)
  -  [https://crbug.com/792303](https://crbug.com/792303)

- zhangtiff@google.com:
  -  [https://crbug.com/760265](https://crbug.com/760265)
  -  [https://crbug.com/788734](https://crbug.com/788734)
  -  [https://crbug.com/792149](https://crbug.com/792149)
  -  [https://crbug.com/792193](https://crbug.com/792193)

# Release Notes sheriff-o-matic 2017-12-04

- 2 commits, 1 bugs affected since e9701c3 (2017-12-01T16:06:40Z)
- 2 Authors:
  - seanmccullough@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [SoM: Add chopsui dep.](https://chromium-review.googlesource.com/806245) (zhangtiff@google.com)
- [[som] Fix bug filing form.](https://chromium-review.googlesource.com/804806) (seanmccullough@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/791184](https://crbug.com/791184)


# Release Notes sheriff-o-matic 2017-12-01

- 3 commits, 3 bugs affected since ec11864 (2017-11-29T18:54:29Z)
- 2 Authors:
  - seanmccullough@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [[som] Send a *pointer* to a proto struct to eventuploader](https://chromium-review.googlesource.com/801353) (seanmccullough@chromium.org)
- [SoM: add snippet about user to inline-filed bugs.](https://chromium-review.googlesource.com/792591) (zhangtiff@google.com)
- [[som, TA/DA] Add link to test expectation editor.](https://chromium-review.googlesource.com/795013) (seanmccullough@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/603982](https://crbug.com/603982)
  -  [https://crbug.com/790559](https://crbug.com/790559)

- zhangtiff@google.com:
  -  [https://crbug.com/788825](https://crbug.com/788825)


# Release Notes sheriff-o-matic 2017-11-29

- 6 commits, 2 bugs affected since dc0bf59
- 2 Authors:
  - zhangtiff@google.com
  - seanmccullough@chromium.org

## Changes in this release

- [Revert "[som] Update RELNOTES.md for weekly push."](https://chromium-review.googlesource.com/795039) (seanmccullough@chromium.org)
- [[som] Fix some text entry issues with email autocomplete](https://chromium-review.googlesource.com/795370) (seanmccullough@chromium.org)
- [[som] Update RELNOTES.md for weekly push.](https://chromium-review.googlesource.com/795111) (seanmccullough@chromium.org)
- [Add autocomplete UI for cc: field in bug form.](https://chromium-review.googlesource.com/792349) (seanmccullough@chromium.org)
- [SoM: Restore autofilling CCed user.](https://chromium-review.googlesource.com/792271) (zhangtiff@google.com)
- [[som] Add a user email autocomplete handler.](https://chromium-review.googlesource.com/786681) (seanmccullough@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/788894](https://crbug.com/788894)

- zhangtiff@google.com:
  -  [https://crbug.com/788825](https://crbug.com/788825)

# Release Notes sheriff-o-matic 2017-11-21

- 9 commits, 6 bugs affected since 52887aa (2017-11-08T00:07:03Z)
- 4 Authors:
  - jojwang@google.com
  - seanmccullough@chromium.org
  - estaab@google.com
  - zhangtiff@google.com

## Changes in this release

- [SoM: Make +/- buttons in menu sections toggleable.](https://chromium-review.googlesource.com/780446) (zhangtiff@google.com)
- [SoM: Remove per-alert group button.](https://chromium-review.googlesource.com/776396) (zhangtiff@google.com)
- [Refactor fileBugDialog into separate element.](https://chromium-review.googlesource.com/767850) (jojwang@google.com)
- [Link fileBugDialog to bugDialog](https://chromium-review.googlesource.com/761319) (jojwang@google.com)
- [[som] TA/DA: allow adding expectations for tests that don't already](https://chromium-review.googlesource.com/761198) (seanmccullough@chromium.org)
- [Link new issue to alerts](https://chromium-review.googlesource.com/760674) (jojwang@google.com)
- [Add inline bug filing](https://chromium-review.googlesource.com/758725) (jojwang@google.com)
- [[som] Change milo links to point to vanity URL and use public name.](https://chromium-review.googlesource.com/757896) (estaab@google.com)
- [Add file bug handler and som-file-bug element](https://chromium-review.googlesource.com/754285) (jojwang@google.com)


## Bugs updated, by author
- estaab@google.com:
  -  [https://crbug.com/765854](https://crbug.com/765854)

- jojwang@google.com:
  -  [https://crbug.com/534071](https://crbug.com/534071)
  -  [https://crbug.com/782883](https://crbug.com/782883)

- seanmccullough@chromium.org:
  -  [https://crbug.com/622359](https://crbug.com/622359)

- zhangtiff@google.com:
  -  [https://crbug.com/785556](https://crbug.com/785556)
  -  [https://crbug.com/787094](https://crbug.com/787094)

# Release Notes sheriff-o-matic 2017-11-07

- 2 commits, 0 bugs affected since baa8249 (2017-11-01T23:22:20Z)
- 2 Authors:
  - davidriley@chromium.org
  - seanmccullough@chromium.org

## Changes in this release

- [[som] Don't rewrite go links to https.](https://chromium-review.googlesource.com/756190) (davidriley@chromium.org)
- [[som] convert logging from txt proto tabledefs to plain protos](https://chromium-review.googlesource.com/747129) (seanmccullough@chromium.org)

# Release Notes sheriff-o-matic 2017-11-01

- 2 commits, 2 bugs affected since 36bb94e (2017-10-31T22:02:06Z)
- 2 Authors:
  - martiniss@chromium.org
  - seanmccullough@chromium.org

## Changes in this release

- [[som] Move annotation key into POST body.](https://chromium-review.googlesource.com/749688) (seanmccullough@chromium.org)
- [SOM: Split alerts by test](https://chromium-review.googlesource.com/671157) (martiniss@chromium.org)


## Bugs updated, by author
- martiniss@chromium.org:
  -  [https://crbug.com/780297](https://crbug.com/780297)

- seanmccullough@chromium.org:
  -  [https://crbug.com/775266](https://crbug.com/775266)

# Release Notes sheriff-o-matic 2017-10-31

- 4 commits, 2 bugs affected since d65cf28 (2017-10-18T17:49:42Z)
- 4 Authors:
  - zhangtiff@google.com
  - nodir@google.com
  - martiniss@chromium.org
  - katthomas@google.com

## Changes in this release

- [Roll infra/go/src/go.chromium.org/luci/ fbb8a7b77..4d42df061 (14 commits)](https://chromium-review.googlesource.com/744722) (nodir@google.com)
- [SOM: Fix reason merging](https://chromium-review.googlesource.com/730882) (martiniss@chromium.org)
- [[eventupload] remove TableDef references](https://chromium-review.googlesource.com/729153) (katthomas@google.com)
- [SoM: Removed unused code.](https://chromium-review.googlesource.com/729327) (zhangtiff@google.com)


## Bugs updated, by author
- katthomas@google.com:
  -  [https://crbug.com/775262](https://crbug.com/775262)

- martiniss@chromium.org:
  -  [https://crbug.com/723875](https://crbug.com/723875)

# Release Notes sheriff-o-matic 2017-10-18

- 2 commits, 0 bugs affected since daed6f1 (2017-10-11T19:51:00Z)
- 1 Authors:
  - seanmccullough@chromium.org

## Changes in this release

- [[som] Add structured event logging for user annotations on alerts](https://chromium-review.googlesource.com/719962) (seanmccullough@chromium.org)
- [[som] Add GAE requestID to alerts event table](https://chromium-review.googlesource.com/714025) (seanmccullough@chromium.org)

# Release Notes sheriff-o-matic 2017-10-11

- 3 commits, 1 bugs affected since 9334646 (2017-10-10T21:44:46Z)
- 2 Authors:
  - seanmccullough@chromium.org
  - martiniss@chromium.org

## Changes in this release

- [[som] authenticate RPCs to Milo](https://chromium-review.googlesource.com/713589) (seanmccullough@chromium.org)
- [[som] SoM manages its own bq tables instead of using chrome-infra-events](https://chromium-review.googlesource.com/711134) (seanmccullough@chromium.org)
- [SOM: Fix grouping logic](https://chromium-review.googlesource.com/710854) (martiniss@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/773674](https://crbug.com/773674)


# Release Notes sheriff-o-matic 2017-10-10

- 10 commits, 2 bugs affected since 05ddbf8 (2017-09-20T22:14:39Z)
- 4 Authors:
  - seanmccullough@chromium.org
  - nodir@google.com
  - tandrii@chromium.org
  - martiniss@chromium.org

## Changes in this release

- [SOM: Remove regression ranges for merged alert](https://chromium-review.googlesource.com/710225) (martiniss@chromium.org)
- [[som] Write alert events to BQ.](https://chromium-review.googlesource.com/701927) (seanmccullough@chromium.org)
- [SoM: pass exclude_deprecated to Milo](https://chromium-review.googlesource.com/706296) (nodir@google.com)
- [SoM: remove unused client.MiloGetBuildInfo](https://chromium-review.googlesource.com/706295) (nodir@google.com)
- [SoM: add cron for new master.chromium.sandbox tree.](https://chromium-review.googlesource.com/699517) (tandrii@chromium.org)
- [Reland "SOM: Group alerts using annotations"](https://chromium-review.googlesource.com/679622) (martiniss@chromium.org)
- [SoM: remove unused client.LatestBuilds](https://chromium-review.googlesource.com/679458) (nodir@google.com)
- [SOM: Fix undefined range check](https://chromium-review.googlesource.com/672155) (martiniss@chromium.org)
- [Roll infra/go/src/go.chromium.org/luci/ 0b4a49dd7..6195d71a7 (32 commits)](https://chromium-review.googlesource.com/677570) (nodir@google.com)
- [gofmt and goimport everything](https://chromium-review.googlesource.com/677469) (nodir@google.com)


## Bugs updated, by author
- nodir@google.com:
  -  [https://crbug.com/712421](https://crbug.com/712421)

- tandrii@chromium.org:
  -  [https://crbug.com/771408](https://crbug.com/771408)

# Release Notes sheriff-o-matic 2017-09-20

- 6 commits, 1 bugs affected since fed5bcc (2017-09-13T00:11:13Z)
- 3 Authors:
  - martiniss@chromium.org
  - zhangtiff@google.com
  - seanmccullough@chromium.org

## Changes in this release

- [Revert "SOM: Group alerts using annotations"](https://chromium-review.googlesource.com/676135) (martiniss@chromium.org)
- [SoM: Edit makefile to use _ instead of -](https://chromium-review.googlesource.com/675830) (zhangtiff@google.com)
- [[som] Register prpc client references instead of host URLs for milo](https://chromium-review.googlesource.com/665984) (seanmccullough@chromium.org)
- [SOM: Group alerts using annotations](https://chromium-review.googlesource.com/633871) (martiniss@chromium.org)
- [SOM: Add some error handling for regression range grouping](https://chromium-review.googlesource.com/661879) (martiniss@chromium.org)
- [SoM: Add null checks to groupRange.](https://chromium-review.googlesource.com/669280) (zhangtiff@google.com)


## Bugs updated, by author
- zhangtiff@google.com:
  -  [https://crbug.com/765485](https://crbug.com/765485)

# Release Notes sheriff-o-matic 2017-09-12

- 8 commits, 4 bugs affected since 0c22583 (2017-09-05T22:38:31Z)
- 3 Authors:
  - martiniss@chromium.org
  - zhangtiff@google.com
  - seanmccullough@chromium.org

## Changes in this release

- [SoM: Add PM/AM to comments timestamp.](https://chromium-review.googlesource.com/662244) (zhangtiff@google.com)
- [SoM: Fix range is undefined error.](https://chromium-review.googlesource.com/660690) (zhangtiff@google.com)
- [SoM: Add relative time to comment timestamps.](https://chromium-review.googlesource.com/658081) (zhangtiff@google.com)
- [[som] Color infra failures purple](https://chromium-review.googlesource.com/658140) (seanmccullough@chromium.org)
- [[som] Package refactoring](https://chromium-review.googlesource.com/656521) (seanmccullough@chromium.org)
- [SOM: Group regression ranges correctly](https://chromium-review.googlesource.com/636176) (martiniss@chromium.org)
- [SoM: Basic tree status viewing page.](https://chromium-review.googlesource.com/648245) (zhangtiff@google.com)
- [SOM: Fix commit position parsing](https://chromium-review.googlesource.com/656563) (martiniss@chromium.org)


## Bugs updated, by author
- martiniss@chromium.org:
  -  [https://crbug.com/723875](https://crbug.com/723875)

- seanmccullough@chromium.org:
  -  [https://crbug.com/763429](https://crbug.com/763429)

- zhangtiff@google.com:
  -  [https://crbug.com/760297](https://crbug.com/760297)
  -  [https://crbug.com/763184](https://crbug.com/763184)


# Release Notes sheriff-o-matic 2017-09-05

- 17 commits, 6 bugs affected since 7fa4298 ()
- 5 Authors:
  - martiniss@chromium.org
  - zhangtiff@google.com
  - dnj@chromium.org
  - seanmccullough@chromium.org
  - jojwang@google.com

## Changes in this release

- [Add test-results.](https://chromium-review.googlesource.com/644847) (jojwang@google.com)
- [SOM: Improve grouped alert UI](https://chromium-review.googlesource.com/633898) (martiniss@chromium.org)
- [SoM: Hide Julie Jumping when filtering alerts.](https://chromium-review.googlesource.com/644164) (zhangtiff@google.com)
- [Add function to query bigquery.](https://chromium-review.googlesource.com/622947) (jojwang@google.com)
- [SoM: Disable examine page refresh for everything except annotations.](https://chromium-review.googlesource.com/644606) (zhangtiff@google.com)
- [Add helper functions for test-results in SoM.](https://chromium-review.googlesource.com/624728) (jojwang@google.com)
- [Update release notes](https://chromium-review.googlesource.com/642123) (jojwang@google.com)
- [Add master-results element](https://chromium-review.googlesource.com/636510) (jojwang@google.com)
- [Roll luci-go and luci/gae.](https://chromium-review.googlesource.com/636852) (dnj@chromium.org)
- [Add builder-result polymer element](https://chromium-review.googlesource.com/633905) (jojwang@google.com)
- [Update RELNOTES.md](https://chromium-review.googlesource.com/626656) (jojwang@google.com)
- [SoM: Make group name changes save on focus changes.](https://chromium-review.googlesource.com/621594) (zhangtiff@google.com)
- [[som] Update README.md to be more friendly to new contributors](https://chromium-review.googlesource.com/621417) (seanmccullough@chromium.org)
- [[som] Attempt to add test expectation information to test failure alerts](https://chromium-review.googlesource.com/617609) (seanmccullough@chromium.org)
- [[som] Update release notes](https://chromium-review.googlesource.com/616066) (seanmccullough@chromium.org)
- [Add new structs for test-results in SoM](https://chromium-review.googlesource.com/619693) (jojwang@google.com)
- [[som] add cloud storage to whitelisted link hosts](https://chromium-review.googlesource.com/620068) (seanmccullough@chromium.org)


## Bugs updated, by author
- jojwang@google.com:
  -  [https://crbug.com/757630](https://crbug.com/757630)

- seanmccullough@chromium.org:
  -  [https://crbug.com/603982](https://crbug.com/603982)
  -  [https://crbug.com/755886](https://crbug.com/755886)

- zhangtiff@google.com:
  -  [https://crbug.com/751297](https://crbug.com/751297)
  -  [https://crbug.com/753482](https://crbug.com/753482)
  -  [https://crbug.com/756434](https://crbug.com/756434)


# Release Notes sheriff-o-matic 2017-08-15

- 6 commits, 5 bugs affected since  (2017-08-08)
- 5 Authors:
  - vadimsh@chromium.org
  - chanli@chromium.org
  - zhangtiff@google.com
  - martiniss@chromium.org
  - seanmccullough@chromium.org

## Changes in this release

- [[SoM-Findit] Add new message format for Findit auto_committed reverts.](https://chromium-review.googlesource.com/607391) (chanli@chromium.org)
- [SoM: Upgrade all elements to ES6 syntax.](https://chromium-review.googlesource.com/602620) (zhangtiff@google.com)
- [Rename github.com/luci/{luci-go,gae} to go.chromium.org/{luci,gae}](https://chromium-review.googlesource.com/607355) (vadimsh@chromium.org)
- [SOM: Remove old test results client](https://chromium-review.googlesource.com/602888) (martiniss@chromium.org)
- [[som] Fix retry logic so 4xx responses don't get retried.](https://chromium-review.googlesource.com/614316) (seanmccullough@chromium.org)
- [[som] Remove old findit calls from client.go, delegate to findit.go](https://chromium-review.googlesource.com/609466) (seanmccullough@chromium.org)


## Bugs updated, by author
- chanli@chromium.org:
  -  [https://crbug.com/727954](https://crbug.com/727954)

- seanmccullough@chromium.org:
  -  [https://crbug.com/752141](https://crbug.com/752141)
  -  [https://crbug.com/755132](https://crbug.com/755132)

- vadimsh@chromium.org:
  -  [https://crbug.com/726507](https://crbug.com/726507)

- zhangtiff@google.com:
  -  [https://crbug.com/646101](https://crbug.com/646101)


# Release Notes sheriff-o-matic 2017-08-08

- 4 commits, 1 bugs affected since e22fada (2017-08-01T22:52:55Z)
- 2 Authors:
  - martiniss@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [Remove unneeded line from som-app.html](https://chromium-review.googlesource.com/602519) (martiniss@chromium.org)
- [SoM: Upgrade som-annotations.html](https://chromium-review.googlesource.com/602616) (zhangtiff@google.com)
- [SoM: Upgrade som-alert-category to ES6.](https://chromium-review.googlesource.com/598465) (zhangtiff@google.com)
- [SoM: Update webcomponents import.](https://chromium-review.googlesource.com/596775) (zhangtiff@google.com)

## Bugs updated, by author
- zhangtiff@google.com:
  -  [https://crbug.com/646101](https://crbug.com/646101)


# Release Notes sheriff-o-matic 2017-08-01

- 11 commits, 4 bugs affected since 1a1f932 (2017-07-25T23:32:04Z)
- 4 Authors:
  - jojwang@google.com
  - zhangtiff@google.com
  - seanmccullough@chromium.org
  - renjietang@google.com

## Changes in this release

- [SoM: Upgrade to Polymer 2.](https://chromium-review.googlesource.com/578383) (zhangtiff@google.com)
- [[som] logdiff tsmon: change to counter to CDF, add log sizes](https://chromium-review.googlesource.com/594969) (seanmccullough@chromium.org)
- [[som] Add progress indicator to logdiff loading](https://chromium-review.googlesource.com/596409) (seanmccullough@chromium.org)
- [[som] set retry limit for log diff tasks](https://chromium-review.googlesource.com/595192) (renjietang@google.com)
- [[som] Add service fakes to remove test flakes](https://chromium-review.googlesource.com/590485) (seanmccullough@chromium.org)
- [Fix edit dialog box bug.](https://chromium-review.googlesource.com/588001) (jojwang@google.com)
- [[som] Change some 500 responses to 400s to better reflect semantics](https://chromium-review.googlesource.com/587375) (seanmccullough@chromium.org)
- [[som] Track client-side navigations as pageviews in GA.](https://chromium-review.googlesource.com/587009) (seanmccullough@chromium.org)
- [[som] Use the trooper template for linking bugs to infra failures.](https://chromium-review.googlesource.com/585549) (seanmccullough@chromium.org)
- [[som] remove index](https://chromium-review.googlesource.com/585830) (renjietang@google.com)
- [[som] official: try to parse version from chrome_version build prop](https://chromium-review.googlesource.com/588115) (seanmccullough@chromium.org)


## Bugs updated, by author
- jojwang@google.com:
  -  [https://crbug.com/749199](https://crbug.com/749199)

- seanmccullough@chromium.org:
  -  [https://crbug.com/747438](https://crbug.com/747438)
  -  [https://crbug.com/747568](https://crbug.com/747568)

- zhangtiff@google.com:
  -  [https://crbug.com/646101](https://crbug.com/646101)


# Release Notes sheriff-o-matic 2017-07-25

- 16 commits, 5 bugs affected since d3ab915 (2017-07-18T22:11:23Z)
- 3 Authors:
  - seanmccullough@chromium.org
  - davidriley@chromium.org
  - renjietang@google.com

## Changes in this release

- [[som] add link to log](https://chromium-review.googlesource.com/585406) (renjietang@google.com)
- [[som] make collapsable](https://chromium-review.googlesource.com/582230) (renjietang@google.com)
- [[som] Move alert filter input below bug queue, closer to alerts.](https://chromium-review.googlesource.com/583530) (seanmccullough@chromium.org)
- [[som] de-dupe test names on the frontend.](https://chromium-review.googlesource.com/582201) (seanmccullough@chromium.org)
- [SoM: do not show resolved alerts for non-CrOS trees](https://chromium-review.googlesource.com/580515) (davidriley@chromium.org)
- [SoM: Split alerts retrieval into two calls.](https://chromium-review.googlesource.com/580029) (davidriley@chromium.org)
- [[som] merge diff data and only show diff link for chromium](https://chromium-review.googlesource.com/580354) (renjietang@google.com)
- [[som] Make test expectation editor deep-linkable to specfic tests.](https://chromium-review.googlesource.com/579794) (seanmccullough@chromium.org)
- [[som] fix LogDIff datastore ID](https://chromium-review.googlesource.com/580292) (renjietang@google.com)
- [[som] Fix QueuedUpdate ID field](https://chromium-review.googlesource.com/579657) (seanmccullough@chromium.org)
- [SoM: Add filtering of shown alerts via regexp.](https://chromium-review.googlesource.com/578480) (davidriley@chromium.org)
- [SoM: Add recently resolved section and unresolve action.](https://chromium-review.googlesource.com/576867) (davidriley@chromium.org)
- [[som] cleanup: move milo and monorail clients to register w/Context](https://chromium-review.googlesource.com/576560) (seanmccullough@chromium.org)
- [[som] add make target for remotely accessible devserver](https://chromium-review.googlesource.com/576858) (seanmccullough@chromium.org)
- [[som] Manually fix RELNOTES.md](https://chromium-review.googlesource.com/576660) (seanmccullough@chromium.org)
- [[som] Continue instead of returning on FindIt rpc errors](https://chromium-review.googlesource.com/582308) (seanmccullough@chromium.org)


## Bugs updated, by author
- davidriley@chromium.org:
  -  [https://crbug.com/693669](https://crbug.com/693669)
  -  [https://crbug.com/725591](https://crbug.com/725591)

- seanmccullough@chromium.org:
  -  [https://crbug.com/603982](https://crbug.com/603982)
  -  [https://crbug.com/712777](https://crbug.com/712777)
  -  [https://crbug.com/721501](https://crbug.com/721501)


# Release Notes sheriff-o-matic 2017-07-18

- 8 commits, 2 bugs affected since 95d93c0 (2017-07-12T22:25:49Z)
- 3 Authors:
  - renjietang@google.com
  - seanmccullough@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [[som] added frontend link](https://chromium-review.googlesource.com/575208) (renjietang@google.com)
- [[som] Make crrev service mockable so tests don't hit network.](https://chromium-review.googlesource.com/570991) (seanmccullough@chromium.org)
- [SoM: Fix comment timestamp.](https://chromium-review.googlesource.com/575356) (zhangtiff@google.com)
- [[som] fetch logs concurrently](https://chromium-review.googlesource.com/572034) (renjietang@google.com)
- [[som] add field of latest passing build](https://chromium-review.googlesource.com/571402) (renjietang@google.com)
- [[som] remove regex filter. Added master name to AlertedBuilder.](https://chromium-review.googlesource.com/570658) (renjietang@google.com)
- [[som] generalize tsmon to take multiple trees, but for now only chromium goes in](https://chromium-review.googlesource.com/569020) (renjietang@google.com)
- [[som] Update release notes](https://chromium-review.googlesource.com/569012) (seanmccullough@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/721501](https://crbug.com/721501)

- zhangtiff@google.com:
  -  [https://crbug.com/743181](https://crbug.com/743181)

# Release Notes sheriff-o-matic 2017-07-12

- 16 commits, 10 bugs affected since 2fa0645 (2017-06-27T22:39:09Z)
- 5 Authors:
  - chanli@chromium.org
  - bevc@google.com
  - seanmccullough@chromium.org
  - renjietang@google.com
  - zhangtiff@google.com

## Changes in this release

- [[som] logdiff: inline temp template](https://chromium-review.googlesource.com/568245) (seanmccullough@chromium.org)
- [[som] use datastore for diffs](https://chromium-review.googlesource.com/544785) (renjietang@google.com)
- [SoM: Fix resolve button.](https://chromium-review.googlesource.com/563466) (zhangtiff@google.com)
- [[SoM-Findit] Use commit_position instead of revision.](https://chromium-review.googlesource.com/560577) (chanli@chromium.org)
- [SoM: Add hint tooltips to give users more context on different features.](https://chromium-review.googlesource.com/553408) (zhangtiff@google.com)
- [[som] cleanup: remove milo alert diff handler, tsmon metrics](https://chromium-review.googlesource.com/558005) (seanmccullough@chromium.org)
- [SoM: Replace go links with goto.google.com](https://chromium-review.googlesource.com/549696) (zhangtiff@google.com)
- [SoM: Add severity title tooltips.](https://chromium-review.googlesource.com/557384) (zhangtiff@google.com)
- [[som] Remove deprecated layout test expectation values](https://chromium-review.googlesource.com/556463) (seanmccullough@chromium.org)
- [[som] Move task queue workers to backend (analyzer) service.](https://chromium-review.googlesource.com/556933) (seanmccullough@chromium.org)
- [Changing date format for comments on alerts](https://chromium-review.googlesource.com/556959) (bevc@google.com)
- [SoM: Add page to view all tree statuses.](https://chromium-review.googlesource.com/549075) (zhangtiff@google.com)
- [[som] Add status message, polling for async CL worker to expectations UI](https://chromium-review.googlesource.com/550602) (seanmccullough@chromium.org)
- [SoM: Remove flaky check from trooper alerts test.](https://chromium-review.googlesource.com/550979) (zhangtiff@google.com)
- [SoM: Add cron to update android bug queue.](https://chromium-review.googlesource.com/550843) (zhangtiff@google.com)
- [[som] Clean up client to remove CBE references.](https://chromium-review.googlesource.com/568623) (seanmccullough@chromium.org)


## Bugs updated, by author
- bevc@google.com:
  -  [https://crbug.com/726258](https://crbug.com/726258)

- chanli@chromium.org:
  -  [https://crbug.com/737709](https://crbug.com/737709)

- seanmccullough@chromium.org:
  -  [https://crbug.com/603982](https://crbug.com/603982)
  -  [https://crbug.com/737720](https://crbug.com/737720)

- zhangtiff@google.com:
  -  [https://crbug.com/637341](https://crbug.com/637341)
  -  [https://crbug.com/707995](https://crbug.com/707995)
  -  [https://crbug.com/733672](https://crbug.com/733672)
  -  [https://crbug.com/737169](https://crbug.com/737169)
  -  [https://crbug.com/737724](https://crbug.com/737724)
  -  [https://crbug.com/739937](https://crbug.com/739937)

# Release Notes sheriff-o-matic 2017-06-27

- 8 commits, 4 bugs affected since 8e25b38 (2017-06-20T21:41:26Z)
- 2 Authors:
  - seanmccullough@chromium.org
  - zhangtiff@google.com

## Changes in this release

- [SoM: Make bug queue look for exact label matches.](https://chromium-review.googlesource.com/550557) (zhangtiff@google.com)
- [SoM: Fix internal builder links for milo.](https://chromium-review.googlesource.com/549091) (zhangtiff@google.com)
- [SoM: Make trooper tree use milo.](https://chromium-review.googlesource.com/549008) (zhangtiff@google.com)
- [SoM: Add tree-specific default snooze times and make autsnooze time configurable.](https://chromium-review.googlesource.com/549081) (zhangtiff@google.com)
- [SoM: Enable grouping for all trees.](https://chromium-review.googlesource.com/544083) (zhangtiff@google.com)
- [[som] Move CL-generating logic to async worker queue.](https://chromium-review.googlesource.com/543912) (seanmccullough@chromium.org)
- [[som] TA/DA: Break CL-generating logic into an async worker task](https://chromium-review.googlesource.com/541582) (seanmccullough@chromium.org)
- [[som] update RELNOTES.md for this week's push](https://chromium-review.googlesource.com/541605) (seanmccullough@chromium.org)


## Bugs updated, by author
- seanmccullough@chromium.org:
  -  [https://crbug.com/603982](https://crbug.com/603982)

- zhangtiff@google.com:
  -  [https://crbug.com/690852](https://crbug.com/690852)
  -  [https://crbug.com/736399](https://crbug.com/736399)
  -  [https://crbug.com/736838](https://crbug.com/736838)


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
