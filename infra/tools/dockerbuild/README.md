# DockerBuild

`infra.tools.dockerbuild` is a management and execution environment for Chrome
Infrastructure's Docker toolchain build environment. Fundamentally, it handles:

- Generation and internment of Chrome Infrastructure Docker build images.
- Specific build instructions for Python wheels.
- Entry point for build operations using Docker toolchains.

DockerBuild is complex. It justifies this complexity by solving some annoying
problems:

- Cross-compiling is really useful. It is difficult to have continuous builders
  for each supported platform, especially the more esoteric ones. Adding support
  for a new platform is decoupled from actually having that platform running.
- Cross-compiling Python wheels is nuanced and full of errors. Python build
  scripts, in general, do not really accommodate cross-compiling without hacks.
  These hacks, and the overall logic, should be enshrined somewhere.
- Building the Python `cryptography` wheel for Linux really sucks. This logic
  and all of its prerequisites should be enshrined in a script somewhere.
- In general, it is really good to zip up build toolchains and environments
  and use them hermetically instead of relying on the configuration of a
  builder somewhere.

## DockerBuild Images

DockerBuild images are based on
[dockcross](https://github.com/dockcross/dockcross) project images. Each
`dockcross` image bundles a platform's toolchain with an entry point script
which can be used to execute commands within that toolchain. The script, when
run, mounts a directory to `/work` within the Docker image and invokes the
provided command on that directory. This allows a user to almost-seamlessly
use the `dockcross` image's toolchain to operate on local files. This, in turn
makes it really easy to cross-compile.

DockerBuild extends `dockcross` images to add:

- A host and cross-compiled Python environment.
- A host Perl installation.
- Several packages in support of generation of complex Python wheels.

See [dockcross.py](dockcross.py) for more details.

DockerBuild images, like `dockcross` images, can be run using a generated entry
point script. This can be created by running the image:

```bash
docker run <image-name> > ./entrypoint.sh
chmod +x ./entrypoint.sh
./entrypoint.sh
```

Alternatively, the script can be run through `dockerbuild` using the `run`
subcommand.

## Note on Windows and Mac

It is important to note that Docker image environments only exist for Linux
systems at the moment. Chrome Infrastructure's build strategy for Windows and
Mac is to actually perform the builds on real Windows and Mac systems. Support
for Windows and Mac Python wheels is built into DockerBuild, but serves mostly
as a wrapper around using `pip` to download pre-generated packages and upload
them to CIPD.

Windows and Mac support are gated on the ability to have a fully-functioning
Windows and Mac build toolchain running in a Linux (i.e., Docker) environment.
This may be possible with a combinaton of `wine` and/or a Mac cross-compiler,
but this is not currently explored or implemented.

## Lifecycle

Walking backwards through the lifecycle of this script:

- Building Python wheels requires
- Python wheel source files, which requires
- Downloading and storing Python sources in CIPD.
- It also requires a DockerBuild image, which requires
- A `dockcross` base image and a set of sources.
- The sources need to be interned in CIPD for consistency.
- The `dockcross` base image needs to be built independently.

Minimal operation will use cached pre-built DockerBuild images and cached
CIPD sources, allowing a user to avoid building everything from scratch.

However, the logic to build everything from scratch is included in DockerBuild
for updates and reproducibility.

### Subcommand: sources

The various sources used to build Python wheels and DockerBuild images must be
downloaded from the Internet and interned in CIPD packages. This ensures that
any given image will be reproducible and resilient to external packaging and
infrastructure changes.

The `sources` subcommand scans through all sources used by DockerBuild,
acquires them, and creates CIPD packages for them. Run `sources` with the
`--help` flag for more information.

If new sources are added, or sources without CIPD packages are identified,
a warning message will be printed at the end of DockerBuild operation
encouraging the user to upload source CIPD packages for future reprocible
builds.

### Subcommand: docker-mirror

The `dockcross` project's images are used as base images for DockerBuild's
specialized images. Rather than rely on upstream Docker hosts, DockerBuild
offers the `docker-mirror` subcommand to load upstream `dockcross` images and
store them in our Google Cloud Docker image registry.

`docker-mirror` can be run to synchronize and/or update the local images. All
DockerBuild images are generated from the local images, not the upstream images,
so an explicit synchronizaton step is required to update their `dockcross`
bases.

### Subcommand: docker-generate

DockerBuild's specialized Docker images can be built locally using the
`docker-generate` subcommand. This will pull the base `dockcross` images
and required sources and construct local DockerBuild images.

Optionally, the local images can be pushed to the Google Cloud Docker image
registry using the `--upload` flag. This ensures that other users of the script
can retrieve and use the images without requiring them to build them locally.

### Subcommand: wheel-build

DockerBuild has specific support for building Python wheels and uploading them
to CIPD. This synergizes with
[vpython](/go/src/infra/tools/vpython)'s CIPD wheel packaging expectations.

Wheels can be built and uploaded by using the `wheel-build` subcommand, and
uploaded using the `--upload` flag.

Support for additional Python wheels and/or wheel versions can be added by
editing [wheel.py](wheel.py) and adding entries for the new wheels.

Adding support for universal wheels is easy. Adding support for **most**
platform-specific binary wheels can range from easy to hacky-difficult depending
on the wheel's binary requirements and suitability for cross-compiling. This has
to be evaluated on a case-by-base basis, sadly.

### Subcommand: run

DockerBuild offers an entry point into a DockerBuild image's toolchain
environment through its `run` subcommand. `run` will mount the specified
directory inside of the DockerBuild enviornment and execute the specified
command against that directory.

`run` can be used to cross-compile software (e.g., `git`) for other Infra
platforms.

## Problems with Known Fixes

### Got permission denied while trying to connect to the Docker daemon socket...

Fix: Add your local user to the docker POSIX group:

```
sudo usermod -a -G docker $USER
```

You need to restart your shell for this to take effect.

### Error response from daemon: squash is only supported with experimental mode

Fix: Run docker in experimental mode (yes, this is a hack):

```
vim /etc/default/docker
# Edit file such that DOCKER_OPTS includes "--experimental=true"
sudo service docker restart
```

## Examples

### Upload all sources to CIPD

To upload all sources to CIPD, run:

```bash
./run.py infra.tools.dockerbuild --upload-sources sources
```

### Update dockcross base image mirrors

To update the Google Cloud repository's mirrored `dockcross` images, run:

```bash
./run.py infra.tools.dockerbuild docker-mirror --upload
```

### Build and upload DockerBuild images

To build new DockerBuild images and upload them to the Google Cloud repository,
run:

```bash
./run.py infra.tools.dockerbuild docker-generate --upload
```

### Regenerate all configured wheels

To ensure that all configured Python wheels are uploaded to CIPD for all known
platforms, run the following command:

```bash
./run.py infra.tools.dockerbuild --upload-sources wheel-build --upload
```

- `--upload-sources` instructs DockerBuild to upload CIPD packages for any
  new wheel sources that are not already locally mirrored.
- `--upload` instructs the `wheel-build` subcommand to upload any wheels that
  are not currently present in CIPD.

This can be run after adding a new wheel configuration, or after adding a new
platform to support.

### Cross-compile Python

To cross-compile Python for the "linux-armv6" platform, download the Python
source, then configure it for the cross-compile enviornment and build.
```bash
wget https://github.com/python/cpython/archive/v2.7.13.tar.gz
cd cpython-2.7.13
./run.py infra.tools.dockerbuild run --platform linux-armv6 run -- \
  sh -c './configure --prefix=/work/PREFIX --host=$CROSS_TRIPLE --build=$(gcc -dumpmachine)'
./run.py infra.tools.dockerbuild run --platform linux-armv6 run -- make install
```

- Note that we use `sh` to ensure that the environment variables are evaluated
  within the container.
- Note that the install prefix is `/work/PREFIX`. This will install into the
  working directory, but all paths will have `/work/PREFIX` hard-coded as their
  prefix. More specific `./configure` options can be used to ensure that the
  configured environment matches the target system environmnet.
