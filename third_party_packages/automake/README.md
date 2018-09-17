This is the package definition for the automake tools and includes a patch to
make them relocatable (written against automake 1.15).

By default automake hard-codes the --prefix value into the binaries it deploys,
making them unsuitable for relocatable deployment (e.g. with CIPD). The patch
here replaces all the hard-coded paths with either:
  * The assumption that the tool is in $PATH, and so "/path/to/tool" is replaced
    by "tool"
  * The assumption that the data files are relative to the binary being run,
    e.g. if we're running ".../bin/tool" that we can find the data files at
    ".../share/extra_files".

The patch was made by doing `make install` on the base package, looking for
absolute paths and then changing the sources so the absolute paths no longer
showed up in the output of `make install`.

