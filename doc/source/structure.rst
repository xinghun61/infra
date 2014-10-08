Structure of infra/ repository
==============================

Please also read the root README.md file in the source tree. The following
sections contain an overview of the directory layout. All paths are relative to
the root one, which means that infra/ refers to infra/infra/.

Entry points
------------
* run.py: wrapper script to run programs contained in subdirectories without
  having to deal with sys.path modifications. See README.md for details and
  invocation.
* test.py: multi-purpose script to run tests.
* infra/libs/: :doc:`reference/infra.libs` generally useful functions and classes
* infra/services/: standalone programs intended to be run as daemons (more
  details below)
* infra/tools: command-line tools, intended to be run by developers.
* appengine/: all Chrome-infra-managed appengine applications (more details
  below)
* infra/experimental: for, well, experimental stuff. Once they are stabilized,
  they should be moved in a more permanent place.


Miscellaneous technical stuff
-----------------------------
* bootstrap/: utilities to set up a proper Python virtual environment.
* infra/path_hacks: submodules of this modules give access to modules in the
  build/ repository (``from infra.path_hacks.common import <stg>`` is actually
  getting ``<stg>`` from build/scripts/common).
* utils/: purpose?
* misc/: purpose? difference with utils/?

infra/services/
---------------
* gnumbd: git numbering daemon. Adds a monotonically-increasing number to git
  commits.
* gsubtreed: ?
* lkgr_finder / lkgr_tag_pusher: computes last known good revision, based on
  test results.

appengine/ and appengine_modules/
---------------------------------
Contains all appengine applications.

