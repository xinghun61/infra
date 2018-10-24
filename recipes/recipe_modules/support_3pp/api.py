# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Allows uniform cross-compiliation, version tracking and archival for
third-party software packages (libs+tools) for distribution via CIPD.

The purpose of the Third Party Packages (3pp) recipe/module is to generate CIPD
packages of statically-compiled software for distribution in our continuous
integration fleets, as well as software distributed to our develepers (e.g.
via depot_tools).

Target os and architecture uses the CIPD "${os}-${arch}" (a.k.a. "${platform}")
nomenclature, which is currently defined in terms of Go's GOOS and GOARCH
runtime variables (with the unfortunate exception that CIPD uses 'mac' instead
of 'darwin'). This is somewhat arbitrary, but has worked well so far for us.

#### Package Definitions

The 3pp module loads package definitions from a folder containing subfolders.
Each subfolder defines a single software package to fetch, build and upload.
For example, you might have a folder in your repo like this:

    my_repo.git/
      3pp/  # "root folder"
        .vpython             # common vpython file for all package scripts
        zlib/                # zlib "package folder"
          3pp.pb             # REQUIRED: the Spec.proto definition for zlib
          install.sh         # a script to build zlib from source
          extra_resource_file
        other_package/
          3pp.pb             # REQUIRED
          fetch.py           # a script to fetch `other_package` in a custom way
          install.sh
          install-win.sh     # windows-specific build script
        ...

This defines two packages (`zlib`, and `other_package`). The 3pp.pb files have
references to the fetch/build scripts, and describe what dependencies the
packages have (if any).

NOTE: Only one layer of package folders is supported currently.

Packages are named by the folder that contains their definition file (3pp.pb)
and build scripts. It's preferable to have package named after software that it
contains. However, sometimes you want multiple major versions of the software to
exist side-by-side (e.g. pcre and pcre2, python and python3, etc.). In this
case, have two separate package definition folders.

Each package folder contains a package spec (3pp.pb), as well as scripts,
patches and/or utility tools to build the software from source.

The spec is a Text Proto document specified by the [spec.proto] schema.

The spec is broken up into two main sections, "create" and "upload". The
create section allows you to specify how the package software gets created, and
allows specifying differences in how it's fetched/built/tested on a per-target
basis, and the upload section has some details on how the final result gets
uploaded to CIPD.

[spec.proto]: /recipes/recipe_modules/support_3pp/spec.proto

#### Creation Stages

The 3pp.pb spec begins with a series of `create` messages, each with details on
on how to fetch+build+test the package.  Each create message contains
a "platform_re" field which works as a regex on the ${platform} value. All
matching patterns apply in order, and non-matching patterns are skipped. Each
create message is applied with a dict.update for each member message (i.e.
['source'].update, ['build'].update, etc.) to build a singular create message
for the current target platform. For list values (e.g. 'tool', 'dep' in the
Build message), you can clear them by providing a new empty value
(e.g. `tool: ""`)

Once all the create messages are merged (see schema for all keys that can be
present), the actual creation takes place.

Note that "source" is REQUIRED in the final merged instruction set. All other
messages are optional and have defaults as documented in [spec.proto].

The creation process is broken up into 4 different stages:

  * Source
  * Build
  * Package
  * Verify

##### Envvars

All scripts described below are invoked with the following environment variables
set:
  * $_3PP_PACKAGE_NAME - the name of the package currently building
  * $_3PP_PATCH_VERSION - the `patch_version` set for the version we're building
    (if any patch version was set).
  * $_3PP_PLATFORM - the platform we're targeting
  * $_3PP_TOOL_PLATFORM - the platform that we're building on (will be different
    than _3PP_PLATFORM if we're cross-compiling)
  * $_3PP_VERSION - the version we're building, e.g. 1.2.3
  * $GOOS - The golang OS name we're targeting
  * $GOARCH - The golang architecture we're targeting
  * $MACOSX_DEPLOYMENT_TARGET - On OS X, set to 10.10, for your
    semi-up-to-date OS X building needs. This needs to be consistently
    set for all packages or it will cause linker warnings/errors when
    linking in static libs that were targeting a newer version (e.g.
    if it was left unset). Binaries built with this set to 10.10 will not
    run on 10.9 or older systems.

Additionally, on cross-compile environments, the $CROSS_TRIPLE environment
variable is set to a GCC cross compile target triplet of cpu-vendor-os.

##### Source

The source is used to fetch the raw sources for assembling the package. In some
cases the sources may actually be binary artifacts (e.g. prebuilt windows
installers).

