Using the infra.git repository
==============================

This page supposes that infra.git has been checked out and configured. See
:doc:`installation` for more details.

Top-level commands
------------------

- Launching ``test.py test`` runs all tests in the infra repository in parallel, 
  including those in appengine applications. 

- ``run.py`` is used to run a command located inside the infra package. See
  next section for details.

- Regenerating this documentation from source is achieved with ``docgen.py``.
  (see :doc:`documenting` for more details)

Invoking tools
--------------

Mixing modules and scripts in the same hierarchy can sometimes be a pain in
Python, because it usually requires updating the Python path. The goal for
infra.git is to be able to check out the repository and be able to run code
right away, without setting up anything. The adopted solution is to use
__main__.py files everywhere.

Example: ``python -m infra.services.lkgr_finder`` will run the lkgr_finder
script.

To make things easier, a convenience script is located at root level. This will
do the same thing: ``run.py infra.services.lkgr_finder``. It also provides some
additional goodness, like listing all available tools (when invoked without any
arguments), and allowing for autocompletion.

If you want run.py to auto-complete, just run::

    # BEGIN = ZSH ONLY
    autoload -Uz bashcompinit
    bashcompinit
    # END   = ZSH ONLY

    eval "$(/path/to/infra/ENV/bin/register-python-argcomplete run.py)"
    eval "$(/path/to/infra/ENV/bin/register-python-argcomplete test.py)"

And that's it. You may want to put that in your .bashrc somewhere.

How it works on bots
--------------------
It is not checked-out on bots yet (September 2014)
