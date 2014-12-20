Bootstrapping the Chromium Infra Repo
=====================================

The infra/infra repo uses python [wheel files][1], [virtualenv][2] and [pip][3]
to manage dependencies. The process for bootstrapping these is contained
entirely within the ``bootstrap`` directory.

1: https://www.python.org/dev/peps/pep-0427/
2: https://github.com/pypa/virtualenv
3: https://github.com/pypa/pip


TL;DR - Workflows
~~~~~~~~~~~~~~~~~

Setting up the env with already-built-deps
++++++++++++++++++++++++++++++++++++++++++
Just run::

  gclient sync
  # OR
  gclient runhooks

Adding a new dep
++++++++++++++++
Say we want to add a stock `my_pkg` python package at version 1.2.3:

If it comes from a tarball::

  $ ./bootstrap/ingest_source.py <tarball>
  ...
  deadbeefdeadbeefdeadbeefdeadbeef.tar.gz

If it comes from a repo:

File a ticket to have it mirrored (no matter what VCS!)
to ``chromium.googlesource.com/external/<repo_url>``

Grab the git commit hash of the commit to build: badc0ffeebadc0ffeebadc0ffeebadc0

Then add the actual dep::

  $ edit bootstrap/deps.pyl  # add a new entry (see the 'deps.pyl' section)
  ...
    'my_pkg' : {
      'version': '1.2.3',
      'build': 0,  # This is the first build
      'gs':  'deadbeefdeadbeefdeadbeefdeadbeef.tar.gz',  # if tarball
      'rev': 'badc0ffeebadc0ffeebadc0ffeebadc0',         # if repo
    }
  ...

Then build it::

  $ ./bootstrap/build_deps.py
  # builds and uploads my_pkg-1.2.3-0_deadbeef...-....whl to google storage

**If your dep is not pure-python, you will have to run ``build_deps.py`` for
each platform.**


If your dep needs special treatment
+++++++++++++++++++++++++++++++++++
Do everything in the 'Adding a new dep' section, but before running
``build_deps.py``, add a file ``bootstrap/custom_builds/{wheel package name}.py``.
This file is expected to implement::

  def Build(source_path, wheelhouse_path)

See `custom builds`_ below for more detail.


``bootstrap.py`` (a.k.a. "I just want a working infra repo!")
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run ``gclient runhooks``. Under the hood, this runs::

  ./bootstrap/bootstrap.py --deps_file bootstrap/deps.pyl ENV

This creates a virtualenv called ``{repo_root}/ENV`` with all the deps contained
in ``bootstrap/deps.pyl``. You must be online, or must already have the wheels
for your system cached in ``{repo_root}/.wheelcache``.

If you already have an ``ENV``, ``bootstrap.py`` will check the manifest in
``ENV`` to see if it matches `deps.pyl`_ (i.e. the diff is zero). If it's not,
then ``ENV`` will be re-created *from scratch*.

``{repo_root}/run.py`` will automatically use the environment ``ENV``. It is an
error to use ``run.py`` without first setting up ``ENV``.


`deps.pyl`
~~~~~~~~~~
This file is a python dictionary containing the exact versions of all Python
module dependencies. These versions are the standard upstream package versions
(e.g. '0.8.0'), plus the commit hash or sha1.{ext} of an ingested source bundle
(see ``inject_source.py``).

The format of this file is ``{'package_name': <values>}``. This file is a Python
`ast literal <https://docs.python.org/2/library/ast.html#ast.literal_eval>`_, so
comments are allowed and encouraged.

Note that the ``package_name`` key is the pip-reported name (the one set in 
``setup.py``). It may be different from the name used for import, and for the
wheel.

Values are:
  * version: The pip version of the module
  * build: An integer representing which build of this version/hash. If you
      modify the _way_ that a requirement is built, but not the source hash, you
      can bump the build number to get a new pinned dependency.

And either:
  * ``rev``: The revision or sha1 of the source for this module.
    The repo is
      ``git+https://chromium.googlesource.com/infra/third_party/{package_name}``
  * ``gs``: ``{sha1}.{ext}`` indicates file
    ``gs://chrome-infra-wheelhouse/sources/{sha1}.{ext}``. The sha1 will be
    checked against the content of the file.

