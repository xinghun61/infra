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

A package is defined in a *.yaml file that is parsed by `build.py` script before
being passed to the CIPD client.

The package file has the following structure:

```yaml
# Name of the package in CIPD repository.
package: infra/example/package
# Human readable description of the package.
description: Example package
# Optional list of Buildbot CI builders to build this package on. If not
# specified the package will be build on all CI builders. When build.py script
# is invoked manually (without --builder flag), this property is ignored.
builders:
  - infra-continuous-precise-64
  - ...
# If true, it means the package is friendly to different GOOS and GOARCH. If not
# set or false, this package will be skipped when doing cross-compilation.
supports_cross_compilation: true
# Optional list of OSes for which to build this package. Supported values: win,
# linux, mac, android
supported_platforms:
  - android
  - ...
# Optional list of go packages to 'go install' before zipping this package.
go_packages:
  - go.chromium.org/luci/cipd/client/cmd/cipd
  - ...
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

  # Exe files can also be augmented with *.bat shims, residing in same dir.
  # Kicks in only when the package is targeting Windows.
  - file: cipd.exe
    generate_bat_shim: true
```

Following features of the package definition are implemented by `build.py`
(basically anything related to the process of building the code and preparing
all necessary files for packaging):

* `builders`
* `supports_cross_compilation`
* `supported_platforms`
* `go_packages`
* `generate_bat_shim`


Strings interpolation
---------------------

Any string in package definition can reference a variable via ${var_name}, for
example:

```yaml
package: infra/tools/cipd/${platform}
```

Available variables are defined in [build.py](build.py) in `get_package_vars`:

* `${exe_suffix}` is `.exe` on Windows and empty string on other platforms. If
  cross-compiling to Windows, it is also set to `.exe` regardless of the host
  platform.
* `${platform}` defines where build.py is running (if not cross-compiling) or
  what the target platform is (when cross-compiling), as `(flavor)-(bitness)`
  string. It is suitable for packages that do not depend much on the exact
  version of the OS, for example packages with statically linked binaries.
  All possible combinations thus far:
    * linux-amd64
    * linux-386
    * linux-armv6l
    * mac-amd64
    * mac-386
    * windows-amd64
    * windows-386
* `${python_version}` defines python version as '(major)(minor)' string,
  e.g '27'. Not set when cross-compiling.

See [packages](packages/) for examples of package definitions.


Build script
------------

[build.py](build.py) script does the following:

* Ensures python virtual environment directory (ENV) is up to date.
* Rebuilds all necessary Go code from scratch and installs binaries into
  `GOBIN`.
* Enumerates `packages/` directory for package definition files, builds and
  (if `--upload` option is passed) uploads CIPD packages to
  [the repository](https://chrome-infra-packages.appspot.com).
* Stores built packages into `out/` (as `*.cipd` files).

Package definition files can assume that Go infra code is built and all
artifacts are installed in `GOBIN` (which is go/bin).

You can also pass one or more *.yaml file names to build only specific packages:

    build.py infra_python cipd_client


Verifying a package
-------------------

To install a built package locally use cipd client binary (it is built by
build.py as well). For example, to rebuild and install infra_python.cipd into
./install_dir, run:

    cd infra.git/
    rm -rf install_dir
    ./build/build.py infra_python
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

    ./build/build.py infra_python
    ./build/test_packages.py infra_python

test_packages.py is used on CI builders to verify packages look good before
uploading them.


Cross compilation of Go code
----------------------------

`build.py` script recognizes `GOOS` and `GOARCH` environment variables used to
specify a target platform when cross-compiling Go code. When it detects them, it
builds only Go packages that have `supports_cross_compilation` property set to
true in the package definition YAML. It also changes the meaning of
`${platform}` and `${exe_suffix}` to match the values for the target platform.

Built packages have `+${platform}` suffix in file names and coexist with native
package in build output directory. When uploading packages (via `build.py
--no-rebuild --upload`), `GOOS` and `GOARCH` are used to figure out what flavor
of built packages to pick (what `+${platform}` to search for).

Cross compiling toolset doesn't include C compiler, so the binaries are built in
`CGO_ENABLED=0` mode, meaning some stdlib functions that depend on libc are not
working or working differently compared to natively built executables.

In particular `os/user` doesn't work at all, and DNS resolution in `net` uses
different implementation.
