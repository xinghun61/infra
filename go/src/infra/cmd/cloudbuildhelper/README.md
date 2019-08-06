Cloud Build Helper
==================

This tool is a helper for building docker images from Infra source code.

As input it takes a YAML file (called "target manifest") with high-level
definition of what to build, how, from what source and where, and produces a
tagged docker image as output.

Images can be of two kinds:
  * **Deterministic** image is a pure function of inputs: if we rebuild such
    image from original sources after e.g. 5 months we should get *exact same*
    output (modulus metadata, like timestamps).
  * **Non-deterministic** image depends on the state of the world at the time it
    is built. It depends on things like external unpinned packages (e.g.
    fetched via `apt-get`), files fetched from the Internet, git repositories
    fetched from `master` ref, etc. Rebuilding such image produces different
    output each time.

This distinction is important when we attempt to build images on *every commit*.
If we treat all images as non-deterministic (which is considered the norm in
the Docker world), and they are stored in a busy repo, we'll be getting *a ton*
of images (one per every commit, no matter how insignificant), with no way track
when images *actually semantically change*. And not knowing when images change,
we don't know when to kick off an automated deployment to a staging cluster.

When we *do* know that an image is deterministic function of its inputs, and we
know what they are, we can track when *these specific inputs* (and only them)
change, to recognize when we need to rebuild the image (and kick off a new
deployment). Unrelated commits just fly by without any effect on the image.

The target manifest YAML (described in detail below) is precisely the definition
of what goes into an image and whether the image is deterministic.

Note that when including complied code into images (like go binaries), we rely
on build reproducibility to detect changes: when rebuilding a binary, if sources
do not change, the output should also not change, i.e. by byte-to-byte
reproducible.


Command line interface
----------------------


### cloudbuildhelper build

```
$ cloudbuildhelper help build
Builds a docker image using Google Cloud Build.

usage:  cloudbuildhelper build <target-manifest-path> [...]
  -build-id string
      Identifier of the CI build that calls this tool (used in various metadata).
  -canonical-tag string
      Tag to push the image to if we built a new image.
  -force
      Rebuild and reupload the image, ignoring existing artifacts.
  -infra string
      What section to pick from 'infra' field in the YAML. (default "dev")
  -json-output string
      Where to write JSON file with the outcome ("-" for stdout).
  -label value
      Labels to attach to the docker image, in k=v form.
  -log-level value
      The logging level. Valid options are: debug, info, warning, error. (default info)
  -service-account-json string
      Path to JSON file with service account credentials to use.
  -tag value
      Additional tag(s) to unconditionally push the image to (e.g. "latest").
```

Either reuses an existing image or builds a new one (see below for details). If
builds a new one, tags it with `-canonical-tag`.

The canonical tag should identify the exact version of inputs (e.g. it usually
includes git revision or other unique version identifier). It is used as
immutable alias of sources and the resulting image.

If `-canonical-tag` is set to a literal constant `:inputs-hash`, it is
calculated from SHA256 of the tarball with the context directory. This is useful
to skip rebuilding the image if inputs do not change, without imposing any
specific schema of canonical tags.

The `build` command works in multiple steps:
  1. Searches for an existing image with the given `-canonical-tag`. If it
     exists, assumes the build has already been done and skips the rest of the
     steps. This applies to both deterministic and non-deterministic targets.
  2. Prepares a context directory by evaluating the target manifest YAML,
     resolving tags in Dockerfile and executing local build steps. The result
     of this process is a `*.tar.gz` tarball that will be sent to Docker daemon.
     See "stage" subcommand for more details.
  3. Calculates SHA256 of the tarball and uses it to construct a Google Storage
     path. If the tarball at that path already exists in Google Storage and
     the target is marked as deterministic in the manifest YAML, examines
     tarball's metadata to find a reference to an image already built from it.
     If there's such image, uses it (and its canonical tag, whatever it was
     when the image was built) as the result.
  4. If the target is not marked as deterministic, or there's no existing images
     that can be reused, triggers "docker build" via Cloud Build and feeds it
     the uploaded tarball as the context. The result of this process is a new
     docker image.
  5. Pushes this image to the registry under `-canonical-tag` tag.
  6. Updates metadata of the tarball in Google Storage with the reference to the
     produced image (its SHA256 digest and its canonical tag), so that future
     builds can discover and reuse it, if necessary.

In the very end, regardless of whether a new image was built or some existing
one was reused, pushes the image to the registry under given `-tag` (or tags),
if any. The is primary used to update "latest" tag.


### cloudbuildhelper localbuild

```
$ cloudbuildhelper help localbuild
Builds a docker image using local docker daemon.

usage:  cloudbuildhelper localbuild <target-manifest-path> [...]
  -label value
      Labels to attach to the docker image, in k=v form.
  -log-level value
      The logging level. Valid options are: debug, info, warning, error. (default info)
```