And optionally:
  * ``implicit``: A boolean indicating that this dep should only be installed as
    a dependency of some other dep. For example, you want package A, which
    depends on package Z, but you don't really care about Z. You should mark
    Z as ``implicit`` to allow it to be pinned correctly, but not to
    deliberately install it.


``ingest_source.py``
~~~~~~~~~~~~~~~~~~~~
Some python modules don't have functional python repos (i.e. ones that pip
can natively clone+build), and thus ship their source in tarballs. To ingest
such a tarball into the infra google storage bucket, use
  `ingest_source.py /path/to/archive`.
This will print the value for the 'gs' key for a `deps.pyl` entry.


`build_deps.py` / rolling deps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Any time a new dependency/version is introduced into ``deps.pyl``, you must run
``build_deps.py``. If the dependency is a pure-Python dependency (i.e. no compiled
extensions), you only need to run it once on CPython 2.7. You can tell that it's
a pure python module by looking at the name of the wheel file. For example::

  requests-2.3.0-py2.py3-none-any.whl

Is compatible with Python 2 and Python 3 (py2.py3) any python ABI (none), and
any OS platform (any).

If the module does contain compiled extensions, you must run ``build_deps.py``
on the following systems (all with CPython 2.7):
  * OS X 10.9 - ``x86_64``
  * Windows 7 - ``x86_64``
  * Linux     - ``x86_64``

TODO(iannucci): Add job to build wheels on all appropriate systems.

Once a wheel is sucessfully built, it is uploaded to
``gs://chrome-python-wheelhouse/wheels`` if it is not there already.

Running ``build_deps.py`` will only attempt to build dependencies which are
missing for the current platform.

``build_deps.py`` assumes that it can find ``gsutil`` on ``PATH``, so go ahead
and install it appropriately for whichever platform you're on. You will also
need write access to the ``chrome-python-wheelhouse`` bucket.


custom builds
~~~~~~~~~~~~~
Sometimes building a wheel is a bit trickier than ``pip wheel {repo}@{hash}``. In
order to support this, add a script named ``custom_builds/{name}.py``. This module
should have a function defined like::

  def Build(source_path, wheelhouse_path)

Where ``source_path`` is a string path to the checked-out / unpacked source code,
and ``wheelhouse_path`` is a string path where ``build_deps.py`` expects to find
a ``.whl`` file after Build completes.

Note that your Build function will actually need to invoke pip manually.
Currently you can get the path for pip by doing: ``os.path.join(sys.prefix,
'bin', 'pip')``, and you can invoke it with subprocess (see
https://code.google.com/p/chromium/codesearch#chromium/infra/bootstrap/custom...
as an example). 


rolling the version of wheel
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Since wheel is a package needed to build the wheels, it has a slightly different
treatment. To roll wheel, bump the version in deps.pyl, and then run
``bootstrap_wheel_wheel.sh``
to build and upload the wheel for ``wheel`` pinned at the version in ``deps.pyl``.

Once you do that, ``build_deps.py`` will continue working as expected.


Building deps on Windows
~~~~~~~~~~~~~~~~~~~~~~~~
TODO(iannucci): actually implement this

Windows builds require a slightly more care when building, due to the
complexities of getting a compile environment. To this effect, ``build_deps.py``
relies on the ``depot_tools/win_toolchain`` functionality to get a hermetic
windows compiler toolchain. This should not be an issue for chromium devs
working on windows, since they should already have this installed by compiling
chromium, but it's something to be aware of.


modified (non-upstream) deps
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If it is necessary to roll a patched version of a library, we should branch it
in the infra googlesource mirror. This branch should be named ``{version}-cr``,
and will build packages whose version is ``{version}.{cr_version}`` (e.g. modify
``setup.py`` on this branch to add an additional component to the version
field).

For example, given the package ``jane`` at version ``2.1.3``, we would create
a branch ``2.1.3-cr``. On this branch we would commit any changes necessary to
``2.1.3``, and would adjust the version number in the builds to be e.g.
``2.1.3.0``.


