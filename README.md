# infra.git repository

Welcome to the Chrome Infra repository!

Wondering where to start? Check out [General Chrome Infrastructure
documentation](doc/index.md). In particular, to check out this repo and the rest
of the infrastructure code, follow the instructions [here](doc/source.md).
The rest of this page is specific to this repo.

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
* [utils/](utils): purpose? utils?
* Need to bump infra/deployed to pick up changes?
    * `git push origin <updated hash>:deployed`
    * mail chrome-troopers@, include:
        * previously deployed hash (for quick rollback)
        * the hash you just pushed
        * the list of CLs that made this push necessary
        * the output of the `git push` command

## Integrating tests with test.py

If you've added a new module, integrate your tests with test.py:

1. Create a .coveragerc file in the root directory of the module you want to
   test. Take a look at another .coveragerc to see what to include in that.
1. Create a "test" directory in the root directory of the module you want to
   test. More your *_test.py files to this directory.

Double-check that your tests are getting picked up when you want them to be:
`./test.py test <path-to-package>`.

Tests still not getting picked up by test.py? Double-check to make sure you have
__init__.py files in each directory of your module so Python recognizes it as a
package.
