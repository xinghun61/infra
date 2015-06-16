Developing an appengine application
===================================

TL;DR
-----

Create a new Appengine app by running ``run.py infra.tools.new_app <app_name>``.

The script will create a minimal structure of a working Appengine app
in infra.git:

- an app directory under ``appengine/``, say ``appengine/myapp``
- ``appengine/myapp/app.yaml`` 
- ``appengine/myapp/main.py`` implements a trivial public endpoint.
- ``appengine/myapp/.expect_tests_pretest.py`` is a symlink pointing at
  ``appengine_module/expect_tests_pretest.py``. This is required for testing, see
  below. Not required if you're not planning to write any tests (but you should).
- ``appengine/myapp/.expect_tests.cfg`` lists any third party components that should be
  skipped by tests.
- ``appengine/myapp/components`` (optional) points at
  ``luci/appengine/components/components``.
  Most infra apps require authentication, and components/auth is our standard.
  Delete this link if your app does not use it, and edit
  ``.expect_tests.cfg`` appropriately.
- ``appengine/myapp/gae.py`` points at
  ``luci/appengine/components/tools/gae.py`` (optional)
  a handy script for deploying and managing your app.
- ``appengine/myapp/test/main_test.py`` (optional, but highly recommended)
  tests for main.py.


Structure in infra.git
----------------------

Infra.git hosts several google AppEngine projects, located in the ``appengine/``
directory. Each subdirectory of ``appengine/`` is supposed to be a single
AppEngine application. Code shared between applications should live in
``appengine_modules/`` and be symlinked into application directories (the
AppEngine upload script ``appcfg.py`` follows symbolic links).

Note: symbolic links do not work on managed VMs
(a.k.a. GAE v2).  A workaround is to create a temporary deployment directory::

  rsync -L -r appengine/myapp /tmp/deploy_myapp
  pushd /tmp/deploy_myapp/myapp
  <deploy your app here>

AppEngine Modules
~~~~~~~~~~~~~~~~~

The default module is configured in ``app.yaml``. Any non-default module must be
configured in ``module-<module_name>.yaml``.  This is how the ``gae.py`` script
will know you what modules you have.


Testing of AppEngine applications
---------------------------------

Tests included in AppEngine applications (classes deriving from
``unittest.TestCase``) are run by ``test.py``. Some convenience functions to
help using the testbed server are included in
``appengine_modules/testing_utils``. Some examples can be found in existing
applications, and a simple test setup is also provided by the
``infra.tools.new_app`` script.

See :doc:`testing` for more details, especially on testing Cloud Endpoints.  In
particular, it's important to have a test file ``test/foo_test.py`` for every
source file ``foo.py``.

Note that for test code to be able to import modules from the AE SDK (e.g.
``endpoints``), some manipulation of ``sys.path`` has to be done by ``test.py``.
This manipulation has to be performed in an ``.expect_tests_pretest.py`` file
located at the root of the appengine app, with the content of
``appengine_module/expect_tests_pretest.py``. **Adding a symlink to that file
should be enough for 99.99% of cases.** (and yes, it's very hacky, we know).


Managing AppEngine apps
-----------------------

A convenience script wrapping ``appcfg.py`` called ``gae.py`` can be used to
simplify and normalize the deployment process in ``infra.git``. Just add a
symlink to it in your application. It is located in
``luci/appengine/components/tools/gae.py``.

``./gae.py devserver``
  Run all modules in the local dev_appserver.

``./gae.py login``
  Authenticates with Google Cloud using OAuth2.

``./gae.py upload -A my-project-id``
  Deploys your app to the Cloud Project ``my-project-id``. If ``-A`` is omitted,
  uses the application ID from ``app.yaml``. It is advised to use the staging
  instance project ID in ``app.yaml`` (e.g. ``my-project-id-dev``), to avoid
  accidental deployments to production version.

``./gae.py switch``
  Set the default version for all modules. The command will list all deployed
  versions and suggest the latest one interactively.

``./gae.py help``
  Prints a help message.

``./gae.py [command] --help``
  Prints a help message for a specific command.
