Docker images on Infra CI
=========================

*** note
**THIS IS WORK IN PROGRESS**
***

This directory contains definitions of docker images built and pushed
automatically by Infra CI systems.

*** note
TODO(vadimsh): Add links to recipes, builders, bug template.
***

*** note
TODO(vadimsh): Explain what the recipe does when it exists, in particular
what docker tags it uses.
***


Adding an image
---------------

*** note
**TL;DR:** Add a new YAML referring to a Dockerfile to `deterministic/` or
`TODO` subdirectory. See [this doc][1] for the description of possible fields
(or use some existing YAML as a starting point).
***

The initial assumption is that you already have a Dockerfile and can build the
image locally. Additionally, all `COPY` statements in the Dockerfile refer to
either committed files in the repository, or to binaries built from Go code
from infra Go workspace.

Next we need to figure out how often to build this image. This depends on
whether the Dockerfile is "deterministic" or not. A Dockerfile is considered
deterministic if it can be understood as a **pure** function that takes the base
image, the context directory and produces a new image.

Examples of things that make Dockerfile **not** deterministic:
  * Using `RUN apt-get` or any other remote calls to non-pinned resources.
  * Cloning repositories from `master` ref (or similar).
  * Fetching external resources using `RUN curl` or `RUN wget`.

Deterministic images are attempted to be built by the Infra CI on
*every commit*, but because they are deterministic, there's often no need to
actually build anything new because inputs do not change. As a result, we get
a new image only when something really changes.

Non-deterministic images are built once per day. Building them on every commit
is generally very wasteful, since each new commit (even totally unrelated one)
produces a new image, even if nothing really changes.

If your image is **deterministic**, create a new YAML in `deterministic/`
subdirectory (name it after your image):

```yaml
name: <image-name-excluding-registry>
extends: ../base.yaml

dockerfile: <path-to-Dockerfile-relative-to-this-yaml>
deterministic: true

# Optional list of build steps to execute prior to launching the Docker build.
#
# See the doc below.
build:
  ...
```

Images built deterministically are tagged using the following scheme:
  * If built on post-commit builders (production or not): `TODO`.
  * If built on pre-commit builders: `TODO`.

If your image is **non-deterministic**, then:

*** note
TODO(vadimsh): Set this up.
***

See [this doc][1] for the
description of possible fields that can appear in the YAMLs.

[1]: ../../go/src/infra/cmd/cloudbuildhelper/README.md


Adding a pinned base image
--------------------------

To support reproducibility of builds and deduplication of images marked as
deterministic, all base images are pinned to their concrete `@sha256:...`
digests in [pins.yaml](./pins.yaml) file. This file represents a point-in-time
snapshot of `image:tag => @sha256:...` mapping of all base images.

If your Dockerfile uses `FROM ...` line that refers to `image:tag` not yet in
`pins.yaml`, add it there by running:

```shell
# Activate infra go environment to add cloudbuildhelper to PATH.
eval `./go/env.py`

# Resolve the tag and add it to pins.yaml.
cloudbuildhelper pins-add build/images/pins.yaml <image>:<tag>
```

The same command can be used to "move" some single specific pin. If you want to
move *all* pins at once, run:

```shell
# Activate infra go environment to add cloudbuildhelper to PATH.
eval `./go/env.py`

# Resolves all tags in pins.yaml and updates the file.
cloudbuildhelper pins-update build/images/pins.yaml
```

This command is run periodically on CI system to keep all base tags up-to-date.

*** note
TODO(vadimsh): Set this up.
***


Testing changes locally
-----------------------

After adding or changing a YAML manifest or `pins.yaml`, you can use
`cloudbuildhelper` tool to verify the change.

If you have Docker installed and want a completely local build, run:

```shell
# Activate infra go environment to add cloudbuildhelper to PATH and to build Go.
eval `./go/env.py`

# Run the build using local Docker. This doesn't push anything anywhere, but
# the image will be available in the local Docker cache.
cloudbuildhelper localbuild build/images/.../<your-yaml>.yaml
```

If you don't have local Docker or prefer a more comprehensive check that
essentially repeats what CI builders would do:

```shell
# Activate infra go environment to add cloudbuildhelper to PATH and to build Go.
eval `./go/env.py`

# Run the build using Cloud Build, push the result to the dev registry.
cloudbuildhelper build build/images/.../<your-yaml>.yaml -tag my-tag

# On success, the image is available as
#    gcr.io/chops-public-nonprod-images/<name-from-yaml>:my-tag
```

For this to work you need to be in TODO group. This grants permission to use
dev copy of the build infrastructure (dev Cloud Build instance, dev Google
Storage, dev Container Registry).
