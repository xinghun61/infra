# Recipes ([go/recipe-docs](http://go/recipe-docs))

Recipes are a domain-specific language (embedded in python) for specifying
sequences of subprocess calls in a cross-platform and testable way.

* [User guide](https://chromium.googlesource.com/external/github.com/luci/recipes-py/+/master/doc/user_guide.md)
  * **NOTE:** This user guide is badly in need of updating as of August 2017. If
    you spot something wrong, please submit a CL to fix it.
* Recipe and recipe module documentation:
  * [recipe_engine](https://chromium.googlesource.com/infra/luci/recipes-py.git/+/master/README.recipes.md)
  * [depot_tools](https://chromium.googlesource.com/chromium/tools/depot_tools.git/+/master/recipes/README.recipes.md)
  * [build](https://chromium.googlesource.com/chromium/tools/build.git/+/master/scripts/slave/README.recipes.md)
  * [build internal](https://chrome-internal.googlesource.com/chrome/tools/build_limited/scripts/slave.git/+/master/README.recipes.md) (internal link)
  * [infra](https://chromium.googlesource.com/infra/infra.git/+/master/recipes/README.recipes.md)

## Recipe Roller

[Builder page (internal link)](https://uberchromegw.corp.google.com/i/internal.infra.cron/builders/recipe-autoroller-internal).

The recipe roller is a service that ensures that the pinned dependencies between
recipe repositories are kept up to date.  At the time of writing, the
dependencies between repositories are as in the following diagram:


     +----recipe_engine------------+
     |     |    |                  |
     |  +--+    |                  |
     |  |       |                  |
     |  |       v                  |
     |  |  depot_tools----------+  |
     |  |  |    |               |  |
     |  |  |    |               |  |
     |  |  |    v               v  v
     +------->build------->build_internal
        |  |      |
        |  +---+  |
        |      v  v
        +---->infra


The recipe roller rolls changes downward through this graph every 10 minutes.

Additionally, the roller tries to keep the skia and fuchsia infra repos up to
date as well.

### For recipe authors:

 * **"Trivial" Rolls:** If your change produced no expectation changes
   downstream, the roller will automatically CR+1 and CQ+2 the roll. The CQ may
   (depending on how its configuration), apply additional tests to the roll, but
   for the most part these rolls will go through without issue.

 * **"Non-trivial" Rolls:** If your change produced some expectation changes
   downstream, you will get a review from recipe-roller@chromium.org with those
   changes. if they look good, cr+1 and cq+2 them. if the if they don't look
   good, **revert the upstream patch** that's being rolled in. Leaving a change
   un-rolled blocks other changes from being rolled, and causes a build-up of
   changes that is hard to manage.

 * **"Error" Rolls:** Sometimes upstream changes cause errors when the roller
   operates that prevents the creation of a downstream patch. These always
   require manual resolution, usually in the form of a revert of the upstream
   patch, or a CL to the downstream repo. Examples of these sorts of rolls would
   be changing a function signature that's in use by downstream repos, or
   removing some piece of configuration from the upstream repo which is in use
   by the downstream repo. A good way to resolve these is to move the upstream
   code to the downstream repo. The best way to prevent these sorts of errors is
   to move the code downstream **first**, and then remove it from the upstream
   repo.


#### Roller implementation

For more information about the autoroller implementation, please refer to the:
  * [Roll algorithm implementation.](https://chromium.googlesource.com/infra/luci/recipes-py/+/master/recipe_engine/autoroll_impl/candidate_algorithm.py)
  * [Autoroller recipe module.](/recipes/README.recipes.md#recipe_modules-recipe_autoroller)
  * [Autoroller recipe.](/recipes/README.recipes.md#recipes-recipe_autoroller)
