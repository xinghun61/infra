# appengine/

This directory contains appengine applications, one per subdirectory (the
testing framework relies on this assumption to list all tests). To be consistent
with appengine principles, each of these directories must contain everything it
needs to work. Code shared between several applications should live in
`appengine_modules/` and be symlinked into each application directory that needs
it.

# Creating an appengine application

## TL;DR

Create a new Appengine app by running `run.py infra.tools.new_app <app_name>`.

The script will create a minimal structure of a working Appengine app in
infra.git:

*  an app directory under `appengine/`, say `appengine/myapp`
*  `appengine/myapp/app.yaml`
*  `appengine/myapp/main.py` implements a trivial public endpoint.
*  `appengine/myapp/.expect_tests_pretest.py` is a symlink pointing at
   `appengine_modules/expect_tests_pretest.py`. This is required for
   testing, see below.
*  `appengine/myapp/.expect_tests.cfg` lists any third-party components
   that should be skipped by tests.
*  `appengine/myapp/components` (optional) points at
   `luci/appengine/components/components`. Most infra apps require
   authentication, and components/auth is our standard. Delete this
   link if your app does not use it, and edit `.expect_tests.cfg`
   appropriately.
*  `appengine/myapp/gae.py` points at
   `luci/appengine/components/tools/gae.py` (optional), a handy script
   for deploying and managing your app.
*  `appengine/myapp/test/main_test.py` (optional, but highly
   recommended) tests for main.py.


Example: the myapp application should live in `appengine/myapp`. To use
`appengine_module/testing_utils`, create a symlink to it in
`appengine/myapp/testing_utils`. The name should remain the same as
Python relies on directory names for its import system.

*** note
Note: symbolic links do not work on Managed VMs.
A workaround is to create a temporary deployment directory:

    rsync -L -r appengine/myapp /tmp/deploy_myapp
    pushd /tmp/deploy_myapp/myapp
    <deploy your app here>
***

# AppEngine Modules

The default module is configured in `app.yaml`. Any non-default module must be
configured in `module-<module_name>.yaml`.  This is how the `gae.py` script
will know you what modules you have.

## Testing

Tests included in AppEngine applications (classes deriving from
`unittest.TestCase`) are run by `test.py`. Some convenience functions to
help using the testbed server are included in
[appengine\_modules/testing\_utils](../appengine_modules/testing_utils).
Some examples can be found in
existing applications, and a simple test setup is also provided by the
`infra.tools.new_app` script.

See [Testing in infra.git](/docs/testing.md) for more details. In particular,
it's important to have a test file `tests/foo_test.py` for every source file
`foo.py`.

*** note
Note: for test code to be able to import modules from the AE SDK
(e.g. `endpoints`), some manipulation of `sys.path` has to be done by
`test.py`. This manipulation has to be performed in an
`.expect_tests_pretest.py` file located at the root of the appengine
app, with the content of `appengine_module/expect_tests_pretest.py`.
**Adding a symlink to that file should be enough for 99.99% of cases.**
(and yes, it's very hacky, we know).
***

## Managing AppEngine apps

A convenience script wrapping `appcfg.py` called `gae.py` can be used to
simplify and normalize the deployment process in `infra.git`. Just add a
symlink to it in your application as `gae.py`. It is located in
`luci/appengine/components/tools/gae.py`:

    cd myproject
    ln -s gae.py ../../../luci/appengine/components/tools/gae.py

Run `gae.py --help` to see what gae.py can do.
