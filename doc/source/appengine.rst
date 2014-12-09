Developing an appengine application
===================================

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


Managing AppEngine apps
-----------------------
A convenience script wrapping ``appcfg.py`` called ``gae.py`` can be used to
simplify and normalize the deployment process in ``infra.git``. Just add a
symlink to it in your application. It is located in
``appengine/swarming/appengine/components/tools/gae.py``, but this location is
bound to change soon(c) (2014-12-05).