The source is unpacked to a checkout directory, possibly in some specified
subdirectory. Sources can either produce the actual source files, or they can
produce a single archive file (e.g. zip or tarball), which can be unpacked with
the 'unpack_archive' option. In addition, patches can be applied to the source
with the 'patch_dir' option (the patches should be in `git format-patch` format,
and will be applied with `git apply`).

  * `git` - This checks out a semver tag in the repo.
  * `cipd` - This fetches data from a CIPD package.
  * `script` - Used for "weird" packages which are distributed via e.g.
    an HTML download page or an API. The script must be able to return the
    'latest' version of its source, as well as to actually fetch a specified
    version. Python fetch scripts will be executed with `vpython`, and so
    may have a .vpython file (or similar) in the usual manner to pull in
    dependencies like `requests`.

Additionally the Source message contains a `patch_version` field to allow symver
disambiguation of the built packages when they contain patches or other
alterations which need to be versioned. This string will be joined with a '.' to
the source version being built when uploading the result to CIPD.

##### Build

The build message allows you to specify `deps`, and `tools`, as well as a script
`install` which contains your logic to transform the source into the result
package.

Deps are libraries built for the target `${platform}` and are typically used for
linking your package.

Tools are binaries built for the host; they're things like `automake` or `sed`
that are used during the configure/make phase of your build, but aren't linked
into the built product. These tools will be available on $PATH (both '$tools'
and '$tools/bin' are added to $PATH, because many packages are set up with their
binaries at the base of the package, and some are set up with them in a /bin
folder)

Installation occurs by invoking the script indicated by the 'install' field
(with the appropriate interpreter, depending on the file extension) like:

    <interpreter> "$install[*]" "$PREFIX" "$DEPS_PREFIX"

Where:

  * The current working directory is the base of the source checkout w/o subdir.
  * `$install[*]` are all of the tokens in the 'install' field.
  * `$PREFIX` is the directory which the script should install everything to;
    this directory will be archived into CIPD verbatim.
  * `$DEPS_PREFIX` is the path to a prefix directory containing the union of all
    of your packages' transitive deps. For example, all of the headers of your
    deps are located at `$DEPS_PREFIX/include`.
  * All `tools` are in $PATH

If the 'install' script is omitted, it is assumed to be 'install.sh'.

If the ENTIRE build message is omitted, no build takes place. Instead the
result of the 'source' stage will be packaged.

During the execution of the build phase, the entire 'root folder' is copied into
the source checkout in the .3pp directory, and the script will be invoked as
`/path/to/checkout/.3pp/$package_name/$script_name`. Because the entire root
folder is copied, you can have shared resources (like `.vpython` files or helper
scripts) which are common to all package definitions and located relative to the
install script.

##### Package

Once the build stage is complete, all files in the $PREFIX folder passed to the
install script will be zipped into a CIPD package.

It is strongly recommended that if your package is a library or tool with many
files that it be packaged in the standard POSIXey PREFIX format (e.g. bin, lib,
include, etc.). If your package is a collection of one or more standalone
binaries, it's permissible to just have the binaries in the root of the output
$PREFIX.

If the build stage is skipped (i.e. the build message is omitted) then the
output of the source stage will be packaged instead (this is mostly useful when
using a 'script' source).

##### Verify

After the package is built it can be optionally tested. The recipe will run your
test script in an empty directory with the path to the
packaged-but-not-yet-uploaded cipd package file and it can do whatever testing
it needs to it (exiting non-zero if something is wrong). You can use the `cipd
pkg-deploy` command to deploy it (or whatever cipd commands you like, though
I wouldn't recommend uploading it to CIPD, as the 3pp recipe will do that after
the test exits 0).

Additionally, vpython for the tool platform will be guaranteed to be in $PATH.

##### Upload

Once the test comes back positive, the CIPD package will be uploaded to the CIPD
server and registered with the prefix indicated in the upload message. The full
CIPD package name is constructed as:

    <prefix>/<pkg_name>/${platform}

So for example with the prefix `infra`, the `bzip2` package on linux-amd64 would
be uploaded to `infra/bzip2/linux-amd64` and tagged with the version that was
built (e.g. `version:1.2.3.patch_version1`).

You can also mark the upload as a `universal` package, which will:
  * Omit the `${platform}` suffix from the upload name
  * Set the target platform for the package to `linux-amd64`, regardless of
    what platform you build the recipe on. This was chosen arbitrarially to
    ensure that "universal" packages build consistently. You can override this
    behavior (and bypass the normal docker environment entirely) by setting
    the no_docker_env flag to true in your Create.Build message.

