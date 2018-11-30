# Tricium Analyzer Contribution

## Types of Tricium functions

A **Tricium function** is takes some input and produces some output; there are
two types of functions, analyzers and isolators:

A **Tricium analyzer** takes some input and produces Tricium `RESULTS`, which is
basically a list of comments that can be posted to Gerrit. Various different
analyzers may potentially use different input data types, so there are other
functions which can take some input and produce an intermediate data type.

Functions that don't produce results, but instead produce intermediate data are
called **isolators**. For example, GitFileIsolator takes `GIT_FILE_DETAILS` and
produces `FILES`, Most of the time, most people will want to develop analyzers
that use some existing data type, but the process for developing an isolator is
the same.

The input and output types that functions can take are defined in
[data.proto](../api/v1/data.proto).

## Simple Function Example

Instructions below are based on the
[Tricium Hello analyzer](../functions/hello/) which is a tiny analyzer that
takes `FILES` and produces `RESULTS` with a comment saying "Hello". This example
demonstrates an Analyzer that doesn't have any dependencies.

Other function examples may be found in [tricium/functions/](../functions/).

### Implement an Analyzer

Create a binary that consumes needed Tricium data, by reading from a
`tricium/data/<input-type>.json` file, and produces Tricium data, by writing to
a `tricium/data/<output-type>.json` file. You can find details about Tricium
data types, and their file paths, in [data.proto](../api/v1/data.proto).

### Dependencies

Note that many Tricium analyzers are actually wrappers for third-party tools; in
general, for tools like this, we need to retrieve the third-party tool and its
dependencies.

If third-party dependencies required, they should be fetched and included in
the CIPD package, but generally should not checked into source. The
dependencies may be fetched using a set-up script that is run at package-build
time. For example, the [eslint](../functions/eslint/) function uses a script
called setup.py that is run before building and uploading a CIPD package.

### Local testing

Besides writing unit tests, you can also test run your analyzer locally, because
the analyzer is just a program that reads from local files and writes to local
files. You can make an example test input directory, for example
[tricium/functions/spacey/test/](../functions/spacey/test/).

Then, you can build your program (if necessary) and run it. For Go programs,
this may be done by running `go build` and then invoking the resulting binary
with the arguments `-input` and `-output`.

### Set up CIPD Package

