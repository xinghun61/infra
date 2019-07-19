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
# all local build steps there. Materializes the resulting context dir in
# a location specified by "-output-location". If it ends in "*.tar.gz", then
# the result is a tarball, otherwise it is a new directory (attempting to output
# to an existing directory is an error).
#
# The contents of this directory/tarball is exactly what will be sent to the
# docker daemon or to a Cloud Build worker.
./cloudbuildhelper stage \
    -target-manifest image.yaml \
    -output-location some/path
```


Target manifest YAML
--------------------

*** note
This is work in progress. Only implemented arguments are documented.
***

```yaml
# Name of the image to build (excluding the registry or any tags).
#
# Required.
target: some-image-name

# Path to the docker context directory to ingest (usually a directory with
# Dockerfile), relative to this YAML file.
#
# All symlinks there are resolved to their targets. Only +w and +x file mode
# bits are preserved. All other file metadata (owners, setuid bits, modification
# times) are ignored.
#
# If not set, the context directory is assumed empty.
contextdir: "../../../src/proj/image"

# An optional list of local build steps. Each one may add more files to the
# context directory. The actual `contextdir` directory on disk won't be
# modified. Files produced here are stored in a temp directory and the final
# context directory is constructed from full recursive copy of `contextdir` and
# filed produced here. Use `cloudbuildhelper stage` subcommand to see what ends
# up in the context directory.
build:
  # Build and install a go binary given by its path relative to GOPATH.
  # All builds happen with CGO_ENABLED=0 GOOS=linux GOARCH=amd64.
  - go_binary: go.chromium.org/cmd/something
    # Where to put it in the contextdir, defaults to go package name
    dest: something
```
