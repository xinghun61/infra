# infra.git repository

Welcome to the Chrome Infra repository!

Wondering where to start? Check out [General Chrome Infrastructure
documentation](docs/index.md). The rest of this page is specific to this repo.

## Entry points

* [run.py](run.py): wrapper script to run programs contained in subdirectories
  without having to deal with `sys.path` modifications.
* [test.py](test.py): multi-purpose script to run tests.
* [infra\_libs/](infra_libs): generally useful functions and classes
* [infra/services/](infra/services): standalone programs intended to be run as
  daemons.
* [infra/tools](infra/tools): command-line tools, intended to be run by developers.
* [appengine/](appengine): many Chrome-infra-managed AppEngine applications
* [infra/experimental](infra/experimental): for, well, experimental stuff. Once
  they are stabilized and reviewed, they should be moved in a more permanent
  place.

## Miscellaneous technical stuff

* [bootstrap/](bootstrap): utilities to set up a proper Python virtual
  environment.
* [infra/path\_hacks](infra/path_hacks): submodules of this modules give access
  to modules in the build/ repository. `from infra.path_hacks.common import
  <stg>` is actually getting `<stg>` from
  [build/scripts/common](https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/common).
* [utils/](utils): purpose?
