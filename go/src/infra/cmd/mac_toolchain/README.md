# Ephemeral Xcode Installer for Mac

The purpose of this binary is to provide tools for temporary Xcode
installations, e.g. to build and test Chrome / Chromium on Mac OS X and iOS.

Specifically, it provides tools for creating appropriate Xcode CIPD packages and
then installing them on demand on bots and developer machines.

## Installation

### From `depot_tools`

The `mac_toolchain` tool is available in
[`depot_tools`](https://chromium.googlesource.com/chromium/tools/depot_tools.git)
as a shim which automatically installs the binary on Mac OS X.

### Prebuilt CIPD Package

For `depot_tool`-independent installation (e.g. on a bot, in a recipe), the
preferred method of installing this tool is through CIPD, e.g.:

    $ echo 'infra/tools/mac_toolchain/${platform}  latest' | cipd ensure -ensure-file - -root .

will install the `mac_toolchain` binary in the current directory (as specified
by the `-root` argument).

Note, that the CIPD package currently exists only for Mac OS, and not for any
other platform, since Xcode installation only makes sense on a Mac.

You can also create shim scripts to install the actual binaries automatically,
and optionally pin the `mac_toolchain` package to a specific revision. Pinning
to `latest` will always install the latest available revision. For inspiration,
see
[`cipd_manifest.txt`](https://chromium.googlesource.com/chromium/tools/depot_tools.git/+/master/cipd_manifest.txt)
in `depot_tools`, and the corresponding shims,
e.g. [`vpython`](https://chromium.googlesource.com/chromium/tools/depot_tools.git/+/master/vpython).

The prebuilt CIPD package is configured and built automatically for (almost)
every committed revision of `infra.git`. It's configuration file is
[`mac_toolchain.yaml`](https://chromium.googlesource.com/infra/infra/+/master/build/packages/mac_toolchain.yaml).

### Compile from source

Since this is a standard Go package, you can also install it by running `go
install` in this folder. See the [`infra/go/README.md`](../../../../README.md) file
for the Go setup.

## Installing an Xcode package

    mac_toolchain install -xcode-version XXXX -output-dir /path/to/root

This will install the requested version of `Xcode.app` in the `/path/to/root`
folder.  Run `mac_toolchain help install` for more information.

_Note:_ to access the Xcode packages, you may need to run:

    cipd auth-login

or pass the appropriate `-service-account-json` argument to `cipd ensure`.

## Creating a new Xcode package

Download the Xcode zip file from your Apple's Developer account, unpack it, and
point the script at the resulting `Xcode.app`.

    mac_toolchain upload -xcode-path /path/to/Xcode.app

This will split up the `Xcode.app` container into several CIPD packages and will
upload and tag them properly. Run `mac_toolchain help upload` for more options.

The upload command is meant to be run manually, and it will upload many GB of
data. Be patient.

### Debugging packages

To debug the packages locally, run:

    mac_toolchain package -output-dir path/to/dir -xcode-path /path/to/Xcode.app

This will drop `mac.cipd` and `ios.cipd` files in `path/to/out` directory and
will not try to upload the packages to CIPD server.

You can then install Xcode from these local packages with:

    cipd pkg-deploy -root path/to/Xcode.app path/to/out/mac.cipd
    cipd pkg-deploy -root path/to/Xcode.app path/to/out/ios.cipd
