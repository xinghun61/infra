Installation of infra/
======================

Checking out the code
---------------------
If you're reading this file, you're probably involved in the Chromium project
already. If this is not the case, you might want to read
`this page <http://dev.chromium.org/developers/how-tos/get-the-code>`_
to get some background information. In particular, depot_tools needs to be
installed by following instructions
`here <http://dev.chromium.org/developers/how-tos/install-depot-tools>`_.

The proper way to check out this repository is (assuming you have depot_tools
somewhere in your path) to run:

::

    mkdir chrome_infra   # or whatever name you please
    cd chrome_infra
    gclient config https://chromium.googlesource.com/infra/infra.git
    gclient sync

This will check out the base repository (infra/) and its dependencies.


Bootstrapping Dependencies
--------------------------
The repository aims at being completely self-contained. It's using virtual
environments extensively to achieve that goal. Creating a environment should be
done once, after the initial checkout by running::

  ./bootstrap/bootstrap.py --deps_file bootstrap/deps.pyl

This is done for you automatically by ``gclient sync`` (or ``gclient runhooks``).

See ``bootstrap/README.md`` in the source code for more details.