#### Versions

Every package will try to build the latest identifiable semver of its source, or
will attempt to build the semver requested as an input property to the
`3pp` recipe. This semver is also used to tag the uploaded artifacts in CIPD.

Because some of the packages here are used as dependencies for others (e.g.
curl and zlib are dependencies of git, and zlib is a dependency of curl), each
package used as a dependency for others should specify its version explicitly
(currently this is only possible to do with the 'cipd' source type). So e.g.
zlib and curl specify their source versions, but git and python float at 'head',
always building the latest tagged version fetched from git.

When building a floating package (e.g. python, git) you may explicitly
state the symver that you wish to build as part of the recipe invocation.

The symver of a package (either specified in the package definition, in the
recipe properties or discovered while fetching its source code (e.g. latest git
tag)) is also used to tag the package when it's uploaded to CIPD (plus the
patch_version in the source message).

#### Cross Compilation

Third party packages are currently compiled on linux using the
'infra.tools.dockerbuild' tool from the infra.git repo. This uses a slightly
modified version of the [dockcross] Docker cross-compile environment. Windows
and OS X targets are built using the 'osx_sdk' and 'windows_sdk' recipe modules,
each of which provides a hermetic (native) build toolchain for those platforms.

For linux, we can support all the architectures implied by dockerbuild,
including:
  * linux-arm64
  * linux-armv6l
  * linux-mips32
  * linux-mips64
  * linux-386
  * linux-amd64

[dockcross]: https://github.com/dockcross/dockcross

#### Dry runs / experiments

If the recipe is run with `force_build` it will always build all packages
indicated (and their dependencies), and will not upload any of them to the
central server.

The recipe must always be run with a package_prefix (by assigning to the
.package_prefix property on the Support3ppApi). If the recipe is run in
experimental mode, 'experimental/' will be prepended to this. Additionally, you
may specify `experimental: true` in the Create message for a package, which will
have the same effect when running the recipe in production (to allow adding new
packages or package/platform combintations experimentally).

#### Examples

As an example of the package definition layout in action, take a look at the
[3pp](/3pp) folder in this infra.git repo.

#### Caches

This module uses the following named caches:
  * `3pp_cipd` - Caches all downloaded and uploaded CIPD packages. Currently
    tag lookups are performed every time against the CIPD server, but this will
    hold the actual package files.
  * `osx_sdk` - Cache for `depot_tools/osx_sdk`. Only on Mac.
  * `windows_sdk` - Cache for `depot_tools/windows_sdk`. Only on Windows.
