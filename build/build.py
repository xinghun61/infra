#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script rebuilds Python & Go universes of infra.git multiverse and
invokes CIPD client to package and upload chunks of it to the CIPD repository as
individual packages.

See build/packages/*.yaml for definition of packages.
"""

import argparse
import glob
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile


# Root of infra.git repository.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Root of infra gclient solution.
GCLIENT_ROOT = os.path.dirname(ROOT)

# Where to upload packages to by default.
PACKAGE_REPO_SERVICE = 'https://chrome-infra-packages.appspot.com'

# .exe on Windows.
EXE_SUFFIX = '.exe' if sys.platform == 'win32' else ''


class BuildException(Exception):
  """Raised on errors during package build step."""


class UploadException(Exception):
  """Raised on errors during package upload step."""


def run_python(script, args):
  """Invokes a python script.

  Raises:
    subprocess.CalledProcessError on non zero exit code.
  """
  print 'Running %s %s' % (script, ' '.join(args))
  subprocess.check_call(
      args=['python', '-u', script] + list(args), executable=sys.executable)


def run_cipd(go_workspace, cmd, args):
  """Invokes CIPD, parsing -json-output result.

  Args:
    go_workspace: path to 'infra/go' or 'infra_internal/go'.
    cmd: cipd subcommand to run.
    args: list of command line arguments to pass to the subcommand.

  Returns:
    (Process exit code, parsed JSON output or None).
  """
  temp_file = None
  try:
    fd, temp_file = tempfile.mkstemp(suffix='.json', prefix='cipd_%s' % cmd)
    os.close(fd)

    cmd_line = [
      os.path.join(go_workspace, 'bin', 'cipd' + EXE_SUFFIX),
      cmd, '-json-output', temp_file,
    ] + list(args)

    print 'Running %s' % ' '.join(cmd_line)
    exit_code = subprocess.call(args=cmd_line, executable=cmd_line[0])
    try:
      with open(temp_file, 'r') as f:
        json_output = json.load(f)
    except (IOError, ValueError):
      json_output = None

    return exit_code, json_output
  finally:
    try:
      if temp_file:
        os.remove(temp_file)
    except OSError:
      pass


def print_title(title):
  """Pretty prints a banner to stdout."""
  sys.stdout.flush()
  sys.stderr.flush()
  print
  print '-' * 80
  print title
  print '-' * 80


def build_go(go_workspace, packages):
  """Bootstraps go environment and rebuilds (and installs) Go packages.

  Compiles and installs packages into default GOBIN, which is <path>/go/bin/
  (it is setup by go/env.py and depends on what workspace is used).

  Args:
    go_workspace: path to 'infra/go' or 'infra_internal/go'.
    packages: list of packages to build (can include '...' patterns).
  """
  print_title('Compiling Go code: %s' % ', '.join(packages))

  # Go toolchain embeds absolute paths to *.go files into the executable. Use
  # symlink with stable path to make executables independent of checkout path.
  new_root = None
  new_workspace = go_workspace
  if sys.platform != 'win32':
    new_root = '/tmp/_chrome_infra_build'
    if os.path.exists(new_root):
      assert os.path.islink(new_root)
      os.remove(new_root)
    os.symlink(GCLIENT_ROOT, new_root)
    rel = os.path.relpath(go_workspace, GCLIENT_ROOT)
    assert not rel.startswith('..'), rel
    new_workspace = os.path.join(new_root, rel)

  # Remove any stale binaries and libraries.
  shutil.rmtree(os.path.join(new_workspace, 'bin'), ignore_errors=True)
  shutil.rmtree(os.path.join(new_workspace, 'pkg'), ignore_errors=True)

  # Recompile ('-a').
  try:
    subprocess.check_call(
        args=[
          'python', '-u', os.path.join(new_workspace, 'env.py'),
          'go', 'install', '-a', '-v',
        ] + list(packages),
        executable=sys.executable,
        stderr=subprocess.STDOUT)
  finally:
    if new_root:
      os.remove(new_root)


def enumerate_packages_to_build(package_def_dir, package_def_files=None):
  """Returns a list of absolute paths to files in build/packages/*.yaml.

  Args:
    package_def_dir: path to build/packages dir to search for *.yaml.
    package_def_files: optional list of filenames to limit results to.

  Returns:
    List of absolute paths to *.yaml files under packages_dir.
  """
  # All existing package by default.
  if not package_def_files:
    return sorted(glob.glob(os.path.join(package_def_dir, '*.yaml')))
  paths = []
  for name in package_def_files:
    abs_path = os.path.join(package_def_dir, name)
    if not os.path.isfile(abs_path):
      raise BuildException('No such package definition file: %s' % name)
    paths.append(abs_path)
  return sorted(paths)


def read_yaml(py_venv, path):
  """Returns content of YAML file as python dict."""
  # YAML lib is in venv, not activated here. Go through hoops.
  oneliner = (
      'import json, sys, yaml; '
      'json.dump(yaml.safe_load(sys.stdin), sys.stdout)')
  if sys.platform == 'win32':
    python_venv_path = ('Scripts', 'python.exe')
  else:
    python_venv_path = ('bin', 'python')
  executable = os.path.join(py_venv, *python_venv_path)
  env = os.environ.copy()
  env.pop('PYTHONPATH', None)
  proc = subprocess.Popen(
      [executable, '-c', oneliner],
      executable=executable,
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      env=env)
  with open(path, 'r') as f:
    out, _ = proc.communicate(f.read())
  if proc.returncode:
    raise BuildException('Failed to parse YAML at %s' % path)
  return json.loads(out)


def should_process_on_builder(pkg_def_file, py_venv, builder):
  """Returns True if package should be processed by current CI builder."""
  if not builder:
    return True
  builders = read_yaml(py_venv, pkg_def_file).get('builders')
  return not builders or builder in builders


def get_package_vars():
  """Returns a dict with variables that describe the current environment.

  Variables can be referenced in the package definition YAML as
  ${variable_name}. It allows to reuse exact same definition file for similar
  packages (e.g. packages with same cross platform binary, but for different
  platforms).
  """
  # linux, mac or windows.
  platform_variant = {
    'darwin': 'mac',
    'linux2': 'linux',
    'win32': 'windows',
  }.get(sys.platform)
  if not platform_variant:
    raise ValueError('Unknown OS: %s' % sys.platform)

  if sys.platform == 'darwin':
    # platform.mac_ver()[0] is '10.9.5'.
    dist = platform.mac_ver()[0].split('.')
    os_ver = 'mac%s_%s' % (dist[0], dist[1])
  elif sys.platform == 'linux2':
    # platform.linux_distribution() is ('Ubuntu', '14.04', ...).
    dist = platform.linux_distribution()
    os_ver = '%s%s' % (dist[0].lower(), dist[1].replace('.', '_'))
  elif sys.platform == 'win32':
    # platform.version() is '6.1.7601'.
    dist = platform.version().split('.')
    os_ver = 'win%s_%s' % (dist[0], dist[1])
  else:
    raise ValueError('Unknown OS: %s' % sys.platform)

  # amd64, 386, etc.
  platform_arch = {
    'amd64': 'amd64',
    'i386': '386',
    'i686': '386',
    'x86': '386',
    'x86_64': 'amd64',
  }.get(platform.machine().lower())
  if not platform_arch:
    raise ValueError('Unknown machine arch: %s' % platform.machine())

  return {
    # e.g. '.exe' or ''.
    'exe_suffix': EXE_SUFFIX,
    # e.g. 'ubuntu14_04' or 'mac10_9' or 'win6_1'.
    'os_ver': os_ver,
    # e.g. 'linux-amd64'
    'platform': '%s-%s' % (platform_variant, platform_arch),
    # e.g. '27' (dots are not allowed in package names).
    'python_version': '%s%s' % sys.version_info[:2],
  }


def build_pkg(go_workspace, pkg_def_file, out_file, package_vars):
  """Invokes CIPD client to build a package.

  Args:
    go_workspace: path to 'infra/go' or 'infra_internal/go'.
    pkg_def_file: path to *.yaml file with package definition.
    out_file: where to store the built package.
    package_vars: dict with variables to pass as -pkg-var to cipd.

  Returns:
    {'package': <name>, 'instance_id': <sha1>}

  Raises:
    BuildException on error.
  """
  print_title('Building: %s' % os.path.basename(pkg_def_file))

  # Make sure not stale output remains.
  if os.path.isfile(out_file):
    os.remove(out_file)

  # Build the package.
  args = ['-pkg-def', pkg_def_file]
  for k, v in sorted(package_vars.items()):
    args.extend(['-pkg-var', '%s:%s' % (k, v)])
  args.extend(['-out', out_file])
  exit_code, json_output = run_cipd(go_workspace, 'pkg-build', args)
  if exit_code:
    print
    print >> sys.stderr, 'FAILED! ' * 10
    raise BuildException('Failed to build the CIPD package, see logs')

  # Expected result is {'package': 'name', 'instance_id': 'sha1'}
  info = json_output['result']
  print '%s %s' % (info['package'], info['instance_id'])
  return info


def upload_pkg(go_workspace, pkg_file, service_url, tags, service_account):
  """Uploads existing *.cipd file to the storage and tags it.

  Args:
    go_workspace: path to 'infra/go' or 'infra_internal/go'.
    pkg_file: path to *.cipd file to upload.
    service_url: URL of a package repository service.
    tags: a list of tags to attach to uploaded package instance.
    service_account: path to *.json file with service account to use.

  Returns:
    {'package': <name>, 'instance_id': <sha1>}

  Raises:
    UploadException on error.
  """
  print_title('Uploading: %s' % os.path.basename(pkg_file))

  args = ['-service-url', service_url]
  for tag in sorted(tags):
    args.extend(['-tag', tag])
  args.extend(['-ref', 'latest'])
  if service_account:
    args.extend(['-service-account-json', service_account])
  args.append(pkg_file)
  exit_code, json_output = run_cipd(go_workspace, 'pkg-register', args)
  if exit_code:
    print
    print >> sys.stderr, 'FAILED! ' * 10
    raise UploadException('Failed to upload the CIPD package, see logs')
  info = json_output['result']
  print '%s %s' % (info['package'], info['instance_id'])
  return info


def run(
    py_venv,
    go_workspace,
    build_callback,
    builder,
    package_def_dir,
    package_out_dir,
    package_def_files,
    build,
    upload,
    service_url,
    tags,
    service_account_json,
    json_output):
  """Rebuild python and Go universes and CIPD packages.

  Args:
    py_venv: path to 'infra/ENV' or 'infra_internal/ENV'.
    go_workspace: path to 'infra/go' or 'infra_internal/go'.
    build_callback: called to build binaries, virtual environment, etc.
    builder: name of CI buildbot builder that invoked the script.
    package_def_dir: path to build/packages dir to search for *.yaml.
    package_out_dir: where to put built packages.
    package_def_files: names of *.yaml files in package_def_dir or [] for all.
    build: False to skip building packages (valid only when upload==True).
    upload: True to also upload built packages, False just to build them.
    service_url: URL of a package repository service.
    tags: a list of tags to attach to uploaded package instances.
    service_account_json: path to *.json service account credential.
    json_output: path to *.json file to write info about built packages to.

  Returns:
    0 on success, 1 or error.
  """
  assert build or upload, 'Both build and upload are False, nothing to do'

  # Remove stale output so that test_packages.py do not test old files when
  # invoked without arguments.
  if build:
    for path in glob.glob(os.path.join(package_out_dir, '*.cipd')):
      os.remove(path)

  packages_to_build = [
    p for p in enumerate_packages_to_build(package_def_dir, package_def_files)
    if should_process_on_builder(p, py_venv, builder)
  ]

  print_title('Overview')
  print 'Service URL: %s' % service_url
  print
  if builder:
    print 'Package definition files to process on %s:' % builder
  else:
    print 'Package definition files to process:'
  for pkg_def_file in packages_to_build:
    print '  %s' % os.path.basename(pkg_def_file)
  if not packages_to_build:
    print '  <none>'
  print
  print 'Variables to pass to CIPD:'
  package_vars = get_package_vars()
  for k, v in sorted(package_vars.items()):
    print '  %s = %s' % (k, v)
  if tags:
    print
    print 'Tags to attach to uploaded packages:'
    for tag in sorted(tags):
      print '  %s' % tag
  if not packages_to_build:
    print
    print 'Nothing to do.'
    return 0

  # Build the world.
  if build:
    build_callback()

  # Package it.
  failed = []
  succeeded = []
  for pkg_def_file in packages_to_build:
    # path/name.yaml -> out/name.cipd.
    name = os.path.splitext(os.path.basename(pkg_def_file))[0]
    out_file = os.path.join(package_out_dir, name + '.cipd')
    try:
      info = None
      if build:
        info = build_pkg(go_workspace, pkg_def_file, out_file, package_vars)
      if upload:
        info = upload_pkg(
            go_workspace,
            out_file,
            service_url,
            tags,
            service_account_json)
      assert info is not None
      succeeded.append({'pkg_def_name': name, 'info': info})
    except (BuildException, UploadException) as e:
      failed.append({'pkg_def_name': name, 'error': str(e)})

  print_title('Summary')
  for d in failed:
    print 'FAILED %s, see log above' % d['pkg_def_name']
  for d in succeeded:
    print '%s %s' % (d['info']['package'], d['info']['instance_id'])

  if json_output:
    with open(json_output, 'w') as f:
      summary = {
        'failed': failed,
        'succeeded': succeeded,
        'tags': sorted(tags),
        'vars': package_vars,
      }
      json.dump(summary, f, sort_keys=True, indent=2, separators=(',', ': '))

  return 1 if failed else 0


def build_infra():
  """Builds infra.git multiverse."""
  # Python side.
  print_title('Making sure python virtual environment is fresh')
  run_python(
      script=os.path.join(ROOT, 'bootstrap', 'bootstrap.py'),
      args=[
        '--deps_file',
        os.path.join(ROOT, 'bootstrap', 'deps.pyl'),
        os.path.join(ROOT, 'ENV'),
      ])
  # Go side.
  build_go(os.path.join(ROOT, 'go'), [
    'infra/...',
    'github.com/luci/luci-go/client/...',
    'github.com/luci/luci-go/tools/...',
    ])


def main(
    args,
    build_callback=build_infra,
    py_venv=os.path.join(ROOT, 'ENV'),
    go_workspace=os.path.join(ROOT, 'go'),
    package_def_dir=os.path.join(ROOT, 'build', 'packages'),
    package_out_dir=os.path.join(ROOT, 'build', 'out')):
  parser = argparse.ArgumentParser(description='Builds infra CIPD packages')
  parser.add_argument(
      'yamls', metavar='YAML', type=str, nargs='*',
      help='name of a file in build/packages/* with the package definition')
  parser.add_argument(
      '--upload',  action='store_true', dest='upload', default=False,
      help='upload packages into the repository')
  parser.add_argument(
      '--no-rebuild',  action='store_false', dest='build', default=True,
      help='when used with --upload means upload existing *.cipd files')
  parser.add_argument(
      '--builder', metavar='NAME', type=str,
      help='Name of the CI buildbot builder that invokes this script.')
  parser.add_argument(
      '--service-url', metavar='URL', dest='service_url',
      default=PACKAGE_REPO_SERVICE,
      help='URL of the package repository service to use')
  parser.add_argument(
      '--service-account-json', metavar='PATH', dest='service_account_json',
      help='path to credentials for service account to use')
  parser.add_argument(
      '--json-output', metavar='PATH', dest='json_output',
      help='where to dump info about built package instances')
  parser.add_argument(
      '--tags', metavar='KEY:VALUE', type=str, dest='tags', nargs='*',
      help='tags to attach to uploaded package instances')
  args = parser.parse_args(args)
  if not args.build and not args.upload:
    parser.error('--no-rebuild doesn\'t make sense without --upload')
  return run(
      py_venv,
      go_workspace,
      build_callback,
      args.builder,
      package_def_dir,
      package_out_dir,
      [n + '.yaml' if not n.endswith('.yaml') else n for n in args.yamls],
      args.build,
      args.upload,
      args.service_url,
      args.tags or [],
      args.service_account_json,
      args.json_output)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
