# Glyco - User Manual

Glyco is a tool to help working with Python wheel files locally. It is a small
wrapper on top of pip that is optimized to deal with Chrome-Infrastructure use
cases:

- Installing packages locally (not system wide)
- Distributing Python packages across repositories, providing exact pinning
  while making it clear where the source of truth is.
- Having full control on where packages are coming from, which essentially means
  not using PyPi but a Chrome Infrastructure-controlled depot.
- Using virtual environments and vendored packages.

Glyco handles wheel files only, because the format and the corresponding
installation process are straightforward.

Glyco strives to be as compatible as possible with what the Python community is
doing. One exception to this is the naming convention for wheel files. Glyco
generates file names with the SHA1 of the file content appended after the
version number, and expects that format when installing a package because it
checks that the content matches the hash.

Example:
`my_package-0.0.1-0_0b7c99e75dffea206eb281cdc29f8bfb51ee7dcd-py2-none-any.whl`


## TL;DR:
Installing a bare package from one repository into another is done using this
series of commands:

    $ cd <path/to/repo1>

    # Create mypackage/setup.cfg (if needed):
    $ cat << EOF > mypackage/setup.cfg
    [metadata]
    version = 0.0.1
    description = my nice package
    EOF

    # Create ~/wheelhouse/mypackage_0.0.1_<sha1>.whl:
    $ glyco pack -o ~/wheelhouse mypackage

    # Install in destination directory:
    $ cd <path/to/repo2>
    $ glyco install -i <third_party> ~/wheelhouse/mypackage_0.0.1_<sha1>.whl

And you have an installed package in `<third_party>`.


## Description of the pack and install commands

The example commands given in this section can be run from the Glyco source tree
directly.


### Creating a wheel file from a standard Python package

A standard Python package contains a setup.py.

    mkdir example
    ./glyco pack tests/data/source_package --output-dir example/wheels

This command creates a wheel in example_wheels/, called
`source_package-0.0.1-0_cc23f640f327c011096ce6958e33a304d71e1463-py2-none-any.whl`.
The SHA1 can vary, the compilation process is not (yet?) deterministic.


### Creating a wheel file from a bare Python package

A bare Python package essentially means a package that can be placed on sys.path
as-is. The targeted use case is distributing code that is part of a larger
program.

Glyco is able to create a wheel file just for a bare package provided a
`setup.cfg` file exists inside the package. This file contains very little
information: version number and a description (see
`tests/data/installed_package/setup.cfg` for the format). This solution is
restricted to pure Python packages.

Example: `tests/data/installed_package/`

    ./glyco pack tests/data/installed_package --output-dir example/wheels


### Installing wheel files locally
With the file from the step above:

    ./glyco install --install-dir example/local example/wheels/source_package-0.0.1-0_*-py2-none-any.whl

This creates `source_package` and `source_package-0.0.1.dist-info/` in
`example/local`. To be able to import the package you just need to add
`example/local` to the Python path.

Several packages can be installed at once by passing several files on the
command-line.

    ./glyco install --install-dir example/local example/wheels/*.whl
