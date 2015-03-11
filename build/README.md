Scripts and files in this directory describe how to build CIPD packages from
the source code in infra.git repo.

There are two flavors of packages:
  * Packages with executables compiled from Go code.
  * Single giant package with all python code and archived virtual environment
    needed to run it.

A package is defined in a *.yaml file with the following structure:

  # Name of the package in CIPD repository.
  package: infra/example/package
  # Human readable description of the package.
  description: Example package
  # Path to the root of the package source files on the system we're building
  # the package from. Can be absolute or relative to the path of the *.yaml
  # file itself.
  root: ../..

  data:
    # 'dir' section adds a subdirectory of 'root' to the package. In this case
    # it will scan directory <yaml_path>/../../a/b/c and put files into a/b/c
    # directory of the package.
    - dir: a/b/c
      # A list of regular expressions for files to exclude from the package.
      # Syntax is defined [here](http://golang.org/pkg/regexp/syntax/). Each
      # expression is implicitly wrapped into ^...$. The tests are applied to
      # paths relative to 'dir', e.g. 'bin/active' regexp matches only single
      # file <yaml_path>/../../a/b/c/bin/active.
      exclude:
        - bin/activate
        - .*\.pyc

    # 'file' section adds a single file to the package.
    - file: run.py

Any string in package definition can reference a variable via ${var_name}, for
example:

  package: infra/tools/cipd/${platform}

See packages/*.yaml for examples of package definitions.
