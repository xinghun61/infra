# Recipes

Recipes are a domain-specific language (embedded in python) for specifying
sequences of subprocess calls in a cross-platform and testable way.

* [User guide](https://chromium.googlesource.com/external/github.com/luci/recipes-py/+/master/doc/user_guide.md)
* Recipes: [public](https://chromium.googlesource.com/chromium/tools/build.git/+/master/scripts/slave/recipes/);
  [internal](https://chrome-internal.googlesource.com/chrome/tools/build_limited/+/master/scripts/slave/recipes/).
* Recipe modules:
  [base library](https://chromium.googlesource.com/external/github.com/luci/recipes-py/+/master/recipe_modules/);
  [public](https://chromium.googlesource.com/chromium/tools/build.git/+/master/scripts/slave/recipe_modules/);
  [internal](https://chrome-internal.googlesource.com/chrome/tools/build_limited/+/master/scripts/slave/recipe_modules/).

## Recipe Roller

[Builder page](https://uberchromegw.corp.google.com/i/internal.infra.cron/builders/recipe-roller).

The recipe roller is a service that ensures that the pinned dependencies between
recipe repositories are kept up to date.  At the time of writing, the
dependencies between repositories are as in the following diagram:

              recipes-py
                /    \  \
               v      \  \
        depot_tools    )  \
                \     /   |
                 v   v    |
                 build    |
                   |      |
                   v      v
     build_internal_scripts_slave

The recipe roller rolls changes downward through this graph every 30 minutes.

### For recipe authors:

* If your change produced no expectation changes downstream, everything should
  just work.
* If your change produced some expectation changes downstream, you will get a
  review from recipe-roller@chromium.org with those changes.  If they look good,
  **you should CQ them**; if they don't, **you should revert the patch that
  caused them**.  Leaving a change un-rolled blocks other changes from being
  rolled, and will cause a build-up of changes that is hard to manage.

### For infra folks who need to understand more:

The recipe roller rolls changes downward through the graph using the following
process (taking build/ as the example of the repository we are rolling):

1. Find all revisions of recipes-py and depot\_tools which are newer than the
   pinned versions.
2. Ensure dependencies are consistent: Exclude any revisions where
   depot\_tools's pinned recipes-py does not match the recipes-py we are
   considering.
3. Run simulation\_test on each of these revisions, each of which can be clean
   (no expectation changes), dirty (expectations changes), or fail (something
   else happened that can't be automatically fixed).
4. Roll to the latest clean revision we found, if there is one (this is called a
   'trivial' roll).
5. If there is a dirty revision after that, train expectations and upload a CL
   with the authors of the corresponding upstream CLs as reviewers.
6. If a simulation\_test train fails, recipe\_roller fails with a message
   indicating who and which CLs caused the failure.  When in doubt and a roll
   needs to happen, revert the offending upstream CL.

The roller has a lot of steps, so they are organized using collapsable nested
steps.  Each repository has a top-level step, containing the rolls and tests
for each revision.  After that, there is usually a `land` (for a clean roll)
and/or an `upload` (for a dirty roll) step, which will have a CL link within its
child steps.

If we seem to be rolling a lot of CLs into a repository (say 10 or more),
something is usually wrong.  This can be that a dirty CL was sent and hasn't
been committed -- the author may need a ping -- or that something else is going
wrong when trying to land the change.

luqui@ is the owner of the roller and can help find problems. martiniss@ and
iannucci@ also have some familiarity.
