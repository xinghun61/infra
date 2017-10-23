# vpython

[TOC]

Chrome Operations builds and maintains a tool called `vpython`, which
offers a simple, easy, reliable, and dependable mechanism for the instantiation
of arbitrary user-specified Python virtual environments for Operations and
client teams.

A `vpython` invocation looks largely like a standard `python` invocation, with
the notable difference of the tool name. `vpython` accepts Python interpreter
arguments and forwards them to an underying `python` interpreter, surrounding
the invocation with on-demand VirtualEnv setup and maintenance. See
[Invocation](#Invocation) for more information.

Alongside `vpython`, Chrome Operations also maintains several Python wheel
bundles for popular or necessary packages. See the
[Available Wheels](#Available-Wheels) section for a non-exhaustive list.

`vpython` takes a hermetic Python bundle and augments it with bundled Python
wheels using
[VirtualEnv](http://docs.python-guide.org/en/latest/dev/virtualenvs/) to create
an effective Python environment that is tailored to each script's needs.

A Python wheel is a pre-packaged formally-specified Python distribution. For
more information on wheels, see
[Wheel vs Egg](https://packaging.python.org/discussions/wheel-vs-egg/).
A wheel may be either universal, written in pure Python, or binary, including
binary content specialized to a specific operating system and/or architecture.

Users can expect that `vpython` will be available in `PATH` in a standard
Chromium development or bot environment.

`vpython` is deployed:

* Using `depot_tools`, through a bootstrap wrapper (
    [Windows](https://chromium.googlesource.com/chromium/tools/depot_tools/+/master/vpython.bat),
    [Linux and Mac](https://chromium.googlesource.com/chromium/tools/depot_tools/+/master/vpython)).
* In bot environments via `PATH`:
    * On BuildBot, it is installed into `PATH` using
      [cipd_bootstrap_v2](https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/slave/cipd_bootstrap_v2.py).
    * On LUCI, this is installed into `PATH` in the `luci-config` Swarming Task
      Template.

To reliably invoke `vpython` in both user and bot environments, Windows users
and scripts should use `vpython.bat` and Linux and Mac users should use
`vpython`.

## Tool Documentation

For documentation on the `vpython` tool itself, see:

* [Generic Tool Documentation](https://chromium.googlesource.com/infra/luci/luci-go/+/master/vpython)
* [Chrome Operations Implementation Documentation](https://chromium.googlesource.com/infra/infra/+/master/go/src/infra/tools/vpython)

For information about using `vpython` in a Chrome Operations environment,
continue reading.

## Usage

A user leverages `vpython` by:

1. Building a [specification protobuf](#Specification-Protobuf) describing their
   Python program's layout.
2. [Invoking](#Invocation) their Python script through `vpython`.

In the expected case, Chrome Operations will have already created wheel packages
for all of the dependencies, and the user just has to pick and choose from that
list. See [Available Wheels](#Available-Wheels) for the most recent list of
available Python wheels.

Some packages or wheel combinations are non-trivial and frequently used. To
facilitate their inclusion, `vpython` specification snippets for these packages
are included in the [Templates](#Templates) section.

Prior to critically depending on `vpython`, please review its
[Caveats](#Caveats).

## Walkthroughs

Below are some simple walkthroughs that a user can use to get a feel for the
`vpython` installation process.

### Walkthrough (Simple Script)

The goal of this walkthrough is to take a script and transform it so that it
works in `vpython`. For example purposes, the script will be very simple: it
wants to use `psutil` to get a count of running processes on the current system.

The Python script, `test.py`, looks like:

```python
#!/usr/bin/env python

import psutil
print 'Number of running processes is:', len(psutil.pids())
```

As-is, this script may or may not work, depending on whether or not the target
system has the `psutil` package installed. Let's try running it on our developer
system:

```bash
python ./test.py
Number of running processes is: 1337
```

Great, ship it! Well, first let's try running it on a bot:

```bash
python ./test.py
Traceback (most recent call last):
  File "test.py", line 3, in <module>
    import psutil
ImportError: No module named psutil
```

Yikes! File an infra ticket! But wait, another bot yielded:

```bash
python ./test.py
Number of running processes:
Traceback (most recent call last):
  File "test.py", line 4, in <module>
    print 'Number of running processes:', len(psutil.pids())
AttributeError: 'module' object has no attribute 'pids'
```

On this system, there is a `psutil`, but it's really old and doesn't have the
`pids` member. Let's file an infra ticket to upgrade it on all bots ... but now
some other builder is red because it depended on that older version...

Enter VirtualEnv (featuring `vpython`)!

We can use `vpython` to download `psutil` and create a VirtualEnv just for this
script! Because we have a separate, hermetic, and isolated VirtualEnv for this
script, it will **not** interfere with other system installations or other
scripts. Other scripts may continue to work as they always have, may use
`vpython` themselves with the same package set (in which case this VirtualEnv
will be re-used) or may choose their own package set with their own wheel
versions.

```bash
vpython ./test.py
Traceback (most recent call last):
  File "test.py", line 3, in <module>
    import psutil
ImportError: No module named psutil
```

This makes sense - we didn't create a specification that includes `psutil`, so
sans specification, `vpython` created a standard, empty VirtualEnv. This
behavior would be observed on any of the three prior systems, though, so already
we have (albeit broken) consistency down. Now, let's add `psutil` to the
`vpython` specification.

This is a single script, but we (pretend) downloaded it from an external source,
so modifying it to have an [Embedded specification](#embedded-specification) is
not an option. Let's choose to create a
[Script-Specific specification](#script_specific-specification) file for this
script so we can externally describe its dependencies to `vpython`.

We note in the [Available Wheels](#Available-Wheels) section that a wheel
for `psutil` is already defined. We'll use this one for the script.

Because the script is called `test.py`, we edit a file called
`test.py.vpython` in the same directory as `test.py`:

```protobuf
python: "2.7"
wheel: <
  name: "infra/python/wheels/psutil/${vpython_platform}"
  version: "version:5.2.2"
>
```

Now, when we run `test.py` through `vpython`, we get:

```bash
vpython ./test.py
Number of running processes is: 1337
```

This will work on developer system and bots, using the same versions and
packages! We have a functional script that will behave consistently on all
target platforms.

Before we finish, let's update the shebang line in `test.py` to mark that it
should be called through `vpython` instead of `python` directly:

```python
#!/usr/bin/env vpython
# (...)
```

In summary:

  1. Identify which wheels were needed, referencing the
     [Available Wheels](#Available-Wheels) section.
  1. Build a `vpython` specification file referencing the necessary wheels.
  1. Configure the script to run through `vpython`.

## Basics

`vpython` is a thin wrapper around a Python invocation. It accepts the same
command-line options as Python, and in most cases can be used in place of a
direct `python` command invocation. When run, `vpython`:

1. Identifies a VirtualEnv spec to use. This may be:
    * [Embedded](#embedded-specification) in the script being invoked.
    * [Located alongside](#script_specific-specification) the script being
      invoked.
    * [Located in a parent directory](#common-specification) of the script being
      invoked.
    * Specified explicitly via the `-vpython-spec` command-line flag.
2. Resolves the Python interpreter and its version from `PATH`.
    * Note in Chrome Operations deployments, this will resolve to the hermetic
      Chrome Operations Python bundle.
3. Generates a unique identifier for this (interpreter, spec) combination.
4. Instantiates an empty VirtualEnv for that identifier.
5. Resolves the set of wheels to install (if any) from the specification.
6. Installs those wheels into the identifier's VirtualEnv.
7. Invokes the VirtualEnv's Python interpreter with the remaining Python
   flags.

If the VirtualEnv for a given identifier is already established, `vpython`
operates near-instantly and completely offline, falling through to the direct
invocation of the interpreter. If the VirtualEnv does not exist or is
incomplete, `vpython` will pause at invocation to create the specified
VirtualEnv. This pause is generally proportional to the number of packages
in the specification, and is on the order of seconds.

## Specification Protobuf

The `vpython` specification is a text-format protocol buffer file that follows
[spec.proto](https://chromium.googlesource.com/infra/luci/luci-go/+/master/vpython/api/vpython/spec.proto).

Generally, a specification will be very simple, naming a Python interpreter
version and the set of CIPD packages to use with it. Some environments require
additional or conditional logic to setup, and may include other message fields.

For more information on how specification files are identified, see the
`vpython` tool [documentation](#Tool-Documentation).

### CIPD Wheel Packages

All dependencies used by Chrome Operations `vpython` are pulled from CIPD, a
Chrome Operations secure package deployment tool. Individual packages are
specified as a combination of a `name` and `version`.

See [Available Wheels](#Available-Wheels) for examples and more information.

In a CIPD `vpython` package:

* The `name` is a CIPD path to the wheel package. Names should begin with
  `infra/python/wheels`.
    * Universal packages, packages that are pure-Python and aren't bound to any
      specific operating system or architecture, will be simply named after
      their package.
    * Binary packages, packages that contain specific binary components binding
      them to a given architecture and operating system, will include their
      constriants (Python version, OS, architecture) in their package name. One
      such package must be individually uploaded for each platform that needs to
      use that package, containing binaries specific to that platform.
    * Templating can be used to have a single package string expand to the
      correct package name for the platform on which it's run.
    * See
      [CIPD Templating](https://chromium.googlesource.com/infra/infra/+/master/go/src/infra/tools/vpython#cipd-templating)
      for details.

Before thinking too much about this, it is highly likely that the package
name for a package that you need is already specified in the
[Available Wheels](#Available-Wheels) section.

### Specification Probing

In order for `vpython` to invoke a script, it must pair it with a `vpython`
[Specification Protobuf](#Specification-Protobuf) that specifies the VirtualEnv
that the script should be run in.

`vpython` offers a variety of options for a user to pair a specification with
a script or collections of scripts. The user should choose a method that is
appropriate based on their software.

Some Recommendations (see below for specifics):

* For an individual script, use an [Embedded](#embedded-specification) or
  [Script-Specific](#script_specific-specification) specification.
    * Embedding has the advantage of implicitly accompanying the script if/when
      it gets copied elsewhere.
* If your entire collection of scripts wants to share the same environment,
  use a single
  [Common Specification](#common-specification) (`.vpython`) at the root
  of your script collection.

If you are uncertain about which option is best for your script or project,
please [contact Chrome Operations](#Contact).

#### Script-Specific Specification

A specification protobuf can be dropped alongside a Python script to implicitly
pair `vpython` with the script.

For a script named `foo.py`, a `vpython` specification would appear in the same
directory alongside it and be named `foo.py.vpython`.

* foo.py.vpython
  ```protobuf
  python: "2.7"
  wheel: <
    name: "infra/python/wheels/coverage/${vpython_platform}"
    version: "version:4.3.4"
  >
  ```

* foo.py
  ```python
  #!/usr/bin/env vpython

  """This is my cool script. It does a lot of stuff. It needs "coverage" though.

  It runs in a VirtualEnv specified by "foo.py.vpython".
  """

  import os
  import coverage

  print coverage.__version__
  ```

When this script is invoked by `vpython`, its specification will be identified
in the filesystem and automatically loaded.

```bash
vpython foo.py
4.3.4
```

#### Embedded Specification

An individual script (e.g., `example.py`) may include a specification in the
script body, likely in a comment block or block string. The specification is
read by `vpython` as the contents between lines containing `[VPYTHON:BEGIN]` and
`[VPYTHON:END]` bookends. The contents between those bookends are interpreted
as a specification text protobuf.

Comment characters are stripped from the beginning of each line.

For example:

* foo.py
  ```python
  #!/usr/bin/env vpython

  """This is my cool script. It does a lot of stuff. It needs "coverage" though.
  """

  # [VPYTHON:BEGIN]
  # wheel: <
  #   name: "infra/python/wheels/coverage/${vpython_platform}"
  #   version: "version:4.3.4"
  # >
  # [VPYTHON:END]

  import os
  import coverage

  print coverage.__version__
  ```

When this script is invoked by `vpython`, its specification will be parsed from
the script content based on the presence of the bookend strings and
automatically loaded.

```bash
vpython foo.py
4.3.4
```

#### Common Specification

If an individual or embedded specification cannot be found, `vpython` will probe
walk filesystem towards root (or `.gclient` root) looking for a common
specification file. This file must be named `.vpython` and be located in
or above the directory of the invoked script.

Comment characters are stripped from the beginning of each line.

For example:

* .vpython
  ```protobuf
  python: "2.7"
  wheel: <
    name: "infra/python/wheels/coverage/${vpython_platform}"
    version: "version:4.3.4"
  >
  ```

* tools/foo.py
  ```python
  #!/usr/bin/env vpython

  """This is my cool script. It does a lot of stuff. It needs "coverage" though.

  It runs in a VirtualEnv specified by "foo.py.vpython".
  """

  import os
  import coverage

  print coverage.__version__
  ```

When this script is invoked by `vpython` will walk up from `tools/`, identify
`.vpython` in a parent directory, and automatically load it.

```bash
vpython tools/foo.py
4.3.4
```

### Example (Recipe Engine)

An example tool which uses `vpython` is the Recipe Engine. It contains a fairly
complicated specification that pulls in, among other things, the complete
`cryptography` Python package.

It is available for study
[here](https://chromium.googlesource.com/infra/luci/recipes-py/+/master/bootstrap/venv.cfg).

## Invocation

A `vpython` environment can be invoked directly or with explicit support in
Chrome Operations tooling.

### Via Recipe

Python scripts are invoked from recipes using the `python`
[recipe module](https://chromium.googlesource.com/infra/luci/recipes-py/+/master/README.recipes.md#recipe_modules-python).

The Python invocation accepts a keyword argument, `venv`.

* Setting `venv` to the path of a `vpython` specification file will cause that
  script to be invoked via `vpython` in that specification's VirtualEnv.
* Setting `venv` to `True` will invoke the script through `vpython`, having
  `vpython` probe the specification from the target script.

For more information on specification probing, see the section on
[Specification Probing](#specification-probing).

### Via Command-Line

Scripts can be invoked using `vpython` by replacing the Python command-line
option with `vpython`.

```bash
vpython /path/to/script.py
```

An explicit specification can be referenced using the `-spec` flag.  Run
`vpython -help` for more information.

If you don't provide an explicit specification (recommended),
[Specification Probing](#specification-probing) will be used to determine which
specification your script should use.

### Propagating VirutalEnv

If your script is invoking another Python script, it will likely work without
modification. This is because `vpython` adds its VirtualEnv's `bin/` directory
to `PATH` during invocation, causing other `python` invocations to automatically
inherit the VirtualEnv (and `PATH`).

However, a few standard guidelines should be followed:

* When invoking a Python script from another Python script, use
  `sys.executable` at the beginning of invocation. This prevents cases where
  a Python script explicitly specifies a Python interpreter in its shebang
  line (e.g., `#! /usr/bin/python`).
* In shebang lines, use `/usr/bin/env` instead of directly referencing a Python
  interpreter. If you know you want to use `vpython` exclusively, you can
  directly reference it instead of `python`.
  ```bash
  #!/usr/bin/env python
  ```

## Caveats

### Offline Availability

`vpython` loads packages from `CIPD`, a Chrome Operations online package
deployment service, during initial invocation. Users wishing to ensure that a
checkout is usable offline should pre-instantiate that checkout's `vpython`
virtual environments by invoking a `vpython` installation command in their
`gclient runhooks` process.

```
vpython -vpython-spec /path/to/vpython.spec -vpython-tool install
```

### No Dependency Resolution

Unlike `pip` or other Python tools, `vpython` does not perform dependency
resolution. It is up to the user constructing a `vpython` environment
specification to ensure that all immediate and transitive package dependencies
are included in that specification.

This design decision was not made lightly. Package and dependency management
carry a whole can of worms with them, including package expression requirements,
non-linear time for package identification, and dependency version resolution
requirements.

As a trade-off, we ask that users perform a one-time manual expansion of
dependencies when constructing a `vpython` specification.

Tooling can be developed to facilitate construction of `vpython` specifications 
if this is problematic or a pain point.

## Available Wheels

`vpython` wheels are stored in CIPD. A list of wheel packages in the
`infra/python/wheels` space can be viewed
[here](https://chrome-infra-packages.appspot.com/#/?path=infra/python/wheels).

A list of wheels that Chrome Operations produces using a wheel production
script, `dockerbuild`, can be found
[here](/infra/tools/dockerbuild/wheels.md).

If a wheel is needed, but is not in this list, please
[contact Chrome Operations](#Contact).

## Templates

Below are some templates for commonly used `vpython` wheel bundles.

### requests 2.13.0 / cryptography 1.8.1

This template can be used to include `requests`. The largest transitive set
of dependencies that `requests` has is derived from the `cryptography` package.

```protobuf

wheel: <
  name: "infra/python/wheels/requests-py2_py3"
  version: "version:2.13.0"
>

##
# BEGIN "cryptography" dependencies.
##

wheel: <
  name: "infra/python/wheels/cryptography/${vpython_platform}"
  version: "version:2.0.3"
>

wheel: <
  name: "infra/python/wheels/appdirs-py2_py3"
  version: "version:1.4.3"
>

wheel: <
  name: "infra/python/wheels/asn1crypto-py2_py3"
  version: "version:0.22.0"
>

wheel: <
  name: "infra/python/wheels/enum34-py2"
  version: "version:1.1.6"
>

wheel: <
  name: "infra/python/wheels/cffi/${vpython_platform}"
  version: "version:1.10.0"
>

wheel: <
  name: "infra/python/wheels/idna-py2_py3"
  version: "version:2.5"
>

wheel: <
  name: "infra/python/wheels/ipaddress-py2"
  version: "version:1.0.18"
>

wheel: <
  name: "infra/python/wheels/packaging-py2_py3"
  version: "version:16.8"
>

wheel: <
  name: "infra/python/wheels/pyasn1-py2_py3"
  version: "version:0.2.3"
>

wheel: <
  name: "infra/python/wheels/pycparser-py2_py3"
  version: "version:2.17"
>

wheel: <
  name: "infra/python/wheels/pyopenssl-py2_py3"
  version: "version:17.2.0"
>

wheel: <
  name: "infra/python/wheels/pyparsing-py2_py3"
  version: "version:2.2.0"
>

wheel: <
  name: "infra/python/wheels/setuptools-py2_py3"
  version: "version:34.3.2"
>

wheel: <
  name: "infra/python/wheels/six-py2_py3"
  version: "version:1.10.0"
>

##
# END "cryptography" dependencies.
##
```

## FAQ

### What is a Python Wheel?

A Python wheel is a pre-packaged formally-specified Python distribution. For
more information on wheels, see
[Wheel vs Egg](https://packaging.python.org/discussions/wheel-vs-egg/).
A wheel may be either universal, written in pure Python, or binary, including
binary content specialized to a specific operating system and/or architecture.

Chrome Operations strongly prefers wheels over eggs, since the latter may
include compilation steps which, in turn, result in system-specific variance and
unmanaged system dependencies (compiler, headers, etc.).

### Is vpython safe for concurrent usage?

TL;DR: Yes, and the overhead of sharing a VirtualEnv across `N` `vpython`
instances is effectively the same as using it with a single instance!

`vpython` uses filesystem locking during VirtualEnv mutations to ensure that it
has exclusive access. If multiple `vpython` instances want to operate on the
same VirtualEnv, they will serialize.

This means that if you start 1000 `vpython` instances with the same
specification, one will sieze the lock and instantiate it, while the others
block. Once the VirtualEnv is created, the remainder will immediately recognize
the set-up environment and start their script.

### Do vpython VirtualEnvs get cleaned up?

Short answer: yes. At the beginning of a `vpython` run, it identifies any
VirtualEnv instances that haven't been used in a while and purges them.

### Are wheels cached?

Yes. `vpython`, through CIPD, caches wheel packages locally. If multiple
VirtualEnv are set-up, the cache will result in any overlapping packages
being downloaded once.

## Contact

Feel free to reach out to Chrome Operations if you have any questions or want to
discuss `vpython` integration design.

* `luci-eng@google.com`
* [File a Bug](https://bugs.chromium.org/p/chromium/issues/entry?template=Build%20Infrastructure)
