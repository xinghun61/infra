# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Updates buildbucket's swarming task templates.

To roll production template:
  cd infradata/config/configs/cr-buildbucket
  cit bbroll prod

To roll canary kitchen to the latest:
  cd infradata/config/configs/cr-buildbucket
  cit bbroll canary kitchen
"""

import argparse
import collections
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

THIS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
INFRA_REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..', '..', '..'))

PROD_TEMPLATE_FILENAME = 'swarming_task_template.json'
CANARY_TEMPLATE_FILENAME = 'swarming_task_template_canary.json'

_PinConfig = collections.namedtuple('_PinConfig', (
  # name (str) - The name of the pin; this is how humans will refer to this pin
  # on the command line.
  'name',

  # package_base (str) - The base CIPD package name.
  'package_base',

  # infra_relpath (str|None) -
  #   If this is a string, this is a relative path to the base of the infra.git
  #     repo, and will be used to generate a git log for the commit message.
  #   If this is None, this pin is just treated as a sourceless CIPD package.
  #     The CIPD version will change, but there won't be any git log.
  'infra_relpath',

  # platform (bool)    - If True, appends "${platform}" to the package_base.
  'platform'))


def cipd_output(args):
  """Runs cipd with the given arguments, and returns the -json-output from the
  command.

  Returns (json_output, error_msg) - If json_output is None, error_msg is the
  error text from running the command.
  """
  with tempdir() as tdir:
    data_file = os.path.join(tdir, 'data.json')

    # Since this process will return a non-zero exit code if the resolution
    # was incomplete, we determine correctness by examining the output JSON,
    # not the exit code.
    proc = subprocess.Popen(['cipd']+args+['-json-output', data_file],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, _ = proc.communicate()

    try:
      with open(data_file, 'r') as fd:
        return json.load(fd), None
    except IOError:
      return None, 'CIPD did not produce a JSON:\n%s' % (stdout,)


# NOTE: This should be kept in sync with "cipd_all_targets" from:
# https://chromium.googlesource.com/chromium/tools/build/+/master/scripts/slave/infra_platform.py
#
# Current version was cut from: df3fabbcf94016a8a37b74014bb4604e55faa577
VERIFY_PLATFORMS = set('%s-%s' % parts for parts in (
    ('linux', '386'),
    ('linux', 'amd64'),
    ('linux', 'arm64'),
    ('linux', 'armv6l'),
    ('linux', 'mips64'),
    ('mac', 'amd64'),
    ('windows', '386'),
    ('windows', 'amd64'),
))


class PinConfig(_PinConfig):
  def cipd_version(self, raw_version):
    """Converts from a raw version to a full CIPD tag, depending on whether this
    pin is an infra.git pin or not."""
    return self.cipd_version_prefix + raw_version

  @property
  def cipd_version_prefix(self):
    if self.is_infra_git:
      return 'git_revision:'
    return 'version:'

  @property
  def is_infra_git(self):
    return self.infra_relpath is not None

  @property
  def cipd_package(self):
    """Returns the CIPD package name for this pin."""
    if self.platform:
      return self.package_base + '${platform}'
    return self.package_base

  def raw_version(self, cipd_version):
    """Converts from a full CIPD tag back to a raw version, depending on whether
    this is an infra.git pin or not."""
    assert cipd_version.startswith(self.cipd_version_prefix), cipd_version
    return cipd_version.split(':', 1)[1]

  def get_latest_version(self):
    """Returns a raw_version of the latest pin packages.

    Returns None if that couldn't be determined.
    """
    if self.is_infra_git:
      print('looking for built %s packages for recent commits...'
            % (self.name,))
      git('-C', INFRA_REPO_ROOT, 'fetch', 'origin')
      print  # Print empty line after git-fetch output

      # Read up to 100 commits. It is unlikely that we will have a latest set of
      # CIPD packages further than 100 commits ago.
      log = git('-C', INFRA_REPO_ROOT, 'log', '-100', '--format=%H')
      for commit in log.splitlines():
        if not self.validate_version(commit):
          return commit
    else:
      print('getting latest cipd version for %s...' % (self.name,))
      description, error_msg = cipd_output([
        'describe', self.cipd_package, '-version', 'latest',
      ])
      if description is None:
        print error_msg
        return None
      tags = description.get('result', {}).get('tags', [])
      for tag in tags:
        name, val = tag['tag'].split(':')
        if name == 'version':
          return val
      print('unknown tags: %r', tags)

  def validate_version(self, raw_version):
    """returns a non-empty string of error text if the cipd version is invalid,
    otherwise returns none.

    `raw_version` is the input from the --version argument. if the pin is an
    infra repo pin, then this should look like a git hash (e.g. `deadbeef...`).
    if the pin is for a non-infra repo tool (like git or python), this will look
    like a version (e.g. `2.14.1.chromium11`). the function will prepend the
    correct cipd tag name (i.e. git_revision or version).
    """
    resolved, error_msg = cipd_output([
      'resolve', self.package_base,
      '-version', self.cipd_version(raw_version),
    ])
    if resolved is None:
      return error_msg

    resolved = resolved.get('result', {}).get('') or []
    resolved = set(entry['package'] for entry in resolved
                   if entry.get('pin'))
    packages = set([self.package_base + plat for plat in VERIFY_PLATFORMS]
                   if self.platform else [self.package_base])
    missing = packages.difference(resolved)
    if missing:
      return 'unresolved packages: %s' % (', '.join(sorted(missing)),)
    return ''

  def get_changes(self, ver1, ver2):
    """Returns a description of changes between two raw versions.

    If there were no changes, returns None.
    """
    if not ver1 or not ver2:
      return INFRA_CHANGES_UNKNOWN

    if not self.is_infra_git:  # No git history for this pin.
      return ''

    args = [
      'log',
      '--date=short',
      '--no-merges',
      '--format=%ad %ae %s',
      '%s..%s' % (ver1, ver2),
      # Here we assume that binary contents changes when files in these
      # directories change.
      # This avoids most of unrelated changes in the change log.
      'DEPS',
      'go/deps.lock',
    ]
    if self.infra_relpath:  # non-empty
      args += [self.infra_relpath]

    changes = git('-C', INFRA_REPO_ROOT, *args)
    if not changes:
      return None
    return '$ git %s\n%s' % (' '.join(args), changes)

  def get_version(self, template):
    """Retrieves raw version of the pin in the task template."""
    package_name = self.cipd_package
    for pkg in template['properties']['cipd_input']['packages']:
      if pkg['package_name'] == package_name:
        return self.raw_version(pkg['version'])
    return None


_PINS = collections.OrderedDict()
def _add_pin(name, package_base, infra_relpath=None, platform=True):
  _PINS[name] = PinConfig(name, package_base, infra_relpath, platform)

_add_pin('kitchen',
         'infra/tools/luci/kitchen/', 'go/src/infra/tools/kitchen')
_add_pin('vpython',
         'infra/tools/luci/vpython/', 'go/src/infra/tools/vpython')
_add_pin('git',
         'infra/git/')
_add_pin('git-wrapper',
         'infra/tools/git/', 'go/src/infra/tools/git')
_add_pin('python',
         'infra/python/cpython/')

INFRA_CHANGES_UNKNOWN = 'infra.git changes are unknown'

# Most of this code expects CWD to be the git directory containing
# swarmbucket template files.


def roll_prod(_args):
  """Copies canary template to prod."""
  # Read templates.
  with open(CANARY_TEMPLATE_FILENAME) as f:
    canary_template_contents = f.read()
  with open(PROD_TEMPLATE_FILENAME) as f:
    prod_template_contents = f.read()
  if canary_template_contents == prod_template_contents:
    print('prod and canary template files are identical')
    return 1

  canary_template = json.loads(canary_template_contents)
  prod_template = json.loads(prod_template_contents)

  changes = []
  sames = []
  for pin in _PINS.itervalues():
    canary_ver = pin.get_version(canary_template)
    prod_ver = pin.get_version(prod_template)
    if canary_ver == prod_ver:
      sames.append(pin.name)
    elif pin.is_infra_git:
      changes += ['%s version %s -> %s\n\n%s\n' % (
          pin.name,
          prod_ver,
          canary_ver,
          pin.get_changes(prod_ver, canary_ver))]
    else:
      changes += ['%s version %s -> %s' % (
          pin.name,
          prod_ver,
          canary_ver)]

  if sames:
    changes += ['', 'unchanged: %s' % (', '.join(sames),), '']

  # Talk to user.
  print('rolling canary to prod')
  for change in changes:
    print(change)
  print(
      'canary was committed %s' %
      git('log', '-1', '--format=%cr', CANARY_TEMPLATE_FILENAME))
  print(
      'check builds in https://luci-milo.appspot.com/buildbucket/'
      'luci.chromium.try/linux_chromium_rel_ng')
  print('check https://goto.google.com/buildbucket-canary-health')
  if raw_input('does canary look good? [N/y]: ').lower() != 'y':
    print('please fix it first')
    return 1

  # Update template and save changes.
  with open(PROD_TEMPLATE_FILENAME, 'w') as f:
    f.write(canary_template_contents)

  cur_commit = git('rev-parse', 'HEAD')
  make_commit(
      ('cr-buildbucket: roll prod template\n'
       '\n'
       'Promote current canary template @ %s to production\n'
       '\n'
       '%s') % (cur_commit, '\n'.join(changes)))
  return 0


def roll_canary(args):
  """Changes pin version in the canary template."""
  pin = _PINS[args.pin]

  # Read current version.
  with open(CANARY_TEMPLATE_FILENAME) as f:
    contents = f.read()
  template = json.loads(contents)
  cur_rev = pin.get_version(template)
  if not cur_rev:
    print('could not find %s pin in the template!' % (pin.name,))
    return 1

  # Read new version.
  new_rev = args.version
  if new_rev:
    err = pin.validate_version(new_rev)
    if err:
      print('version %s is bad. CIPD output:' % new_rev)
      print(err)
      return 1
  else:
    new_rev = pin.get_latest_version()
    if not new_rev:
      print('could not find a good candidate')
      return 1
    print('latest %s package version is %s' % (
      pin.name, pin.cipd_version(new_rev)))

  if cur_rev == new_rev:
    print 'new version matches the current one'
    return 1

  # Read changes.
  changes = pin.get_changes(cur_rev, new_rev)
  if changes is None:
    print 'no changes detected between %s and %s' % (cur_rev, new_rev)
    return 1

  # Talk to the user.
  cur_ver, new_ver = pin.cipd_version(cur_rev), pin.cipd_version(new_rev)
  print('rolling canary %s version %s -> %s' % (pin.name, cur_ver, new_ver))
  print
  print changes
  print
  # TODO(nodir): replace builder URLs with a monitoring link.
  print(
      'check builds in https://luci-milo-dev.appspot.com/buildbucket/'
      'luci.infra.continuous/infra-continuous-win-64')
  print(
      'check builds in https://luci-milo-dev.appspot.com/buildbucket/'
      'luci.infra.continuous/infra-continuous-trusty-64')

  message = 'does %s at TOT look good? [N/y]: ' % (pin.name,)
  if raw_input(message).lower() != 'y':
    print('please fix it first')
    return 1

  # Update the template.
  # Minimize the template diff by using regex.
  # Assume package name goes before version.
  pattern = (
    r'(package_name": "%s[^}]+version": ")[^"]+(")' %
    re.escape(pin.cipd_package))
  match_count = len(re.findall(pattern, contents))
  if match_count != 1:
    print(
      'expected to find exactly 1 match of pattern %r, found %d!' %
      (pattern, match_count))
    print('please fix the template or me')
    return 1

  updated_contents = re.sub(pattern, r'\1%s\2' % new_ver, contents)
  if contents == updated_contents:
    print('internal failure: did not change the template')
    return 1

  # Save changes.
  with open(CANARY_TEMPLATE_FILENAME, 'w') as f:
    f.write(updated_contents)

  make_commit(
      ('cr-buildbucket: roll canary %(pin_name)s @ %(new_rev_short)s\n'
       '\n'
       'Roll canary %(pin_name)s to %(new_rev)s\n'
       '\n'
       '%(pin_name)s change log:\n'
       '%(changes)s') % {
         'pin_name': pin.name,
         'new_rev_short': new_rev[:9] if pin.is_infra_git else new_rev,
         'new_rev': new_rev,
         'changes': changes,
      }
  )
  return 0


@contextlib.contextmanager
def tempdir():
  """Creates and returns a temporary directory, deleting it on exit."""
  path = tempfile.mkdtemp(suffix='bbroll')
  try:
    yield path
  finally:
    shutil.rmtree(path)


def make_commit(commit_message):
  """Makes a commit with a roll."""
  commit_message += '\n\nThis commit was prepared by `cit bbroll` tool'
  git('commit', '-a', '-m', commit_message)
  subprocess.check_call(['git', 'show'])
  print
  print('the commit is prepared; please send it out for review')


def git(*args):
  """Calls git and returns output without last \n."""
  cmdline = ['git'] + list(args)
  return subprocess.check_output(cmdline).rstrip('\n')


def main(argv):
  parser = argparse.ArgumentParser('Swarmbucket template roller')
  parser.add_argument(
      '-C',
      dest='config_dir',
      help='Path to the directory containing buildbucket service configs',
      default='.',
  )
  subparsers = parser.add_subparsers(dest='subcommand')

  prod = subparsers.add_parser('prod', help='Roll swarming_task_template.json')
  prod.set_defaults(func=roll_prod)

  canary = subparsers.add_parser(
      'canary',
      help='Roll swarming_task_template_canary.json')
  canary.add_argument(
      'pin',
      choices=_PINS.keys(),
      help='The name of the pin to roll.')
  canary.add_argument(
      '--version',
      help='git revision or cipd version of the pin. Defaults to latest.')
  canary.set_defaults(func=roll_canary)

  args = parser.parse_args(argv)

  if args.config_dir != '.':
    os.chdir(args.config_dir)
    print 'entering %s' % args.config_dir

  if not os.path.isfile(CANARY_TEMPLATE_FILENAME):
    print(
        './%s is not found. Are you running this in the config directory?' %
        CANARY_TEMPLATE_FILENAME)
    return 1

  # Check current directory:
  # - must be a git repo
  # - the work tree must be clean
  # - HEAD must match remote origin/master
  if git('status', '-s'):
    print '%r' % git('status', '-s')
    print('The work tree in is dirty!')
    return 1
  git('fetch', 'origin', 'master')
  print  # Print empty line after git-fetch output
  expected, actual = (
      git('rev-parse', 'FETCH_HEAD', 'HEAD').splitlines())
  if expected != actual:
    print('HEAD does not match origin/master (%s)!' % expected)
    return 1

  return args.func(args)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
