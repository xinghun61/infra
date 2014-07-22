Contributing to the Chrome infra codebase
=========================================

This document explains how to contribute to the Chrome infrastructure codebase.
If you want to contribute to the Chromium browser, you're in the wrong place.
See
[http://dev.chromium.org/getting-involved](http://dev.chromium.org/getting-involved)
instead. You can find more information on the Chrome infrastructure
[here](http://dev.chromium.org/infra).

Checking out the code
---------------------
If you're reading this file, you're probably involved in the Chromium project
already. If this is not the case, you might want to read
[this page](http://dev.chromium.org/developers/how-tos/get-the-code)
to get some background information. In particular, depot_tools needs to be
installed by following instructions
[here](http://dev.chromium.org/developers/how-tos/install-depot-tools).

The proper way to check out this repository is (assuming you have depot_tools
somewhere in your path) to run:

    mkdir chrome_infra   # or whatever name you please
    cd chrome_infra
    gclient config https://chromium.googlesource.com/infra/infra.git
    gclient sync

This will check out the base repository (infra/) and its dependencies.


Bootstrapping Dependencies
--------------------------
(See `bootstrap/README.md` for more details).

Manually create a bootstrap virtualenv environment by running:

  `./bootstrap/bootstrap.py --deps_file bootstrap/deps.pyl`

This is done for you automatically by `gclient sync` (or `gclient runhooks`).


Invoking tools
--------------

Mixing modules and scripts in the same hierarchy can sometimes be a pain in
Python, because it usually requires updating the Python path. The goal for
infra/ is to be able to check out the repository and be able to run code right
away, without setting up anything. The adopted solution is to use __main__.py
files everywhere.

Example: `python -m infra.services.lkgr_finder` will run the lkgr_finder script.

To make things easier, a convenience script is located at root level. This will
do the same thing: `run.py infra.services.lkgr_finder`. It also provides some
additional goodness, like listing all available tools (when invoked without any
arguments), and allowing for autocompletion.

If you want run.py to auto-complete, just run:

    # BEGIN = ZSH ONLY
    autoload -Uz bashcompinit
    bashcompinit
    # END   = ZSH ONLY

    eval "$(/path/to/infra/ENV/bin/register-python-argcomplete run.py)"

And that's it. You may want to put that in your .bashrc somewhere.


External packages
-----------------

### Description

`infra/ext/` (short for "external") is intended for various python libraries.
This directory is populated by `gclient sync` using information from infra/DEPS.
The raw repositories are checked out, and used in-place. This requires a bit a
magic for imports to work properly (see `infra/ext/__init__.py` for details).
The framework assumes that the actual python packages to import are located
inside directories right under infra/ext.

Example: infra/ext/dateutil contains the dateutils repository checkout, and the
actual dateutil package is in infra/ext/dateutil/dateutil. In practice, dateutil
is imported using the 'from' syntax:

    from infra.ext import dateutil

`import infra.ext.dateutil` will __not__ work.


### Adding an external package in the ext directory

Only repositories hosted on chromium.googlesource.com should be used as source.
Adding something in infra/ext thus requires more than adding an entry into DEPS:

- create a new repository on chromium.googlesource.com
- populate it with a mirror of the third-party repository (e.g.:
  [https://github.com/jcgregorio/httplib2.git](https://github.com/jcgregorio/httplib2.git)
  is mirrored on
  [https://chromium.googlesource.com/infra/third_party/httplib2.git](https://chromium.googlesource.com/infra/third_party/httplib2.git))
- add an entry into infra/DEPS pointing to the mirror, at a given revision
  (not HEAD).
- add an 'import' entry into `infra/ext/__init__.py`. This is to enable
  autocompletion for tools like pylint and jedi.

The two first steps can only be performed by a limited set of people. Send an
email to infra-dev@chromium.org to request that.