"""

import re

from google.protobuf import json_format as jsonpb
from google.protobuf import text_format as textpb

from recipe_engine import recipe_api

from . import spec_pb2
from .resolved_spec import ResolvedSpec, parse_name_version, tool_platform
from .resolved_spec import platform_for_host
from .exceptions import BadParse, DuplicatePackage, UnsupportedPackagePlatform

from . import create
from . import cipd_spec


def _flatten_spec_pb_for_platform(orig_spec, platform):
  """Transforms a copy of `orig_spec` so that it contains exactly one 'create'
  message.

  Every `create` message in the original spec will be removed if its
  `platform_re` field doesn't match `platform`. The matching messages will be
  applied, in their original order, to a single `create` message by doing
  a `dict.update` operation for each submessage.

  Args:
    * orig_spec (spec_pb2.Spec) - The message to flatten.
    * platform (str) - The CIPD platform value we're targeting (e.g.
    'linux-amd64')

  Returns a new `spec_pb2.Spec` with exactly one `create` message, or None if
  the original spec is not supported on the given platform.
  """
  spec = spec_pb2.Spec()
  spec.CopyFrom(orig_spec)

  resolved_create = {}

  applied_any = False
  for create_msg in spec.create:
    plat_re = "^(%s)$" % (create_msg.platform_re or '.*')
    if not re.match(plat_re, platform):
      continue

    if create_msg.unsupported:
      return None

    # We're going to apply this message to our resolved_create.
    applied_any = True

    # To get the effect of the documented dict.update behavior, round trip
    # through JSONPB. It's a bit dirty, but it works.
    dictified = jsonpb.MessageToDict(
      create_msg, preserving_proto_field_name=True)
    for k, v in dictified.iteritems():
      if isinstance(v, dict):
        resolved_create.setdefault(k, {}).update(v)
        to_clear = set()
        for sub_k, sub_v in resolved_create[k].iteritems():
          if isinstance(sub_v, list) and not any(val for val in sub_v):
            to_clear.add(sub_k)
        for sub_k in to_clear:
          resolved_create[k].pop(sub_k)
      else:
        resolved_create[k] = v

  if not applied_any:
    return None

  # To make this create rule self-consistent instead of just having the last
  # platform_re to be applied.
  resolved_create.pop('platform_re', None)

  # Clear list of create messages, and parse the resolved one into the sole
  # member of the list.
  del spec.create[:]
  jsonpb.ParseDict(resolved_create, spec.create.add())

  return spec


class Support3ppApi(recipe_api.RecipeApi):
  def __init__(self, **kwargs):
    super(Support3ppApi, self).__init__(**kwargs)
    # map of name -> (base_path, spec_pb2.Spec)
    self._loaded_specs = {}
    # map of (name, platform) -> ResolvedSpec
    self._resolved_packages = {}
    # map of (name, version, platform) -> CIPDSpec
    self._built_packages = {}
    # Used by CIPDSpec; must be defined here so that it doesn't persist
    # accidentally between recipe tests.
    self._cipd_spec_pool = None

    # (required) The package prefix to use for built packages (not for package
    # sources).
    #
    # NOTE: If `runtime.is_experimental`, then this is prepended with
    # 'experimental/'.
    self._package_prefix = ''

  def initialize(self):
    self._cipd_spec_pool = cipd_spec.CIPDSpecPool(self.m)

  def package_prefix(self, experimental=False):
    """Returns the CIPD package name prefix (str), if any is set.

    This will prepend 'experimental/' to the currently set prefix if:
      * The recipe is running in experimental mode; OR
      * You pass experimental=True
    """
    assert self._package_prefix, 'A non-empty package prefix is required.'
    experimental = experimental or self.m.runtime.is_experimental
    return (
      ('experimental/' if experimental else '')
      + self._package_prefix + '/'
    )

  def set_package_prefix(self, prefix):
    """Set the CIPD package name prefix (str).

    All CIPDSpecs for built packages (not sources) will have this string
    prepended to them.
    """
    assert isinstance(prefix, str)
    self._package_prefix = prefix.strip('/')

  BadParse = BadParse
  DuplicatePackage = DuplicatePackage
  UnsupportedPackagePlatform = UnsupportedPackagePlatform

  def _resolve_for(self, pkgname, platform):
    """Resolves the build instructions for a package for the given platform.

    This will recursively resolve any 'deps' or 'tools' that the package needs.
    The resolution process is entirely 'offline' and doesn't run any steps, just
    transforms the loaded 3pp.pb specs into usable ResolvedSpec objects.

    The results of this method are cached.

    Args:
      * pkgname (str) - The name of the package to resolve. Must be a package
      registered via `load_packages_from_path`.
      * platform (str) - A CIPD `${platform}` value to resolve this package for.
      Always in the form of `GOOS-GOARCH`, e.g. `windows-amd64`.

    Returns a ResolvedSpec.

    Raises `UnsupportedPackagePlatform` if the package cannot be built for this
    platform.
    """
    key = (pkgname, platform)
    ret = self._resolved_packages.get(key)
    if ret:
      return ret

    base_path, orig_spec = self._loaded_specs[pkgname]

    spec = _flatten_spec_pb_for_platform(orig_spec, platform)
    if not spec:
      raise UnsupportedPackagePlatform(
        "%s not supported for %s" % (pkgname, platform))

    create_pb = spec.create[0]

    # Universal specs using docker always target linux-amd64, for consistency
    # when running the recipe on different platforms. We change the target
    # platform here from the native platform so that dep and tool resolutions
    # occur for linux-amd64.
    if spec.upload.universal and not create_pb.build.no_docker_env:
      platform = 'linux-amd64'

    if create_pb.source.WhichOneof('method') == 'cipd':
      if not create_pb.source.cipd.original_download_url:  # pragma: no cover
        raise Exception(
          'CIPD Source for `%s/%s` must have `original_download_url`.' % (
          pkgname, platform))

    source_pb = create_pb.source
    assert source_pb.patch_version == source_pb.patch_version.strip('.'), (
      'source.patch_version has starting/trailing dots')

    assert spec.upload.pkg_prefix == spec.upload.pkg_prefix.strip('/'), (
      'upload.pkg_prefix has starting/trailing slashes')

    # Recursively resolve all deps
    deps = []
    for dep in create_pb.build.dep:
      deps.append(self._resolve_for(dep, platform))

    # Recursively resolve all unpinned tools. Pinned tools are always
    # installed from CIPD.
    unpinned_tools = []
    for tool in create_pb.build.tool:
      tool_name, tool_version = parse_name_version(tool)
      if tool_version == 'latest':
        unpinned_tools.append(self._resolve_for(
          tool_name, tool_platform(self.m, platform, spec)))

    ret = ResolvedSpec(
      self.m, self._cipd_spec_pool, self.package_prefix(create_pb.experimental),
      pkgname, platform, base_path, spec, deps, unpinned_tools)
    self._resolved_packages[key] = ret
    return ret

  def _build_resolved_spec(self, spec, version, force_build):
    """Builds the resolved spec. All dependencies for this spec must already be
    built.

    Args:
      * spec (ResolvedSpec) - The spec to build.
      * version (str) - The symver of the package that we want to build.
      * force_build (bool) - If True, ignore remote server checks.

    Returns CIPDSpec for the built package.
    """
    return create.build_resolved_spec(
      self.m, self._resolve_for, self._built_packages, force_build,
      spec, version)

  def load_packages_from_path(self, path):
    """Loads all package definitions from the given path.

    This will parse and intern all the 3pp.pb package definition files so that
    packages can be identified by their name. For example, if you pass:

      path/
        pkgname/
          3pp.pb
          install.sh

    This would parse path/pkgname/3pp.pb and register the "pkgname" package.

    Args:
      * path (Path) - A path to a directory full of package definitions. Each
        package definition is a directory containing at least a 3pp.pb file,
        whose behavior is defined by 3pp.proto.

    Returns a set(str) containing the names of the packages which were loaded.

    Raises a DuplicatePackage exception if this function encounters a package
    whose name is already registered. This could occur if you call
    load_packages_from_path multiple times, and one of the later calls tries to
    load a package which was registered under one of the earlier calls.
    """
    known_package_specs = self.m.file.glob_paths(
      'find package specs', path,
      self.m.path.join('*', '3pp.pb'))

    discovered = set()

    with self.m.step.nest('load package specs'):
      for spec in known_package_specs:
        pkg = spec.pieces[-2]  # ../../<name>/3pp.pb
        if pkg in self._loaded_specs:
          raise DuplicatePackage(pkg)

        data = self.m.file.read_text('read %r' % pkg, spec)
        if not data:
          self.m.step.active_result.presentation.status = self.m.step.FAILURE
          raise self.m.step.StepFailure('Bad spec PB for %r' % pkg)

        try:
          self._loaded_specs[pkg] = (path, textpb.Merge(data, spec_pb2.Spec()))
        except Exception as ex:
          raise BadParse('While adding %r: %r' % (pkg, str(ex)))
        discovered.add(pkg)

    return discovered

  def ensure_uploaded(self, packages=(), platform='', force_build=False):
    """Executes entire {fetch,build,package,verify,upload} pipeline for all the
    packages listed, targeting the given platform.

    Args:
      * packages (seq[str]) - A sequence of packages to ensure are
        uploaded. Packages must be listed as either 'pkgname' or
        'pkgname@version'. If empty, builds all loaded packages.
      * platform (str) - If specified, the CIPD ${platform} to build for.
        If unspecified, this will be the appropriate CIPD ${platform} for the
        current host machine.

    Returns (list[(cipd_pkg, cipd_version)], set[str]) of built CIPD packages
    and their tagged versions, as well as a list of unsupported packages.
    """
    unsupported = set()

    explicit_build_plan = []
    packages = packages or self._loaded_specs.keys()
    platform = platform or platform_for_host(self.m)
    for pkg in packages:
      name, version = parse_name_version(pkg)
      try:
        resolved = self._resolve_for(unicode(name), platform)
      except UnsupportedPackagePlatform:
        unsupported.add(pkg)
        continue
      explicit_build_plan.append((resolved, unicode(version)))

    expanded_build_plan = set()
    for pkg, version in explicit_build_plan:
      expanded_build_plan.add((pkg, version))
      # Anything pulled in either via deps or tools dependencies should be
      # explicitly built at 'latest'.
      for subpkg in pkg.all_possible_deps_and_tools:
        expanded_build_plan.add((subpkg, 'latest'))

    ret = []
    for spec, version in sorted(expanded_build_plan):
      ret.append(self._build_resolved_spec(spec, version, force_build))
    return ret, unsupported