Roughly does `docker build --no-cache --squash --tag <name> <context>`, where
`<name>` and `<context>` come from the manifest.

Doesn't upload the image anywhere.


### cloudbuildhelper stage

```
$ cloudbuildhelper stage --help
Prepares the tarball with the context directory.

usage:  cloudbuildhelper stage <target-manifest-path> -output-tarball <path> [...]
  -log-level value
      The logging level. Valid options are: debug, info, warning, error. (default info)
  -output-tarball string
      Where to write the tarball with the context dir.
```

Evaluates input YAML manifest specified via the positional argument, executes
all local build steps there, and rewrites Dockerfile to use pinned digests
instead of tags. Writes the resulting context dir to a `*.tar.gz` file specified
via `-output-tarball`. The contents of this tarball is exactly what will be sent
to the docker daemon or to a Cloud Build worker.


### cloudbuildhelper pins-add

```
$ cloudbuildhelper help pins-add
Adds a pinned docker image to the image pins YAML file.

usage:  cloudbuildhelper pins-add <pins-yaml-path> <image>[:<tag>]
  -log-level value
      The logging level. Valid options are: debug, info, warning, error. (default info)
  -service-account-json string
      Path to JSON file with service account credentials to use.
```

Resolves `<image>[:<tag>]` to a docker image digest and adds an entry to the
image pins YAML file. If there's such entry already, overwrites it.

Rewrites the YAML file destroying any custom formatting or comments there.
If you want to comment an entry, manually add `comment` field.

The file must exist already. If you are starting completely from scratch, create
an empty file first (e.g. using `touch`).


### cloudbuildhelper pins-update

```
$ cloudbuildhelper help pins-update
Updates digests in the image pins YAML file.

usage:  cloudbuildhelper pins-update <pins-yaml-path>
  -log-level value
      The logging level. Valid options are: debug, info, warning, error. (default info)
  -service-account-json string
      Path to JSON file with service account credentials to use.
```

Resolves tags in all entries not marked as frozen and writes new SHA256 digests
back into the file.

To freeze an entry (and thus exclude it from the update process) add `freeze`
field specifying the reason why it is frozen.

Rewrites the YAML file destroying any custom formatting or comments there.
If you want to comment an entry, manually add `comment` field.


Cloud Build vs local mode
-------------------------

`cloudbuildhelper` uses Google Cloud Build service to actually "compile" images
from docker context tarballs. That way there's no need to have Docker installed
locally, which simplifies usage of the tool on CI builders.

This is the primary mode of operation and all bells and whistles described above
work only in this mode.

If for whatever reason Cloud Build infrastructure is inaccessible, there's a
local mode that uses local docker daemon. It builds the image locally without
touching any external services. The result is stored in the local docker cache.
If you want to release an image built this way, you'll need to tag and push it
yourself using standard docker tooling:

```shell
# Do the local build. Notice "sha256:..." digest of the final image in the log.
# Or just use '<name-in-the-manifest>:latest' as a reference to the produced
# image.
cloudbuildhelper localbuild <target-manifest.yaml>

# Prepare the image for the pushed by tagging it locally.
docker tag <name-in-the-manifest>:latest gcr.io/<registry>/<name>:<tag>

# Actually upload it to the registry.
docker push gcr.io/<registry>/<name>:<tag>
```

In this mode there's no distinction between deterministic and non-deterministic
images. Google Storage is not used. Cloud Build is not used. It's just a thin
wrapper around preparing the context directory and running "docker build".


Target manifest YAML
--------------------

