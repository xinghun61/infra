Installation of infra.git
=========================

Checking out the code
---------------------
If you're reading this file, you're probably involved in the Chromium project
already. If this is not the case, you might want to read
`this page <http://dev.chromium.org/developers/how-tos/get-the-code>`_
to get some background information. In particular, depot_tools needs to be
installed by following instructions
`here <http://dev.chromium.org/developers/how-tos/install-depot-tools>`_.

The proper way to check out this repository is (assuming you have depot_tools
somewhere in your path) to run::

    mkdir chrome_infra   # or whatever name you please
    cd chrome_infra
    fetch infra

This will check out the base repository (infra.git) and its dependencies.

Troubleshooting
~~~~~~~~~~~~~~~
If you're not running a supported distribution, ``fetch infra`` will
probably fail complaining that it cannot find some packages on Cloud Storage.
This happens with architecture-dependent packages like numpy, which need to be
compiled. The workaround is to build the packages for yourself. Just run::

   infra/bootstrap/build_deps.py
   gclient runhooks

The first command will build the packages are store them locally. The second
command deploy them into ``infra/ENV``. For more details on this see
:doc:`bootstrap`.

