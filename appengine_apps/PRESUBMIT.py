# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""appengine-specific presubmit for running pylint.
"""

# LGTM FROM iannucci@ REQUIRED TO EDIT THIS LIST:
DISABLED_PYLINT_WARNINGS = [
  'W0231',  # __init__ method from base class is not called
  'W0232',  # Class has no __init__ method
]

DISABLED_PROJECTS = [
    # Swarming components hacks sys.path to thus skip tools/

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


def IgnoredPaths(input_api): # pragma: no cover
  # This computes the list if repository-root-relative paths which are
  # ignored by .gitignore files. There is probably a faster way to do this.
  status_output = input_api.subprocess.check_output(
      ['git', 'status', '--porcelain', '--ignored'])
  statuses = [(line[:2], line[3:]) for line in status_output.splitlines()]
  return [path for (mode, path) in statuses if mode in ('!!', '??')]


def PythonRootForPath(input_api, path):
  # For each path, walk up directories until find no more __init__.py
  # The directory above the last __init__.py is considered our root.
  root = input_api.os_path.dirname(path)
  while True:
    init_file = input_api.os_path.join(root, '__init__.py')
    if not input_api.os_path.isfile(init_file):
      break
    root = input_api.os_path.dirname(root)

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


def GetAppEngineLibraryPaths(input_api, appengine_env_path):  # pragma: no cover
  # AppEngine has a wrapper_util module which knows where the various
  # appengine libraries are stored inside the SDK. All AppEngine scripts
  # 'import wrapper_util' and then call its various methods to get those
  # paths to fix their sys.path. Since AppEngine isn't in our sys.path yet
  # we use imp.load_source to load wrapper_util from an absolute path
  # and then call its methods to get all the paths to the AppEngine-provided
  # libraries to add to sys.path when calling pylint.
  import imp
  wrapper_util_path = input_api.os_path.join(appengine_env_path,
      'wrapper_util.py')
  wrapper_util = imp.load_source('wrapper_util', wrapper_util_path)
  wrapper_util_paths = wrapper_util.Paths(appengine_env_path)
  appengine_lib_paths = wrapper_util_paths.script_paths('dev_appserver.py')
  # Unclear if v2_extra_paths is correct here, it contains endpoints
  # and protorpc which several apps seem to depend on.
  return appengine_lib_paths + wrapper_util_paths.v2_extra_paths


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

  pylint_path = input_api.os_path.join(depot_tools_path,
      'third_party', 'pylint.py')

  # Make paths relative to pylint_root
  for filename in files:
    assert(filename.startswith(pylint_root + '/') if pylint_root else True)
  files = [filename[len(pylint_root)+1:] if pylint_root else filename
           for filename in files]

  kwargs = {'env': env, 'stdin': '\n'.join(pylint_args + files)}
  if pylint_root:
    kwargs['cwd'] = pylint_root

  # Pass args via stdin, because windows (command line limit).
  return input_api.Command(
      name='Pylint (%s files under %s)' % (len(files), pylint_root),
      cmd=[input_api.python_executable,
           pylint_path,
           '--args-on-stdin'],
      kwargs=kwargs,
      message=output_api.PresubmitError)


def PylintChecks(input_api, output_api):  # pragma: no cover
  infra_root = input_api.os_path.dirname(input_api.PresubmitLocalPath())

  # DEPS specifies depot_tools, google_appengine as siblings of infra.
  appengine_env_path = input_api.os_path.join(
      input_api.os_path.dirname(infra_root),
      'google_appengine')
  venv_path = input_api.os_path.join(infra_root, 'ENV', 'lib', 'python2.7')

  # Cause all pylint commands to execute in the virtualenv
  input_api.python_executable = (
    input_api.os_path.join(infra_root, 'ENV', 'bin', 'python'))

  white_list = ['.*\.py$']
  black_list = list(input_api.DEFAULT_BLACK_LIST)
  black_list += DISABLED_PROJECTS
  black_list += IgnoredPaths(input_api)

  appengine_lib_paths = GetAppEngineLibraryPaths(input_api, appengine_env_path)
  extra_syspaths = [appengine_env_path, venv_path] + appengine_lib_paths

  # FIXME: FetchAllFiles is extremely slow (35s on my Mac Book Pro)
  # we need to profile this and make it much faster.
  all_python_files = FetchAllFiles(input_api, white_list, black_list)

  root_to_paths = GroupPythonFilesByRoot(input_api, all_python_files)
  source_filter = lambda path: input_api.FilterSourceFile(path,
      white_list=white_list, black_list=black_list)
  # Compute paths of changed files relative to the present file.
  changed_py_files = [
      f.AbsoluteLocalPath()[len(input_api.PresubmitLocalPath())+1:]
      for f in input_api.AffectedSourceFiles(source_filter)]

  dirty_roots = DirtyRootsFromAffectedFiles(changed_py_files, root_to_paths)

  tests = []
  for root_path in sorted(dirty_roots):
    python_files = root_to_paths[root_path]

    input_api.logging.info('Running appengine_apps pylint on %d files under %s',
        len(python_files), root_path)
    syspaths = extra_syspaths

    tests.append(PylintFiles(input_api, output_api, python_files, root_path,
      DISABLED_PYLINT_WARNINGS, syspaths))
  return tests


def CommonChecks(input_api, output_api):  # pragma: no cover
  output = input_api.RunTests(PylintChecks(input_api, output_api))
  return output


def CheckChangeOnUpload(input_api, output_api):  # pragma: no cover
  output = CommonChecks(input_api, output_api)
  return output


def CheckChangeOnCommit(input_api, output_api):  # pragma: no cover
  output = CommonChecks(input_api, output_api)
  return output
