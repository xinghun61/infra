Infra steps in the builds
=========================

This page describes the purpose of various common steps in builders on the
waterfall and tryservers.

+------------------------+-----------------------------------------------------+
| Step name              | Purpose/descripion                                  |
+========================+=====================================================+
| find_isolated_tests    | Returns a list of *.isolated files together with    |
|                        | their SHA1 hashes. Such hash identifies the         |
|                        | isolated file tree. It's passed from builder to     |
|                        | a tester, or to a swarming job where it is used to  |
|                        | reconstruct the file tree (by downloading files     |
|                        | from the isolate server). *.isolated files are      | 
|                        | built during compilation (ninja invokes isolate.py) |
+------------------------+-----------------------------------------------------+
| clean_isolated_files   | Removes .isolate files from the build directory     |
|                        | before compilation (and isolation), to ensure no    |
|                        | stale *.isolated are left.                          | 
+------------------------+-----------------------------------------------------+
| cleanup_temp           | This step is a hack, which tries to delete portions |
|                        | of the live temp directory based on a variety of    |
|                        | hard-coded globs. This is not scalable as people    |
|                        | change file names and do not update globs and won't |
|                        | work on Windows, since processes with handles to    |
|                        | files make them un-deletable, so there is no way    |
|                        | to have this step *fail*, since there's no way to   |
|                        | know if it *should* be able to delete a given file. |
+------------------------+-----------------------------------------------------+