```yaml
# Image name (without registry or any tags).
name: some-image

# Path (relative to this YAML file) to a manifest used as a base.
#
# Optional.
#
# Such base manifests usually contain definitions shared by many files, such
# as "imagepins" and "infra".
#
# Dicts are merged (recursively), lists are joined (base entries first).
extends: ../base.yaml

# Path to the image's Dockerfile, relative to this YAML file.
#
# All images referenced in this Dockerfile are resolved into concrete digests
# via an external file. See 'imagepins' field for more information.
dockerfile: "../../../src/proj/image/Dockerfile"

# Path to the directory to use as a basis for the build. The path is relative
# to this YAML file.
#
# All files there end up available to the remote builder (e.g. a docker
# daemon will see this directory as a context directory when building
# the image).
#
# All symlinks there are resolved to their targets. Only +w and +x file mode
# bits are preserved (all files have 0444 mode by default, +w adds additional
# 0200 bit and +x adds additional 0111 bis). All other file metadata (owners,
# setuid bits, modification times) are ignored.
#
# The default value depends on whether Dockerfile is set. If it is, then
# ContextDir defaults to the directory with Dockerfile. Otherwise the context
# directory is assumed to be empty.
contextdir: "../../../src/proj/image"

# Path to the YAML file with pre-resolved mapping from (docker image, tag) pair
# to the corresponding docker image digest.
#
# The path is relative to the manifest YAML file. See below for the expected
# structure of this file.
#
# This file will be used to rewrite the input Dockerfile to reference all
# images (in "FROM ..." lines) only by their digests. This is useful for
# reproducibility of builds.
#
# Only following forms of "FROM ..." statement are allowed:
#  * FROM <image> [AS <name>] (assumes "latest" tag)
#  * FROM <image>[:<tag>] [AS <name>] (resolves the given tag)
#  * FROM <image>[@<digest>] [AS <name>] (passes the definition through)
#
# In particular ARGs in FROM line (e.g. "FROM base:${CODE_VERSION}") are
# not supported.
#
# If not set, the Dockerfile must use only digests to begin with, i.e.
# all FROM statements should have form "FROM <image>@<digest>".
#
# Ignored if Dockerfile field is not set.
imagepins: "pins.yaml"

# Set to true if Dockerfile (with all "FROM" lines resolved) can be understood
# as a pure function of inputs in ContextDir, i.e. it does not depend on the
# state of the world.
#
# Examples of things that make Dockerfile NOT deterministic:
#   * Using "apt-get" or any other remote calls to non-pinned resources.
#   * Cloning repositories from "master" ref (or similar).
#   * Fetching external resources using curl or wget.
#
# When building an image marked as deterministic, the builder will calculate
# a hash of all inputs (including resolve Dockerfile itself) and check
# whether there's already an image built from them. If there is, the build
# will be skipped completely and the existing image reused.
#
# Images marked as non-deterministic are always rebuilt and reuploaded, even
# if nothing in ContextDir has changed.
deterministic: true

# Configuration of the build infrastructure to use: Google Storage bucket,
# Cloud Build project, etc.
#
# Keys are names of presets (like "dev", "prod"). What preset is used is
# controlled via "-infra" command line flag (defaults to "dev").
infra:
  dev:
    # Google Storage location to store *.tar.gz tarballs produced after
    # executing all local build steps.
    #
    # Expected format is "gs://<bucket>/<prefix>". Tarballs will be stored as
    # "gs://<bucket>/<prefix>/<name>/<sha256>.tar.gz", where <name> comes from
    # the manifest and <sha256> is a hex sha256 digest of the tarball.
    #
    # The bucket should exist already. Its contents is trusted, i.e. if there's
    # an object with desired <sha256>.tar.gz there already, it won't be
    # replaced.
    #
    # Required when using Cloud Build.
    storage: gs://some-dev-project/path

    # Cloud Registry to push images to.
    #
    # If empty, images will be built and then just discarded (will not be pushed
    # anywhere). Useful to verify Dockerfile is working without accumulating
    # cruft.
    registry: gcr.io/some-dev-project

    # Configuration of Cloud Build infrastructure.
    cloudbuild:
      project: some-dev-project  # name of Cloud Project to use for builds
      docker: 18.09.6            # version of "docker" tool to use for builds

# An optional list of local build steps. Each step may add more files to the
# context directory. The actual `contextdir` directory on disk won't be
# modified. Files produced here are stored in a temp directory and the final
# context directory is constructed from the full recursive copy of `contextdir`
# and files produced here. Use `cloudbuildhelper stage` subcommand to see what
# ends up in the context directory after all build steps are finished.
build:
  # Copy a file or directory into the context dir.
  - copy: ../../../src/stuff
    dest: stuff

  # Build and install a go binary given by its path relative to GOPATH.
  # All builds happen with CGO_ENABLED=0 GOOS=linux GOARCH=amd64.
  - go_binary: go.chromium.org/cmd/something
    # Where to put it in the contextdir, defaults to go package name
    dest: something
```


Image pins YAML
---------------

Contains mapping `(image, tag) => digest` used to resolve tags in `FROM ...`
lines in Dockerfiles into concreted digests.

```yaml
# Managed by cloudbuildhelper.
#
# All comments or unrecognized fields will be overwritten. To comment an entry
# use "comment" field.
#
# To update digests of all entries:
#   $ cloudbuildhelper pins-update <path-to-this-file>
#
# To add an entry (or update an existing one):
#   $ cloudbuildhelper pins-add <path-to-this-file> <image>[:<tag>]
#
# To remove an entry just delete it from the file.
#
# To prevent an entry from being updated by pins-update, add "freeze" field with
# an explanation why it is frozen.

- pins:
  - image: docker.io/library/ubuntu
    tag: latest
    digest: sha256:1234567...
    comment: Arbitrary string, will be retained by 'pins-add' and 'pins-update'.
  - image: gcr.io/distroless/static
    tag: latest
    digest: sha256:1234567...
    freeze: If this field is present, 'pins-update' won't update this pin.
  ...
```
