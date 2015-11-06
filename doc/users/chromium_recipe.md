# Chromium Recipes: Reference Doc

[TOC]

## Background
Chromium tests are currently run on buildbot, and are organized by builders.
A builder, in buildbot’s terminology, is a sequence of steps
(typically, individual commands) executed by a slave, and controlled by
the central master process.

Since such tightly controlled system is hard to maintain at scale, and requires
human attention and frequent downtimes for master restarts on every update,
Chrome Infra introduced [recipes](https://chromium.googlesource.com/external/github.com/luci/recipes-py/+/master/doc/user_guide.md).

A recipe is a single command executed as a single buildbot builder step
(called steps), which dynamically generates all the other steps. This moves the
control over steps from the master to the slaves, allows for dynamic creation of
steps at runtime, and, most importantly, eliminates the need for master restarts
when a builder configuration changes.

Recipe-based builders have a very generic configuration on the buildbot master,
and all the other specific configs live in recipes and recipe modules
(more on that later).

Additional requirement is to keep continuous integration (aka waterfall)
builders in sync with the tryserver (commit queue) builders.

## Life of a CL
To give recipes some context, let’s consider what a typical Chromium CL goes
through, from its inception to landing into the repository.

1. A developer clones Chromium repo locally, and makes a change.
1. The change is uploaded to Rietveld at http://codereview.chromium.org.
1. The developer may run manual try jobs (git cl try).
1. The change goes through the approval process, and eventually receives an LGTM.
1. The change is submitted to Commit Queue (CQ), which:
  1. Checks for a valid LGTM
  1. Runs all required try jobs - a subset of the equivalent waterfall jobs
  1. If all jobs succeed, commits the change to the repository.
1. Continuous Integration masters (waterfall) run the complete set of jobs on
the new revision (often batched with other revisions).
1. If all tests pass, the revision stays. Otherwise it may be reverted.

On a typical day, Chromium CQ may check up to 400 CLs, and land over 300 of
them. At peak times, CQ may land as many as 30 CLs every hour.

## Constraints and Requirements
In order for the system to function efficiently and reliably, several important
constraints are enforced.

* Speed: Each builder must be fast, to ensure short cycle time and efficient development.
  * Heavy tests are run in parallel using Swarming infrastructure
  * On the waterfall, compile and tests are split into two separate builders,
  so they can run in parallel, reducing the latency between each verified revision.
* Accuracy: CQ must guarantee correctness of CLs with high accuracy.
  * For capacity reasons, we cannot run tests on every single architecture in
  CQ, so only the most important subset is run.
  * It is very important for CQ jobs to run exactly the same steps (compile and
  test) as in the waterfall. Any discrepancy often leads to missed bugs and a
  broken tree.
* Reliability: CQ should land correct CLs, and reject incorrect ones.
  * In practice, false rejections will happen, but it is important to keep them
  to a minimum.
  * For that, CQ employs a sophisticated system of retries, and various
  heuristics determining when it is OK to give up on a CL.

## Implementation

Each of the requirements above needs a fairly complex and highly tuned system
to perform each step of the verification. Therefore, Chrome Infra provides a
common library of recipes implementing all of these requirements, and expects
developers to use it with minimum configuration on their part.

Currently, the following components are involved in configuring a builder:

### master.cfg/builders.pyl

  c['builders'] = `<list of builder specs>`

Each waterfall builder is specified using a dict like this
(example from [master.chromium.mac/master_mac_cfg.py](https://code.google.com/p/chromium/codesearch#chromium/build/masters/master.chromium.mac/master_mac_cfg.py&sq=package:chromium&l=55)
):

``` python
{
  'name': 'mac_chromium_rel_ng'
  'factory': m_annotator.BaseFactory(
      'chromium',     # name of the recipe
      factory_properties=None,  # optional factory properties
      triggers=[<list of triggered builders>]),
  'notify_on_missing': True,
  'category': '3mac',
}
```

Note the name of the recipe: `chromium`. Together with the name of the master
and builder, this fully determines the builder configuration in the master. All
the other details (specific steps) are configured in the recipe and recipe
modules.

Similarly, a tryserver builder is specified using `chromium_trybot` recipe (from [master.tryserver.chromium.mac/master.cfg](https://code.google.com/p/chromium/codesearch#chromium/build/masters/master.tryserver.chromium.mac/master.cfg&sq=package:chromium)
):

``` python
{
  'name': 'mac_chromium_rel_ng',
  'factory': m_annotator.BaseFactory('chromium_trybot'),
  # Share build directory [...] to save space.
  'slavebuilddir': 'mac'
}
```

Again, the recipe, master and builder names fully determine the configuration
on the master side. Changing how the builder is defined can now be done without
restarting the master.

### chromium.py: the main [waterfall] recipe

Path: [build/scripts/slave/recipes/chromium.py](https://code.google.com/p/chromium/codesearch#chromium/build/scripts/slave/recipes/chromium.py)

This is a very short “glue” recipe which reads the detailed configurations,
prepares the checkout, compiles the targets, and runs the tests. All the
specifics are done in a shared recipe module `chromium_tests`.

### chromium_trybot.py: the tryserver recipe, and trybot configs

Path: [build/scripts/slave/recipes/chromium_trybot.py ](https://code.google.com/p/chromium/codesearch#chromium/build/scripts/slave/recipes/chromium_trybot.py)

Each trybot (builder) is defined in terms of the corresponding main waterfall
builders. This config file is in
[build/scripts/slave/recipe_modules/chromium_tests/trybots.py](https://code.google.com/p/chromium/codesearch#chromium/build/scripts/slave/recipe_modules/chromium_tests/trybots.py&l=359)

```
'mac_chromium_rel_ng': {
    'mastername': 'chromium.mac',
    'buildername': 'Mac Builder',
    'tester': 'Mac10.8 Tests',
}
```

The recipe takes the corresponding compile and test configs, and adds the
tryserver specific logic, such as applying a patch from a CL, retrying compile
and failed tests without the patch, and failing / succeeding the build
appropriately.

In particular, if compile fails both with and without a patch, the entire job
fails. However, if a small portion of tests fails in the same way with and
without a patch, the job succeeds (the failures are assumed not because of the
CL, and are tolerable to continue the development).

This implements the requirement that try bots (CQ) are always in sync with the
waterfall builders. This recipe also uses the best proven retry strategies, thus
keeping CQ jobs robust and accurate.

### chromium_tests module: implements actual steps

Path: [build/scripts/slave/recipe_modules/chromium_tests/api.py](https://code.google.com/p/chromium/codesearch#chromium/build/scripts/slave/recipe_modules/chromium/api.py)

Implements methods like `configure_build`, `prepare_checkout`, compile, etc.
that take configuration parameters and actually run the steps.

### src/testing/buildbot/*.json: per-master configs: targets & tests

Example config: [src/testing/buildbot/chromium.mac.json](https://code.google.com/p/chromium/codesearch#chromium/src/testing/buildbot/chromium.mac.json&sq=package:chromium)

These configs live in the project repo, and define additional compile targets and specific tests to run on each builder.

## Creating a New Builder

* Add the builder configs to the corresponding master file in chromium recipe module
* Add the builder to `chromium_trybot.py` recipe (reference the above builder)
* Add the builder targets to the corresponding <master>.json file in src/testing/buildbot.
* Declare the new builder in master.cfg, assign it a recipe name and a slave pool (slaves.cfg). Restart the master.
* May need to provision hardware for the new slaves
* This has to be done both for the waterfall and the tryserver masters.

Note, that only adding builder targets to corresponding <master>.json file can
be tested on the tryserver. Therefore, the recommended way is to

* add the new builder config to `chromium_fyi.py`,
* add a trybot configuration derived from it to chromium_trybot.py,
* add the new trybot to the corresponding tryserver master (e.g. tryserver.chromium.linux/master.cfg),
* request the master restart, and
* test your builder on the tryserver (create a dummy Chromium CL, then ‘git cl try -b <your-new-trybot>’).

Chromium.fyi master doesn’t need to have a new builder configured in its master.cfg - this eliminates one master restart. However, for completeness, it makes sense to test the new builder on the waterfall as well.

Once everything is tested and the builder works, move the waterfall builder config to the appropriate main waterfall master (e.g. chromium.linux)

* Update its chromium recipe module config (e.g. `chromium_linux.py`)
* Update master config (e.g. `master.chromium.linux/master_linux_cfg.py`), and request the master restart
* Re-point `chromium_trybot.py` config to the new master. No tryserver master restart is needed.
