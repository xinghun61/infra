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


Adding an external package in the ext directory
-----------------------------------------------

infra/ext/ (short for "external") is intended for various python libraries. This
directory is populated by `gclient sync` using information from infra/DEPS. Only
repositories hosted on chromium.googlesource.com should be used as source. 
Adding something here requires those steps:

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