Make sure you have the CIPD client installed; see
[installation instructions](https://dev.chromium.org/developers/how-tos/install-depot-tools).
Add a cipd.yaml file to the root of your analyzer's directory tree, e.g.
[hello/cipd.yaml](../functions/hello/cipd.yaml):

```
package: infra/tricium/function/hello
install_mode: symlink
data:
        - file: hello
```

Note that package should be `infra/tricium/functions/ANALYZER`, replacing
CamelCase (e.g. ClangTidy) with words separated with dashes, e.g. (clang-tidy).
The data section should list files to be included in the CIPD package; see
[cipd/client/cipd/local/pkgdef.go](https://github.com/luci/luci-go/blob/master/cipd/client/cipd/local/pkgdef.go#L35)
for details.

### Deploy CIPD Package

Run the CIPD command line tool to create and tag the new release. If the CIPD
client complains about a lack of authentication, contact tricium-dev@google.com
to get added to the "tricium-contributors" group.

Uploading a new version of an analyzer usually has two steps: uploading a new
instance and setting the ref "live" to that instance.

There is a convenience helper script [update.sh](../functions/update.sh) which
may be used to update analyzers.

```
$ cipd create -pkg-def cipd.yaml
…
infra/tricium/function/hello:5b010cd78bc78252dda3e791cd6510c56111a990 was successfully registered
$ cipd set-ref infra/tricium/functions/hello -ref live -version 5b010cd78bc78252dda3e791cd6510c56111a990
[P26551 20:36:06.432 client.go:1004 I] cipd: setting ref of "infra/tricium/function/hello": "live" => "5b010cd78bc78252dda3e791cd6510c56111a990"
Packages:
  infra/tricium/function/hello:5b010cd78bc78252dda3e791cd6510c56111a990
```

NB! If your analyzer contains compiled binaries, make sure that the target
platform for your built binaries are the same as the platform that will run the
analyzer; for example, if your analyzer will run on Windows, you must build for
Windows. The place where the runtime platform is configured is in the analyzer
definition; see the example config below, which specifies "UBUNTU".

### About CIPD Packages

CIPD packages are basically zip files with a manifest file. They have an
instance ID which is a digest of the zip package, which may look like
`ZEBe-8SEx5Z3TQ_bby6Ok82WbLc71YPdLEAnGWjmHKsC`.

CIPD package instances have a package name and version. Versions can be the
instance ID, or a ref, such as "live". It's conventional for Tricium analyzers
to use the "live" ref, which is set in the analyzer definition in the config
file, as in the example below.

### Configure your Analyzer

There are two different places where Analyzer definitions can be located: - The
Tricium service configs (either
[tricium-prod](https://luci-config.appspot.com/#/services/tricium-prod) or
[tricium-dev](https://luci-config.appspot.com/#/services/tricium-dev)) - Your
project config (example
[tricium-dev.cfg](https://chromium.googlesource.com/infra/infra/+/infra/config/tricium-dev.cfg)).

An analyzer definition looks like this:

```
functions {
  type: ANALYZER
  name: "Hello"
  needs: FILES
  provides: RESULTS
  owner: "emso@chromium.org"
  component: "monorail:Infra>Platform>Tricium>Analyzer"
  impls {
    runtime_platform: UBUNTU
    provides_for_platform: UBUNTU
    cmd {
      exec: "hello"
      args: "--output=${ISOLATED_OUTDIR}"
    }
    deadline: 30
    cipd_packages {
      package_name: "infra/tricium/function/hello"
      path: "."
      version: "live"
    }
  }
}
```

In the project config, you'll want to choose what subset of available functions
should be enabled for the project. Here you can add your analyzer and any
isolators that it depends on:

```
selections {
  function: "GitFileIsolator"
  platform: UBUNTU
}

selections {
  function: "Hello"
  platform: UBUNTU
}
```

Testing and release process:

*   In the project config for a test project connected to tricium-dev (e.g.
    [playground/gerrit-tricium](https://chromium.googlesource.com/playground/gerrit-tricium)),
    add the analyzer definition and selection to the project config. Upload an
    example CL to test.
*   If the analyzer is applicable for multiple projects, you can move the
    analyzer definition to the service config (still on tricium-dev) and test.
*   Finally, update the project and/or service config on tricium-prod.

For new versions of an analyzer:

*   Update the project config of a project connected to tricium-dev with a new
    analyzer implementation using the new cipd package of the analyzer.
*   If applicable, move analyzer implementation to the service config on
    tricium-dev.
*   Finally, update the project and/or service config on tricium-prod.

## Analyzer guidelines

### What makes a good analyzer?

-   An analyzer should not be too noisy; for example, you should aim for false
    positive rate of less than 10%. That is, messages should be "useful" at
    least 90% of the time. Categories of comments that have been found to be too
    noisy should be disabled or improved.
-   An analyzer should be fast enough so that results can generally appear
    before the reviewer reviews the CL; for example, you should aim for results
    in under 10 minutes.
-   An analyzer should produce clear and actionable comments.

A Tricium analyzer can take more time and include more checks than presubmit. It
should find some results when run on the whole codebase, but not too many so
that it's overwhelming.

### How to Release a New Analyzer Version

If you have an analyzer that's already running and configured, and you want to
release a new version, the following is a general process for release:

First, test locally; try both unit tests and a test-invocation on sample input.
Note, you can run Go unit tests by running `go test ./...`. Make sure you run
this on a machine that is binary-compatible with the actual Swarming task
environment.

Optionally, **try with a local devserver instance of Tricium.** The advantage of
testing it out with a devserver instance is that you can change the configs
without making any actual changes by changing
[tricium/appengine/devcfg](../appengine/devcfg/).

After you're ready, upload it as described above in the "Deploy CIPD Package"
section, by running the cipd commands yourself or possibly by running `update.sh
my-analyzer` from [tricium/functions](../functions).

Then, **try it out on a real project**. You can add your analyzer to the project
config for
[the playground repo](https://chromium.googlesource.com/playground/gerrit-tricium)
if there's no other suitable project.

After testing with the tricium-dev instance, you can add it to the tricium-prod
instances service config and announce the release on tricium-dev@google.com.
