Structure of the infra.git repository
=====================================

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
* bootstrap/: utilities to set up a proper Python virtual environment. More
  details about it can be found on this page: :doc:`bootstrap`.
* infra/path_hacks: submodules of this modules give access to modules in the
  build/ repository (``from infra.path_hacks.common import <stg>`` is actually
  getting ``<stg>`` from build/scripts/common).
* utils/: purpose?
* misc/: purpose? difference with utils/?

infra/services/
---------------
* gnumbd: git numbering daemon. Adds a monotonically-increasing number to git
  commits.
* gsubtreed: git subtree daemon. Mirrors subdirectories of some repositories
  into independent repos so they can be consumed by downstream projects.
* lkgr_finder / lkgr_tag_pusher: computes last known good revision, based on
  test results.

appengine/ and appengine_modules/
---------------------------------
``appengine/`` is meant to contain appengine applications, one per directory
(the testing framework relies on this assumption to list all tests).
To be consistent with appengine principles, each of these directories must
contain everything it needs to work. Code shared between several applications
should live in ``appengine_modules/`` and be symlinked into each application
directory that need it.

Example: the `myapp` application should live in `appengine/myapp`. To use
`appengine_module/testing_utils`, create a symlink to it in
`appengine/myapp/testing_utils`. The name should remain the same as Python
relies on directory names for its import system.

For more details, see :doc:`appengine`
