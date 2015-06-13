Overview
--------

Scripts and files in this directory describe how to build CIPD packages from
the source code in infra.git repo.

There are two flavors of packages:

* Packages with executables compiled from Go code.
* Single giant package with all python code and archived virtual environment
  needed to run it.


Package definition
------------------

A package is defined in a *.yaml file with the following structure:

```yaml
# Name of the package in CIPD repository.
package: infra/example/package
# Human readable description of the package.
description: Example package
# Path to the root of the package source files on the system we're building
# the package from. Can be absolute or relative to the path of the *.yaml
# file itself.
root: ../..

data:
  # 'dir' section adds a subdirectory of 'root' to the package. In this case
  # it will scan directory <yaml_path>/../../a/b/c and put files into a/b/c
  # directory of the package.
  - dir: a/b/c
    # A list of regular expressions for files to exclude from the package.
    # Syntax is defined at http://golang.org/pkg/regexp/syntax/. Each expression
    # is implicitly wrapped into ^...$. The tests are applied to paths relative
    # to 'dir', e.g. 'bin/active' regexp matches only single file
    # <yaml_path>/../../a/b/c/bin/active.
    exclude:
      - bin/activate
      - .*\.pyc

  # 'file' section adds a single file to the package.
  - file: run.py
```

Any string in package definition can reference a variable via ${var_name}, for
example:

```yaml
package: infra/tools/cipd/${platform}
```

Available variables are defined in [build.py](build.py) in `get_package_vars`:

* `${exe_suffix}` is '.exe' on Windows and empty string on other platforms.
* `${platform}` defines where build.py is running, as '(flavor)-(bitness)'
  string. It is suitable for packages that do not depend much on the exact
  version of the OS, for example packages with statically linked binaries.
  Example values:
    * linux-amd64
    * linux-386
    * mac-amd64
    * mac-386
    * windows-amd64
    * windows-386
* `${os_ver}` defines major and minor version of the OS/Linux distribution.
  It is useful if package depends on *.dll/*.so libraries provided by the OS.
  Example values:
    * ubuntu14_04
    * mac10_9
    * win6_1
* `${python_version}` defines python version as '(major)(minor)' string,
  e.g '27'.

See [packages](packages/) for examples of package definitions.


Build script
------------

[build.py](build.py) script does the following:

* Ensures python virtual environment directory (ENV) is up to date.
* Rebuilds all infra Go code from scratch, with 'release' tag set.
* Enumerates packages/ directory for package definition files, builds and
  (if `--upload` option is passed) uploads CIPD packages to
  [the repository](https://chrome-infra-packages.appspot.com).
* Stores built packages into out/ (as *.cipd files).

Package definition files can assume that Go infra code is built and all
artifacts are installed in `GOBIN` (which is go/bin).

You can also pass one or more *.yaml file names to build only specific packages:

    build.py infra_python.yaml cipd_client.yaml


Verifying a package
-------------------

To install a built package locally use cipd client binary (it is built by
build.py as well). For example, to rebuild and install infra_python.cipd into
./install_dir, run:

    cd infra.git/
    rm -rf install_dir
    ./build/build.py infra_python.yaml
    ./go/bin/cipd pkg-deploy -root=install_dir build/out/infra_python.cipd
    cd install_dir


Package tests
-------------

test_package.py script can be used to run simple package integrity tests to
verify a built package looks good after deploy.

For each *.yaml in packages/* there can be corresponding *.py file in tests/*
that is invoked by test_package.py to check that deployed package looks good.

Basically test_package.py does the following:

* Installs a CIPD file to a local directory or update currently installed
  version there (if `--work-dir` is used).
* Runs `python test/<name>.py` with cwd == installation directory.
* If test returns 0, considers it success, otherwise - failure.

Thus to test that infra_python.cipd package works, one can do the following:

    ./build/build.py infra_python.yaml
    ./build/test_packages.py infra_python.cipd

test_packages.py is used on CI builders to verify packages look good before
uploading them.
