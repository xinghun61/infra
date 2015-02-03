Developing an appengine application
===================================

TL;DR
-----

The minimal structure of an Appengine app in infra.git is:

- an app directory under ``appengine/``, say ``appengine/myapp``
- ``appengine/myapp/app.yaml``
- ``appengine/myapp/.expect_tests_pretest.py`` shoud be a symlink pointing at
  ``appengine_module/expect_tests_pretest.py``. This is required for testing, see
  below. Not required if you're not planning to write any tests (but you should).
- ``appengine/myapp/gae.py`` can point at
  ``appengine/swarming/appengine/components/tools/gae.py`` (optional but handy).


Structure in infra.git
----------------------

Infra.git hosts several google AppEngine projects, located in the ``appengine/``
directory. Each subdirectory of ``appengine/`` is supposed to be a single
AppEngine application. Code shared between applications should live in
``appengine_modules/`` and be symlinked into application directories (the
AppEngine upload script ``appcfg.py`` follows symbolic links).


Testing of AppEngine applications
---------------------------------
Tests included in AppEngine applications (classes deriving from
``unittest.TestCase``) are run by ``test.py``. Some convenience functions to
help using the testbed server are included in
``appengine_modules/testing_utils``. Some examples can be found in existing
applications.

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
``appengine/swarming/appengine/components/tools/gae.py``, but this location is
bound to change soon(c) (2014-12-05).

