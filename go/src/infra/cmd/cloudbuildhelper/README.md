Cloud Build Helper
==================

This tool is a helper for building docker images from infra source code.

As input it takes a YAML file (called "target manifest") with high-level
definition of what to build, how and where, and produces a tagged docker image
as output.

It makes following assumptions:
  * Output image tags are immutable and they identify the inputs: if there's
    already an image with a tag we are about to set, the build is totally
    skipped and the existing image is reused.
  * An output image is a deterministic function of all inputs: if for given
    inputs there's already some built image, we just apply the new tag to it
    without rebuilding it (saves us round trips through Cloud Build).


Modes of operation
------------------

There's a local mode based on `docker` daemon and a remote mode based on
Google Cloud Build infrastructure.

Infra CI builder always use Cloud Build mode. `docker` mode may be useful
for debugging and for urgent builds if Google Cloud Build infrastructure is
down for some reason.


Execution flow
--------------

  1. Read and validate the target manifest YAML.
  2. Execute all local build steps, populating `contextdir` with their results.
  3. **TODO** Draw the rest of the owl.


Command line interface
----------------------

*** note
This is work in progress. Only implemented arguments are documented.
***

```shell
# Evaluates input YAML manifest specified via "-target-manifest" and executes
# all local build steps there. Writes the resulting context dir to a *.tar.gz
# file specified via "-output-tarball". The contents of this tarball is exactly
# what will be sent to the docker daemon or to a Cloud Build worker.
./cloudbuildhelper stage \
    -target-manifest image.yaml \
    -output-tarball some.tar.gz
```


Target manifest YAML
--------------------

*** note
This is work in progress. Only implemented arguments are documented.
***

```yaml
# Path to the image's Dockerfile, relative to this YAML file.
#
# All images referenced in this Dockerfile are resolved into concrete digests
# via an external file. See 'imagepins' field below for more information.
dockerfile: "../../../src/proj/image/Dockerfile"

# Path to the docker context directory to ingest (usually a directory with
# Dockerfile), relative to this YAML file.
#
# All symlinks there are resolved to their targets. Only +w and +x file mode
# bits are preserved. All other file metadata (owners, setuid bits, modification
# times) are ignored.
#
# If not set, the context directory is assumed empty.
contextdir: "../../../src/proj/image"

# Path to the YAML file with pre-resolved mapping from (docker image, tag) pair
# to the corresponding docker image digest.
#
# The path is relative to the manifest YAML file. See "Image pins YAML" section
# below for the expected structure.
#
# This file will be used to rewrite the input Dockerfile to reference all
# images (in "FROM ..." lines) only by their digests. This is useful for
# reproducibility of builds.
#
# Only following forms of "FROM ..." statement are allowed:
#   * FROM <image> [AS <name>] (assumes "latest" tag)
#   * FROM <image>[:<tag>] [AS <name>] (resolves the given tag)
#   * FROM <image>[@<digest>] [AS <name>] (passes the definition through)
#
# In particular ARGs in FROM line (e.g. "FROM base:${CODE_VERSION}") are
# not supported.
#
# If not set, the Dockerfile must use only digests to begin with, i.e.
# all FROM statements should have form "FROM <image>@<digest>".
imagepins: "pins.yaml"

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

*** note
This is work in progress. Only implemented arguments are documented.
***

```yaml
- pins:
  - image: ubuntu
    tag: latest
    digest: sha256:1234567...
  - image: gcr.io/distroless/static
    tag: latest
    digest: sha256:1234567...
  ...
```
