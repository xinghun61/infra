# Adding a new wheel for vpython

For this example, we'll be adding 'scandir' at version 1.7.

1. Go to pypi and find the wheel at the appropriate version in question.
   1. Project: https://pypi.org/project/scandir
   1. Versions: https://pypi.org/project/scandir/#history
   1. Version 1.7: https://pypi.org/project/scandir/1.7/
   1. Files for 1.7: https://pypi.org/project/scandir/1.7/#files

1. Determine what type of wheel it is (in order of preference):
   1. Universal
      1. Pure-python libraries already packaged as wheels.
      1. These will have a `*-py2.py3-none-any.whl` file (may be just py2)
      1. Example: https://pypi.org/project/requests/#files
   1. UniversalSource
      1. Pure-python libraries distributed as a tarball.
      1. These will have a `*.tar.gz` file. You'll have to fetch this tarball
         and look to see if it contains any .c or .cc files. If it does, then
         this is either `Prebuilt` or `SourceOrPrebuilt`.
      1. Example: https://pypi.org/project/httplib2/#files
   1. Prebuilt
      1. Python libs with c extensions, pre-built for platforms we care about.
      1. These will have many .whl files for various platforms. Look at the list
         to see if it covers all the platforms your users care about. If not
         then you may have to use `SourceOrPrebuilt.`
      1. Example: https://pypi.org/project/pillow/#files
   1. PrebuiltOrSource
      1. Python libs with c extensions, pre-built for some platforms we care
         about. These don't require extra C libraries though, just typical
         system/python C libraries.
      1. They will include `*.tar.gz` with the library source, but may also
         contain `.whl` files for some platforms.
      1. Example: https://pypi.org/project/scandir/#files
      1. Example (no .whl): https://pypi.org/project/wrapt/#files
   1. "Special" wheels
      1. These deviate from the wheels above in some way, usually by requiring
         additional C libraries.
      1. We always prepare our wheels and their C extensions to be as static as
         possible. Generally this means building the additional C libraries as
         static ('.a') files, and adjusting the python setup.py to find this.
      1. See the various implementations referenced by wheel.py to get a feel
         for these.
      1. These are (fortunately) pretty rare (but they do come up occasionally).
   1. The "infra_libs" wheel
      1. This one is REALLY special, but essentially packages the
         [packages/infra_libs](/packages/infra_libs) wheel. Check
         wheel_infra.py.


Once you've identified the wheel type, open [wheel.py](./wheel.py) and find the
relevant section. Each section is ordered by wheel name and then by symver. If
you put the wheel definition in the wrong place, dockerbuild will tell you :)

So for `scandir`, we see that there are prebuilts for windows, but for
everything else we have to build it ourself.

The wheels are built for linux platforms using Docker (hence "dockerbuild").
Unfortunately this tool ONLY supports building for linux this way. For building
mac and windows, this can use the ambient toolchain (i.e. have XCode or MSVS
installed on your system).

*** note
I actually haven't ever run this on windows. Usually python wheels with
C extensions that chromium may actually need have pre-built windows wheels.

That said, this is essentially just doing `setup.py bdist_wheel` to generate the
wheel contents, so if that process works with MSVS, it SHOULD work.
***

The upshot of this is that if you need to build for e.g. mac or windows, you
need to run this from one of those platforms with an appropriate SDK installed.

Back to our example, we'll be adding a new entry to the SourceOrPrebuilt
section:

    SourceOrPrebuilt('scandir', '1.9.0',
        packaged=[
          'windows-x86',
          'windows-x64',
        ],
    ),

This says the wheel `scandir-1.9.0` is either built from source (.tar.gz) or is
prebuilt (for the following `packaged` platforms).

Finally, we need to build it:

    path/to/infra.git/run.py         \
       infra.tools.dockerbuild       \
       --logs-debug --upload-source  \
       wheel-build                   \
       --wheel 'scandir-1.9.0'       \
       --upload

Notable options (check `--help` for details):
  * `--wheel_re` - Use in place of `--wheel` to run for multiple wheels or
    versions.
  * `--platform` - Specify a specific platform to build for.
  * If you don't have upload permission, you can still check your change to
    `wheels.py` by omitting the two "upload" flags above.

This command will build (into path/to/infra.git/.dockerbuild) all of the .whl
files, and then upload them to CIPD (for use by vpython).

And update the wheel.md documentation:

    path/to/infra.git/run.py         \
       infra.tools.dockerbuild       \
       wheel-dump

NOTE: If this shows a change for `infra_libs` it means that someone modified
`infra_libs` without uploading it to CIPD. To fix this, run:

    path/to/infra.git/run.py         \
       infra.tools.dockerbuild       \
       --logs-debug --upload-source  \
       wheel-build                   \
       --wheel_re 'infra_libs.*'     \
       --upload

Then you upload your CL and commit as usual.

Since the 'wheel-build' command is executed locally (i.e. not by a bot) we
typically TBR these changes to an OWNER as long as they're only touching
wheels.py and wheels.md (since 'wheel-build' pushes the wheels directly to
CIPD/prod).
