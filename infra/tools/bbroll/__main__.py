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
import json
import os
import re
import subprocess
import sys

THIS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
INFRA_REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..', '..', '..'))

PROD_TEMPLATE_FILENAME = 'swarming_task_template.json'
CANARY_TEMPLATE_FILENAME = 'swarming_task_template_canary.json'

KITCHEN_CIPD_PACKAGE_PREFIX = 'infra/tools/luci/kitchen/'
KITCHEN_PIN_NAME = KITCHEN_CIPD_PACKAGE_PREFIX + '${platform}'
INFRA_CHANGES_UNKNOWN = 'infra.git changes are unknown'

FNULL = open(os.devnull, 'w')

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

  canary_kitchen_ver = get_kitchen_version(json.loads(canary_template_contents))
  prod_kitchen_ver = get_kitchen_version(json.loads(prod_template_contents))
  if canary_kitchen_ver == prod_kitchen_ver:
    kitchen_changes = 'kitchen version is the same'
  else:
    kitchen_changes = 'kitchen version %s -> %s\n\n%s\n' % (
        prod_kitchen_ver,
        canary_kitchen_ver,
        get_infra_changes(prod_kitchen_ver, canary_kitchen_ver))

  # Talk to user.
  print('rolling canary to prod')
  print(kitchen_changes)
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
       '%s') % (cur_commit, kitchen_changes))
  return 0


def roll_canary_kitchen(args):
  """Changes kitchen version in the canary template."""
  # Read current version.
  with open(CANARY_TEMPLATE_FILENAME) as f:
    contents = f.read()
  template = json.loads(contents)
  cur_ver = get_kitchen_version(template)
  if not cur_ver:
    print('could not find kitchen pin in the template!')
    return 1

  # Read new version.
  new_rev = args.git_revision
  if new_rev:
    err = validate_kitchen_git_revision(new_rev)
    if err:
      print('git revision %s is bad. CIPD output:' % new_rev)
      print(err)
      return 1
  else:
    print('looking for built kitchen packages for recent commits...')
    new_rev = get_latest_kitchen_package_git_revision()
    if not new_rev:
      print('could not find a good candidate')
      return 1
    print('latest kitchen package version is git_revision:%s' % new_rev)

  new_ver = 'git_revision:' + new_rev
  if cur_ver == new_ver:
    print 'new version matches the current one'
    return 1

  # Read changes.
  kitchen_changes = get_infra_changes(cur_ver, new_ver)
  assert kitchen_changes

  # Talk to the user.
  print('rolling canary kitchen version %s -> %s' % (cur_ver, new_ver))
  print
  print kitchen_changes
  print
  # TODO(nodir): replace builder URLs with a monitoring link.
  print(
      'check builds in https://luci-milo-dev.appspot.com/buildbucket/'
      'luci.infra.continuous/infra-continuous-win-64')
  print(
      'check builds in https://luci-milo-dev.appspot.com/buildbucket/'
      'luci.infra.continuous/infra-continuous-trusty-64')
  if raw_input('does kitchen at TOT look good? [N/y]: ').lower() != 'y':
    print('please fix it first')
    return 1

  # Update the template.
  # Minimize the template diff by using regex.
  # Assume package name goes before version.
  pattern = (
    r'(package_name": "%s[^}]+version": ")[^"]+(")' %
    re.escape(KITCHEN_PIN_NAME))
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
      ('cr-buildbucket: roll canary kitchen @ %s\n'
       '\n'
       'Roll canary kitchen to %s\n'
       '\n'
       'Kitchen change log:\n'
       '%s') % (new_rev[:9], new_rev, kitchen_changes)
  )
  return 0


def get_kitchen_version(template):
  """Retrieves version of the kitchen pin in the task template."""
  for pkg in template['properties']['cipd_input']['packages']:
    if pkg['package_name'] == KITCHEN_PIN_NAME:
      return pkg['version']
  return None


def get_latest_kitchen_package_git_revision():
  """Returns a value of git_revision tag of the latest kitchen packages."""
  git('-C', INFRA_REPO_ROOT, 'fetch', 'origin')
  # Read up to 100 commits. It is unlikely that we will have a latest set of
  # CIPD packages further than 100 commits ago.
  log = git('-C', INFRA_REPO_ROOT, 'log', '-100', '--format=%H')
  for commit in log.splitlines():
    err = validate_kitchen_git_revision(commit)
    if not err:
      return commit
  return None


def get_infra_changes(ver1, ver2):
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
  ]
  changes = git('-C', INFRA_REPO_ROOT, *args)
  if not changes:
    return None
  return '$ git %s\n%s' % (' '.join(args), changes)


def validate_kitchen_git_revision(git_revision):
  """Returns CIPD output if git_revision is invalid, otherwise returns ''."""
  try:
    cmdline = [
      'cipd',
      'resolve', KITCHEN_CIPD_PACKAGE_PREFIX,
      '-version', 'git_revision:' + git_revision,
    ]
    subprocess.check_call(cmdline, stdout=FNULL, stderr=FNULL)
    return ''
  except subprocess.CalledProcessError as ex:
    return ex.output


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
  canary_kitchen = canary.add_subparsers().add_parser(
      'kitchen',
      help='Roll kitchen version in swarming_task_template_canary.json')
  canary_kitchen.add_argument(
      '--git-revision',
      help='git revision of kitchen. Defaults to latest.')
  canary_kitchen.set_defaults(func=roll_canary_kitchen)

  args = parser.parse_args(argv)

  if args.config_dir != '.':
    os.chdir(args.config_dir)
    print 'entering %s' % args.config_dir

  # Check current directory:
  # - must be a git repo
  # - the work tree must be clean
  # - HEAD must match remote origin/master
  if git('status', '-s'):
    print '%r' % git('status', '-s')
    print('The work tree in is dirty!')
    return 1
  git('fetch', 'origin', 'master')
  expected, actual = (
      git('rev-parse', 'FETCH_HEAD', 'HEAD').splitlines())
  if expected != actual:
    print('HEAD does not match origin/master (%s)!' % expected)
    return 1

  return args.func(args)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
