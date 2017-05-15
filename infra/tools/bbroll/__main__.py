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
    'package_base', 'platform', 'infra_relpath'))

_PINS = collections.OrderedDict()
_PINS['kitchen'] = _PinConfig(
    package_base='infra/tools/luci/kitchen/',
    platform=True,
    infra_relpath='go/src/infra/tools/kitchen',
)
_PINS['vpython'] = _PinConfig(
    package_base='infra/tools/luci/vpython/',
    platform=True,
    infra_relpath='go/src/infra/tools/vpython',
)
_PINS['git'] = _PinConfig(
    package_base='infra/tools/git/',
    platform=True,
    infra_relpath='go/src/infra/tools/git',
)

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
  for pin_name, pin in _PINS.iteritems():
    canary_ver = get_version(pin, canary_template)
    prod_ver = get_version(pin, prod_template)
    if canary_ver == prod_ver:
      changes += ['%s version is the same' % (pin_name,)]
    else:
      changes += ['%s version %s -> %s\n\n%s\n' % (
          pin_name,
          prod_ver,
          canary_ver,
          get_changes(pin, prod_ver, canary_ver))]

  # Talk to user.
  print('rolling canary to prod')
  for change in changes:
    print(change)
  print(
      'canary was committed %s' %
      git('log', '-1', '--format=%cr', CANARY_TEMPLATE_FILENAME))
  # TODO(nodir): replace builder URLs with a monitoring link.
  print(
      'check builds in https://luci-milo.appspot.com/buildbucket/'
      'luci.chromium.try/LUCI%20linux_chromium_rel_ng')
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
  pin_name = args.pin
  pin = _PINS[pin_name]

  # Read current version.
  with open(CANARY_TEMPLATE_FILENAME) as f:
    contents = f.read()
  template = json.loads(contents)
  cur_ver = get_version(pin, template)
  if not cur_ver:
    print('could not find %s pin in the template!' % (pin_name,))
    return 1

  # Read new version.
  new_rev = args.git_revision
  if new_rev:
    err = validate_git_revision(new_rev, pin)
    if err:
      print('git revision %s is bad. CIPD output:' % new_rev)
      print(err)
      return 1
  else:
    print('looking for built %s packages for recent commits...' % (pin_name,))
    new_rev = get_latest_package_git_revision(pin)
    if not new_rev:
      print('could not find a good candidate')
      return 1
    print('latest %s package version is git_revision:%s' % (pin_name, new_rev))

  new_ver = 'git_revision:' + new_rev
  if cur_ver == new_ver:
    print 'new version matches the current one'
    return 1

  # Read changes.
  changes = get_changes(pin, cur_ver, new_ver)
  if not changes:
    print 'no changes detected between %s and %s' % (cur_ver, new_ver)
    return 1

  # Talk to the user.
  print('rolling canary %s version %s -> %s' % (pin_name, cur_ver, new_ver))
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

  message = 'does %s at TOT look good? [N/y]: ' % (pin_name,)
  if raw_input(message).lower() != 'y':
    print('please fix it first')
    return 1

  # Update the template.
  # Minimize the template diff by using regex.
  # Assume package name goes before version.
  pattern = (
    r'(package_name": "%s[^}]+version": ")[^"]+(")' %
    re.escape(get_package_name(pin)))
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
         'pin_name': pin_name,
         'new_rev_short': new_rev[:9],
         'new_rev': new_rev,
         'changes': changes,
      }
  )
  return 0


def get_package_name(pin, platform=None):
  """Returns the CIPD package name for a pin."""
  name = pin.package_base
  if pin.platform:
    name += platform or '${platform}'
  return name


def get_version(pin, template):
  """Retrieves version of the pin in the task template."""
  package_name = get_package_name(pin)
  for pkg in template['properties']['cipd_input']['packages']:
    if pkg['package_name'] == package_name:
      return pkg['version']
  return None


def get_latest_package_git_revision(pin):
  """Returns a value of git_revision tag of the latest pin packages."""
  git('-C', INFRA_REPO_ROOT, 'fetch', 'origin')
  print  # Print empty line after git-fetch output

  # Read up to 100 commits. It is unlikely that we will have a latest set of
  # CIPD packages further than 100 commits ago.
  log = git('-C', INFRA_REPO_ROOT, 'log', '-100', '--format=%H')
  for commit in log.splitlines():
    if not validate_git_revision(commit, pin):
      return commit
  return None


def get_changes(pin, ver1, ver2):
  """Returns a description of changes between two versions.

  If there were no changes, returns None.
  """
  if not ver1 or not ver2:
    return INFRA_CHANGES_UNKNOWN
  prefix = 'git_revision:'
  if not ver1.startswith(prefix) or not ver2.startswith(prefix):
    return INFRA_CHANGES_UNKNOWN

  rev1, rev2 = ver1[len(prefix):], ver2[len(prefix):]
  args = [
    'log',
    '--date=short',
    '--no-merges',
    '--format=%ad %ae %s',
    '%s..%s' % (rev1, rev2),
    # Here we assume that binary contents changes when files in these
    # directories change.
    # This avoids most of unrelated changes in the change log.
    'DEPS',
    'go/deps.lock',
  ]
  if pin.infra_relpath:
    args += [pin.infra_relpath]

  changes = git('-C', INFRA_REPO_ROOT, *args)
  if not changes:
    return None
  return '$ git %s\n%s' % (' '.join(args), changes)


@contextlib.contextmanager
def tempdir():
  """Creates and returns a temporary directory, deleting it on exit."""
  path = tempfile.mkdtemp(suffix='bbroll')
  try:
    yield path
  finally:
    shutil.rmtree(path)


def validate_git_revision(git_revision, pin):
  """
  Returns a non-empty string of error text if git_revision is invalid,
  otherwise returns None.
  """

  with tempdir() as tdir:
    resolved_path = os.path.join(tdir, 'resolve.json')

    # Since this process will return a non-zero exit code if the resolution
    # was incomplete, we determine correctness by examining the output JSON,
    # not the exit code.
    cmdline = [
      'cipd',
      'resolve', pin.package_base,
      '-version', 'git_revision:' + git_revision,
      '-json-output', resolved_path,
    ]
    proc = subprocess.Popen(cmdline, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    stdout, _ = proc.communicate()

    try:
      with open(resolved_path, 'r') as fd:
        resolved = json.load(fd)
    except IOError:
      return 'CIPD did not produce a JSON:\n%s' % (stdout,)

  resolved = resolved.get('result', {}).get('') or []
  resolved = set(entry['package'] for entry in resolved
                 if entry.get('pin'))
  packages = set([pin.package_base + plat for plat in VERIFY_PLATFORMS]
                 if pin.platform else [pin.package_base])
  missing = packages.difference(resolved)
  if missing:
    return 'unresolved packages: %s' % (', '.join(sorted(missing)),)
  return ''


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
      '--git-revision',
      help='git revision of the pin. Defaults to latest.')
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
