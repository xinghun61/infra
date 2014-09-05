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
    eval "$(/path/to/infra/ENV/bin/register-python-argcomplete test.py)"

And that's it. You may want to put that in your .bashrc somewhere.


AppEngine
---------
Infra.git hosts several google appengine projects.  In order to support
ease of testing and pylint all of the python code for these projects
is stored in one shared python package "appengine_module".

In order to interface well with dev_appserver.py and appcfg.py individual
directories exist for the appengine projects under "appengine_apps".  Symlinks
exist from those directories back into appengine_module to expose the necessary
parts of the appengine_module package to run the app in question.

The 'appengine' directory holds the as-of-yet fully converted Appengine apps.
All of those should be split into appengine_apps and appengine_module pieces
and appengine_module should be renamed to 'appengine'.  See crbug.com/407734.
