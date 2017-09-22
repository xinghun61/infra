# vpython in Infra

For general information on `vpython` see its [LUCI code base
documentation](https://chromium.googlesource.com/infra/luci/luci-go/+/master/vpython).

The LUCI `vpython` code is a set of libraries that comprise the majority of
`vpython` functionality. Those libraries are linked together with a
domain-specific configuration ([this directory](.)) to form a `vpython` binary.
This document will detail the domain-specific aspects of the Infra `vpython`
deployment.

## Spec Building and Usage

The `vpython` VirutalEnv spec is a text protobuf that references wheels to
install into the VirtualEnv. Infra's `vpython` implementation uses CIPD for
package deployment. For more information, see
[CIPD Client and Packages](#CIPD-Client-and-Packages).

A user who wants to create a `vpython` spec for thier project should:

1. Determine which Python packages and versions are needed.
1. [Check CIPD](https://chrome-infra-packages.appspot.com/#/?path=infra/python/wheels/)
  to see which packages are available.
1. Construct a spec protobuf referencing these packages.

Packages that are not wholly universal will need to use
[CIPD templating](#CIPD-Templating) to express which packages should be used
on a given platform. If some packages are conditionally required by platform
(e.g., "Windows only"), the `match` protobuf directive can be used.

If a package or version of a package is missing, consult an Infra `vpython`
point of contact for assistance in building and uploading the package, or see
the [CIPD Package Layout](#CIPD-Package-Layout) section.

## Configuration

The Infra `vpython` version configures:

- Package installation via an integrated CIPD client.
- The default VirtualEnv package.
- Old `vpython` environment Pruning configuration.
- Default `vpython` package verification platforms.
- CIPD template extensions to allow resolution of PEP 425 tag parameters, and an
  algorithm for determining the PEP 425 tags to use for a given system.
- System-specific constraints.

For more information on the base configuration, see the `application.Config`
struct in this package.

## Implementation

### CIPD Client and Packages

The generic `vpython` library defines a `PackageLoader` interface, which
resolves an abstract "name" and "version" string pair into a set of Python
wheels to deploy. The CIPD `PackageLoader` implementation defines:

- "name" is a CIPD package name.
- "version" is a CIPD instance ID, "key:value" tag, or ref.
- The hostname of the Chrome Infrastructure CIPD service.

### CIPD Templating

In addition to the default CIPD templates (e.g., "platform"), this `vpython`
configuration enables some additional tags:

- **py_python** is the system's PEP 425 "python" field.
- **py_abi** is the system's PEP 425 "ABI" field.
- **py_platform** is the system's PEP 425 "platform" field.

A given system may expose several PEP 425 tag combinations. To view the
combination on a given system, run:

```python
import pip.pep425tags
pip.pep425tags.get_supported()
```

`vpython` must choose one set of those tags to use for template completion. It
does this through a preference algorithm that is implemented in this package.

### CIPD Package Layout

A `vpython` CIPD package is just a CIPD package that contains Python wheels.
Whatever wheels are in the CIPD package will be installed by `vpython`.

`vpython`'s wheel installation procedure is very simple:

1. Unpack all of the contents in all of the referenced packages into a single
  directory.
1. Scan through that directory and identify all wheel names and versions.
1. Install all of the wheels that were identified via `pip`, which will select
  which wheels should be installed based on the current system.

As such, a directory with multiple wheels that share a name and version but
differ by platform will result in a single wheel within that package that
matches the host platform being chosen and installed by `vpython` / `pip`.

So far, Infra has been following these general guidelines:

- A single CIPD package should hold a single wheel.
- CIPD wheel packages are named:
  - `infra/python/wheels/name/${platform}_${py_python}_${py_abi}`, for
    platform-specific wheels.
    - (For example, `infra/python/wheels/cryptography/linux-amd64_cp27_cp27mu`)
  - `infra/python/wheels/name_${py_platform}` for universal wheels.
    - (For example, `infra/python/wheels/protobuf_py2_py3`)
- The CIPD package should be tagged with a `version:PACKAGE_VERSION` tag.
  - (For example, `version:5.2.2` for a CIPD package containing wheel version
    5.2.2)

Circumstantially, other ways of creating `vpython` CIPD wheel packages include:

- A multi-architecture package, which is a single CIPD package that contains
  Python wheels for multiple platforms (e.g., Windows, Linux, Mac) in the same
  package. `vpython` will defer to `pip`, which will identify and install only
  the wheel matching the current Python platform.
- A dependency-resolved package, wihch is a single CIPD package containig
  multiple different wheels, perhaps a single package and all of its transitive
  dependencies. This can be used for easy deployment of wheels with complex
  or numerous dependencies.

### Deployment

`vpython` is deployed using a variety of mechanisms.

- For users, it is deployed via
  [depot_tools](https://chromium.googlesource.com/chromium/tools/depot_tools/+/master)
  using the `vpython` and `vpython.bat` shims to bootstrap `vpython` from
  `cipd_manifest.txt`.

- For BuildBot bots, it is deployed via
  [cipd_bootstrap_v2.py](https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/slave/cipd_bootstrap_v2.py),
  which also integrates it into `PATH` on bots.

- For LUCI builds, it is deployed and integrated into `PATH` via the build's
  SwarmBucket template.

Bot builds set the `VPYTHON_VIRTUALENV_ROOT` enviornment variable to control
the directory that is used to accumulate VirtualEnv deployments.

## Building

`vpython` is built by the [Infra continuous
builder](https://build.chromium.org/p/chromium.infra/console) set. It is built
by the [infra_continuous](/recipes/recipes/infra_continuous.py) recipe, and is
configured in [vpython.yaml](/build/packages/vpython.yaml).
