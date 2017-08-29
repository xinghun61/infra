# Python VirtualEnv

[TOC]

Lots of infrastructure, building, and testing code is built using Python. Chrome
Operations supports the deployment, management, and augmentation of basic Python
installation on infrastructure systems.

Chrome Operations currently supports **Python 2.7** on Windows, Linux, and Mac
OSX.

## Python Packages and VirtualEnv

Chrome Operations provides a bundled Python distribution. This Python
distribution is hermetic, ignoring system packages and software. The set of
packages available by default to a bundled Python version is fixed and deployed
within that bundle.

Using Python bundles enables Chrome Operations and its clients to reliably
create Python package sets, canary new Python distributions, and deploy bug- and
security fixes independently from underlying Operating System updates. This
results in reliability and long-term reproducibility of Python code and
programs.

With a hermetic Python bundle, traditional methods of deploying Python packages
(e.g., `pip`) are not available. Python hermetic bundle environments are
read-only, as they must be to satisfy hermeticity. Users oftentimes need to
augment the default Python package set, typically with public packages from
`pip` or [PyPi](https://pypi.python.org/pypi).  For this reason, Chrome
Operations has built a tool called [vpython](vpython.md) which allows Python
programs to explicitly request their dependencies.

[vpython](vpython.md) is designed to make the specification, instantiation, and
execution of VirtualEnv simple and reliable. Code that requires additional
Python packages will use `vpython` to start with a read-only hermetic python
bundle and augment it with specific packages in a disposable VirtualEnv,
producing a final Python environment that is fully specified and completely
under their control.

## FAQ

### Why not System Python?

POSIX systems typically include their own version of system Python and a set of
associated packages composed of:

* Packages that are part of the Python distribution.
* Additional system packages installed via the system package manager (e.g.,
  `apt-get`, `dpkg`).
* Additional packages pulled in during installation of Python-based tooling.
* Packages installed via Puppet.
* Packages installed by users manually via `pip`.

Because these sets of packages widely vary with the version and lifecycle of a
given system, they are not suitable for hard dependencies for infrastructure,
build, or test code.

Further, upgrading system Python involves upgrading all of the system software
and packages that depend on that Python. This makes system Python upgrades
necessarily heavy operations instead of the quick low-risk agility enabled by
using non-system bundles.

## Python on Chrome Operations Systems

Python versioning and dependencies have traditionally been managed differently
on different platforms. This is both a consequence of the fundamental
differences between those platforms and the native offerings of those platforms:

* Windows Python through `depot_tools` bootstrap.
* Linux and Mac Python is whatever the native operating system provides.

For security- and bug-related reasons, systems and users require a higher
standard of Python package management than that natively provided by the myriad
systems that Chrome Operations supports. Chrome Operations is solving this by
using hermetic deployable Python bundles built on top of CIPD. For more
information, see the [Python packaging](../packaging/python.md) section.

Python bundles are installed on and used in various parts of the system:

* A system-level bundle is deployed for system foundation software.
    * On Windows, this is installed at: `C:\infra-system\bin\python.exe`
    * On Mac and Linux, this is installed at: `/opt/infra-system/bin/python`
* A Python bundle is used per-build to run the Recipe Engine and its associated
  software, including building and testing code.
    * On BuildBot, this is implemented using
      [cipd_bootstrap_v2](https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/slave/cipd_bootstrap_v2.py).
    * On LUCI, this is installed in the `luci-config` Swarming Task Template.
* For legacy reasons, Windows systems still have a Python bundle installed
  in their build root `depot_tools` directory.
