# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Top-level presubmit script for infra.

See http://dev.chromium.org/developers/how-tos/depottools/presubmit-scripts for
details on the presubmit API built into gcl.
"""

DISABLED_TESTS = [
    '.*appengine/chromium_status/tests/main_test.py',
    '.*appengine/chromium_build/app_test.py',
]

# LGTM FROM iannucci@ REQUIRED TO EDIT THIS LIST:
DISABLED_PYLINT_WARNINGS = [
  'W0231',  # __init__ method from base class is not called
  'W0232',  # Class has no __init__ method
]

DISABLED_PROJECTS = [
    # Taken care of by appengine/PRESUBMIT.py
    'appengine/*',
    'infra/services/lkgr_finder',
    'infra/services/gnumbd',

    # Don't bother pylinting (these could also move to .gitignore):
    '.*/__pycache__',
    '\.git',
    '\.wheelcache',
    'bootstrap/virtualenv',
]


# Forked from depot_tools/presubmit_canned_checks._FetchAllFiles
def FetchAllFiles(input_api, white_list, black_list):
  import datetime
  start_time = datetime.datetime.now()
  def Find(filepath, filters):
    return any(input_api.re.match(item, filepath) for item in filters)

  repo_path = input_api.PresubmitLocalPath()
  def MakeRootRelative(dirpath, item):
    path = input_api.os_path.join(dirpath, item)
    # Poor man's relpath:
    if path.startswith(repo_path):  # pragma: no cover
      return path[len(repo_path) + 1:]
    return path  # pragma: no cover

  dirs_walked = []

  files = []
  for dirpath, dirnames, filenames in input_api.os_walk(repo_path):
    dirs_walked.append(dirpath)
    for item in dirnames[:]:
      filepath = MakeRootRelative(dirpath, item)
      if Find(filepath, black_list):
        dirnames.remove(item)
    for item in filenames:
      filepath = MakeRootRelative(dirpath, item)
      if Find(filepath, white_list) and not Find(filepath, black_list):
        files.append(filepath)
  duration = datetime.datetime.now() - start_time
  input_api.logging.info('FetchAllFiles found %s files, searching '
      '%s directories in %ss' % (len(files), len(dirs_walked),
      duration.total_seconds()))
  return files


def EnvAddingPythonPath(input_api, extra_python_paths):
  # Copy the system path to the environment so pylint can find the right
  # imports.
  # FIXME: Is there no nicer way to pass a modified python path
  # down to subprocess?
  env = input_api.environ.copy()
  import sys
  env['PYTHONPATH'] = input_api.os_path.pathsep.join(
      extra_python_paths + sys.path).encode('utf8')
  return env


# Forked with prejudice from depot_tools/presubmit_canned_checks.py
def PylintFiles(input_api, output_api, files, pylint_root, disabled_warnings,
      extra_python_paths):  # pragma: no cover
  input_api.logging.debug('Running pylint on: %s', files)

  # FIXME: depot_tools should be right next to infra, however DEPS
  # recursion into build/DEPS does not seem to be working: crbug.com/410070
  canned_checks_path = input_api.canned_checks.__file__
  canned_checks_path = input_api.os_path.abspath(canned_checks_path)
  depot_tools_path = input_api.os_path.dirname(canned_checks_path)

  pylintrc_path = input_api.os_path.join(depot_tools_path, 'pylintrc')
  pylint_args = ['--rcfile=%s' % pylintrc_path]
  pylint_args.extend(['-d', ','.join(disabled_warnings)])

  env = EnvAddingPythonPath(input_api, extra_python_paths)

  pytlint_path = input_api.os_path.join(depot_tools_path,
      'third_party', 'pylint.py')

  # Pass args via stdin, because windows (command line limit).
  return input_api.Command(
      name='Pylint (%s files under %s)' % (len(files), pylint_root),
      cmd=[input_api.python_executable,
           pytlint_path,
           '--args-on-stdin'],
      kwargs={'env': env, 'stdin': '\n'.join(pylint_args + files)},
      message=output_api.PresubmitError)


def IgnoredPaths(input_api): # pragma: no cover
  # This computes the list if repository-root-relative paths which are
  # ignored by .gitignore files. There is probably a faster way to do this.
  status_output = input_api.subprocess.check_output(
      ['git', 'status', '--porcelain', '--ignored'])
  statuses = [(line[:2], line[3:]) for line in status_output.splitlines()]
  return [
    input_api.re.escape(path) for (mode, path) in statuses
    if mode in ('!!', '??') and not path.endswith('.pyc')
  ]


def PythonRootForPath(input_api, path):
  # For each path, walk up dirtories until find no more __init__.py
  # The directory with the last __init__.py is considered our root.
  root = input_api.os_path.dirname(path)
  while True:
    root_parent = input_api.os_path.dirname(root)
    parent_init = input_api.os_path.join(root_parent, '__init__.py')
    if not input_api.os_path.isfile(parent_init):
      break
    root = root_parent
  return root


def GroupPythonFilesByRoot(input_api, paths):
  sorted_paths = sorted(paths)
  import collections
  grouped_paths = collections.defaultdict(list)
  for path in sorted_paths:
    # FIXME: This doesn't actually need to touch the filesystem if we can
    # trust that 'paths' contains all __init__.py paths we care about.
    root = PythonRootForPath(input_api, path)
    grouped_paths[root].append(path)
  # Convert back to a normal dict before returning.
  return dict(grouped_paths)


def DirtyRootsFromAffectedFiles(changed_py_files, root_to_paths):
  # Compute root_groups for all python files
  path_to_root = {}
  for root, paths in root_to_paths.items():
    for path in paths:
      path_to_root[path] = root

  # Using the above mapping, compute the actual roots we need to run
  dirty_roots = set()
  for path in changed_py_files:
    dirty_roots.add(path_to_root[path])
  return dirty_roots


def NoForkCheck(input_api, output_api): # pragma: no cover
  """Warn when a file that should not be modified is modified.

  This is useful when a file is to be moved to a different place
  and is temporarily copied to preserve backward compatibility. We don't
  want the original file to be modified.
  """
  # Files that must not be modified (regex)
  # Paths tested are relative to the directory containing this file.
  # Ex: infra/libs/logs.py
  black_list = ['^infra/libs']
  black_list_re = [input_api.re.compile(regexp) for regexp in black_list]
  offending_files = []
  for filename in input_api.AffectedTextFiles():
    if any(regexp.search(filename.LocalPath()) for regexp in black_list_re):
      offending_files.append(filename.LocalPath())
  if offending_files:
    return [output_api.PresubmitPromptWarning(
      'You modified files that should not be modified. Look for a NOFORK file\n'
      + 'in a directory above those files to get more context:\n%s'
      % '\n'.join(offending_files)
      )]
  return []



def EmptiedFilesCheck(input_api, output_api): # pragma: no cover
  """Warns if a CL empties a file.

  This is not handled properly by apply_patch from depot_tools: the
  file would not exist at all on trybot checkouts.
  """
  empty_files = []
  infra_root = input_api.PresubmitLocalPath()
  for filename in input_api.AffectedTextFiles():
    fullname = input_api.os_path.join(infra_root, filename.LocalPath())
    if not input_api.os_stat(fullname).st_size:
      empty_files.append(filename.LocalPath())
  if empty_files:
    return [output_api.PresubmitPromptWarning(
      'Empty files found in the CL. This can cause trouble on trybots\n'
      + 'if your change depends on the existence of those files:\n%s'
      % '\n'.join(empty_files)
      )]
  return []


def BrokenLinksChecks(input_api, output_api):  # pragma: no cover
  """Complains if there are broken committed symlinks."""
  stdout = input_api.subprocess.check_output(['git', 'ls-files'])
  files = stdout.splitlines()
  output = []
  infra_root = input_api.PresubmitLocalPath()
  for filename in files:
    fullname = input_api.os_path.join(infra_root, filename)
    if (input_api.os_path.lexists(fullname)
        and not input_api.os_path.exists(fullname)):
      output.append(output_api.PresubmitError('Broken symbolic link: %s'
                                              % filename))
  return output


def PylintChecks(input_api, output_api):  # pragma: no cover
  infra_root = input_api.PresubmitLocalPath()
  # DEPS specifies depot_tools, as sibling of infra.
  venv_path = input_api.os_path.join(infra_root, 'ENV', 'lib', 'python2.7')

  # Cause all pylint commands to execute in the virtualenv
  input_api.python_executable = (
    input_api.os_path.join(infra_root, 'ENV', 'bin', 'python'))

  white_list = ['.*\.py$']
  black_list = list(input_api.DEFAULT_BLACK_LIST)
  black_list += DISABLED_PROJECTS
  black_list += ['.*\.pyc$', '.*_pb2\.py']
  black_list += IgnoredPaths(input_api)

  extra_syspaths = [venv_path]

  all_python_files = FetchAllFiles(input_api, white_list, black_list)

  root_to_paths = GroupPythonFilesByRoot(input_api, all_python_files)
  source_filter = lambda path: input_api.FilterSourceFile(path,
      white_list=white_list, black_list=black_list)
  changed_py_files = [f.LocalPath()
      for f in input_api.AffectedSourceFiles(source_filter)]
  dirty_roots = DirtyRootsFromAffectedFiles(changed_py_files, root_to_paths)

  tests = []
  for root_path in sorted(dirty_roots):
    python_files = root_to_paths[root_path]
    if root_path == '':
      root_path = input_api.PresubmitLocalPath()
    input_api.logging.info('Running pylint on %d files under %s',
        len(python_files), root_path)

    syspaths = extra_syspaths + [root_path]

    tests.append(PylintFiles(input_api, output_api, python_files, root_path,
      DISABLED_PYLINT_WARNINGS, syspaths))
  return tests


def CommonChecks(input_api, output_api):  # pragma: no cover
  output = input_api.RunTests(PylintChecks(input_api, output_api))
  output.extend(BrokenLinksChecks(input_api, output_api))
  return output


def CheckChangeOnUpload(input_api, output_api):  # pragma: no cover
  output = CommonChecks(input_api, output_api)
  output.extend(NoForkCheck(input_api, output_api))
  output.extend(EmptiedFilesCheck(input_api, output_api))
  return output


def CheckChangeOnCommit(input_api, output_api):  # pragma: no cover
  output = CommonChecks(input_api, output_api)
  output.extend(input_api.canned_checks.CheckOwners(input_api, output_api))
  output.extend(input_api.canned_checks.CheckTreeIsOpen(
      input_api,
      output_api,
      json_url='http://infra-status.appspot.com/current?format=json'))
  return output


# Unused argument - pylint: disable=W0613
def GetPreferredTryMasters(project, change):  # pragma: no cover
  return {
    'tryserver.chromium.linux': {
      'infra_tester': set(['defaulttests']),
    }
  }
