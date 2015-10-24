# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import distutils.util
import logging
import os
import re
import tempfile

from infra.libs.gitiles import gitiles
from infra.tools.cros_pin import checkout, execute, pinfile
from infra.tools.cros_pin.logger import LOGGER

# Ths path of the Chromite repository.
CHROMITE_REPOSITORY = 'https://chromium.googlesource.com/chromiumos/chromite'

# The number of stable release branches to build in addition to the beta
# branch.
DEFAULT_STABLE_COUNT = 2

# Regular expression to match release branch names.
RELEASE_RE = re.compile(r'release-R(\d+)-.*')


def add_argparse_options(parser):
  parser.add_argument('-d', '--dry-run',
      action='store_true',
      help="Stop short of submitting the CLs.")
  parser.add_argument('-n', '--no-verify',
      action='store_true',
      help="Don't check that the specified pin exists.")
  parser.add_argument('-C', '--checkout-path', metavar='PATH',
      help="If specified, the checkout at PATH will be used instead of a "
           "temporary one. If PATH does not exist, it will be created, and "
           "the checkout will not be cleaned up. This is intended for "
           "debugging.")
  parser.add_argument('--chromite-repository', default=CHROMITE_REPOSITORY,
      help="The Chromite repository to query (default is %(default)s).")
  parser.add_argument('-b', '--bug',
      help="Cite this BUG when creating CLs.")
  parser.add_argument('-r', '--reviewer',
      action='append', default=[],
      help="Add this reviewer to the uploaded CL. If no reviewers are "
           "specified, someone from the OWNERS file will be chosen.")
  parser.add_argument('-m', '--commit-message',
      help="Use this commit message instead of an auto-generated one.")
  parser.add_argument('--no-commit', dest='commit', action='store_false',
      help="Don't automatically mark generated CLs for commit queue.")

  subparsers = parser.add_subparsers(help='CrOS Pin Subcommands')

  # Subcommand: update
  subp = subparsers.add_parser('update',
      help=subcommand_update.__doc__)
  subp.add_argument('-t', '--target',
      choices=["existing", "external", "internal", "both"], default='existing',
      help="Specifies which pin repositories to update. 'existing' (default) "
           "updates all existing named pins. 'external', 'internal', and "
           "'both' indicate that the pin should be updated in the external "
           "and/or internal pin repositories, and should be added if not "
           "currently present. Use these with caution!")
  subp.add_argument('name',
      help="The name of the pin to update.")
  subp.add_argument('version', nargs='?',
      help="The new commit hash for the pin. If empty, probe for tip-of-tree "
           "of the branch sharing the pin's name.")
  subp.set_defaults(func=subcommand_update)

  # Subcommand: add-release
  subp = subparsers.add_parser('add-release',
      help=subcommand_add_release.__doc__)
  subp.add_argument('--stable-count', metavar='COUNT',
      type=int, default=DEFAULT_STABLE_COUNT,
      help="Specifies the number of stable branches to preserve. (default is "
           "%(default)s). The youngest COUNT release branch pins beyond the "
           "newest will be preserved as stable branches, and any additional "
           "release branches will be removed from the pins.")
  subp.add_argument('branch',
      help='The name of the release branch. Must begin with "release-R#".')
  subp.add_argument('version', nargs='?',
      help="The commit hash for the branch. If empty, use the branch's "
           "tip-of-tree commit.")
  subp.set_defaults(func=subcommand_add_release)


def checkout_for_args(args):
  """A contextmanager that supplies the Checkout configured in args.

  The Checkout's teardown() method will be invoked on cleanup.

  Args:
    args (argparse.Options): Parsed option list.
  """
  return checkout.Checkout.use(
      path=args.checkout_path)

def pinfile_editor_from_args(args, c):
  return pinfile.Editor(
      c.path,
      gitiles.Repository(args.chromite_repository),
      validate=not args.no_verify)


def logging_verbosity():
  count = 0
  if LOGGER.level >= logging.INFO:
    count += 1
  if LOGGER.level >= logging.DEBUG:
    count += 1
  return ['-v'] * count


def get_release_version(v):
  m = RELEASE_RE.match(v)
  if not m:
    return None
  return int(m.group(1))


def subcommand_update(args):
  """Update a single Chromite pin."""
  create = (args.target != 'existing')
  target_pins = []
  if args.target in ('external', 'both', 'existing'):
    target_pins.append(pinfile.EXTERNAL)
  if args.target in ('internal', 'both', 'existing'):
    target_pins.append(pinfile.INTERNAL)

  with checkout_for_args(args) as c:
    pfe = pinfile_editor_from_args(args, c)
    tracker = UpdateTracker.from_args(args, c)

    for pin in target_pins:
      logging.debug('Updating target pin [%s]', pin)

      # Update 
      pf = pfe.load(pin)
      update = pf.update(args.name, version=args.version, create=create)
      if not update:
        LOGGER.debug('Did not update pins for [%s]', pin)
        continue
      tracker.add(pin, update)

    LOGGER.debug('Updated pin set: %s', update)
    if not tracker:
      LOGGER.error('No pins were updated.')
      return 1

    # Regenerate slave pools for affected masters.
    tracker.update()
    for i in tracker.issues:
      LOGGER.warning('Created Issue: %s', i)
  return 0


def subcommand_add_release(args):
  """Add a new release branch to the list of pins."""
  with checkout_for_args(args) as c:
    pfe = pinfile_editor_from_args(args, c)
    tracker = UpdateTracker.from_args(args, c)

    add_release = (get_release_version(args.branch), args.branch)
    if add_release[0] is None:
      raise ValueError("Invalid release branch: [%s]" % (args.branch,))

    # Build a list of releases and their versions.
    pf = pfe.load(pinfile.INTERNAL)
    releases = [add_release]
    for name, _ in pf.iterpins():
      v = get_release_version(name)
      if v == add_release[0]:
        LOGGER.error('Release [%s] (%d) is already pinned.',
                     add_release[1], add_release[0])
        return 1

      if v is not None:
        releases.append((v, name))
    releases.sort(reverse=True)

    # Shave off the top [stable_count+1] releases.
    count = args.stable_count+1
    releases, deleted = releases[:count], releases[count:]
    if add_release not in releases:
      raise ValueError("Updated releases do not include added (%s):\n%s" % (
          add_release[1], '\n'.join(r[1] for r in releases)))

    # Set the new releases.
    tracker.add(pinfile.INTERNAL, pf.update(add_release[1], create=True))
    for _, r in deleted:
      tracker.add(pinfile.INTERNAL, pf.remove(r))

    if not tracker:
      LOGGER.error('No pins were updated.')
      return 1

    # Regenerate slave pools for affected masters.
    tracker.update()
    LOGGER.warning('Created issues:\n%s', '\n'.join(tracker.issues))
  return 0


class SlavePoolUpdateError(Exception):
  pass


class UpdateTracker(object):

  RUNIT_PY = ('build', 'scripts', 'tools', 'runit.py')
  SLAVE_ALLOC_UPDATE = ('build', 'scripts', 'tools', 'slave_alloc_update.py')

  RE_ISSUE_CREATED = re.compile(r'^Issue created. URL: (.+)$')

  def __init__(self, c, cq=False, bug=None, reviewers=None, dry_run=True):
    self._c = c
    self._cq = cq
    self._bug = bug
    self._reviewers = reviewers
    self._dry_run = dry_run

    self._updated = {}
    self._issues = set()

  @classmethod
  def from_args(cls, args, c):
    return cls(
        c,
        cq=args.commit,
        bug=args.bug,
        reviewers=args.reviewer,
        dry_run=args.dry_run)

  def __nonzero__(self):
    return bool(self._updated)

  @property
  def issues(self):
    return sorted(self._issues)

  def add(self, pin, update):
    self._updated.setdefault(pin, {})[update.name] = (update.fr, update.to)

  def update(self):
    LOGGER.info('Updating repositories: %s', self._updated)
    affected_masters = set()
    for pin in self._updated.iterkeys():
      affected_masters.update(pin.masters)

    failed_slave_pool_masters = []
    for m in sorted(affected_masters):
      try:
        self._regenerate_slave_pool(m)
      except SlavePoolUpdateError:
        failed_slave_pool_masters.append(m)
    if failed_slave_pool_masters:
      LOGGER.error('Failed to update slave pools for %s. You may need to '
                   'add additional slaves the pool(s).',
                   failed_slave_pool_masters)
      raise SlavePoolUpdateError("Failed to update slave pools.")

    # Upload CLs for the affected repositories.
    for pin, updates in self._updated.iteritems():
      self._upload_patch(
          self._c.subpath(*pin.base),
          self._generate_commit_message(updates))

  def _regenerate_slave_pool(self, master):
    LOGGER.debug('Regenerating slave pool for: %s', master)
    cmd = [
        os.path.join(*self.RUNIT_PY),
        os.path.join(*self.SLAVE_ALLOC_UPDATE),
    ]
    cmd += logging_verbosity()
    cmd.append(master)

    rv, stdout = execute.call(cmd, cwd=self._c.path)
    if rv != 0:
      LOGGER.exception('Failed to update slaves for master [%s] (%d):\n%s',
                       master, rv, stdout)
      raise SlavePoolUpdateError()


  def _upload_patch(self, repo_path, commit_msg):
    # Check if the Git repository actually has changes.
    diff_args = ['git', 'diff', '--no-ext-diff', '--exit-code']
    if not LOGGER.isEnabledFor(logging.DEBUG):
      diff_args.append('--quiet')
    rv, diff = execute.call(diff_args, cwd=repo_path)
    LOGGER.debug('Diff for [%s]:\n%s', repo_path, diff)
    if rv == 0:
      LOGGER.warning('No changes in repository; refusing to commit.')
      return

    LOGGER.debug('Creating commit in [%s] with message:\n%s',
                 repo_path, commit_msg)
    execute.check_call(
        ['git', 'checkout', '-b', '_cros_pin'],
        cwd=repo_path)
    execute.check_call(
        ['git', 'commit', '--all', '--message', commit_msg],
        cwd=repo_path)

    LOGGER.debug('Uploading CL!')
    args = [
        'git', 'cl', 'upload',
        '--bypass-hooks', # The CQ will take care of them!
        '-t', commit_msg,
        '-m', 'Auto-generated by `%s`' % (__name__,),
        '-f',
        ]
    if self._cq:
      print 'Commit? [Y/n]:',
      input_string = raw_input()
      if input_string != '' and not distutils.util.strtobool(input_string):
        LOGGER.info('User opted not to commit; aborting.')
        return
      args.append('--use-commit-queue')
    if not self._reviewers:
      args.append('--tbr-owners')

    output = execute.check_call(args, cwd=repo_path, dry_run=self._dry_run)
    issue = None
    for line in output.splitlines():
      match = self.RE_ISSUE_CREATED.match(line)
      if match:
        issue = match.group(1)
        LOGGER.debug('Extracted issue from output: %s', issue)
        self._issues.add(issue)
        break
    else:
      LOGGER.warning("Unable to extract issue from patch submission.")

  def _generate_commit_message(self, updates):
    lines = [
        'CrOS: Update Chromite pin.',
        '',
        'Update ChromeOS Chromite pins.'
        ]
    for name, update in updates.iteritems():
      if not update:
        continue

      fr, to = update
      lines.append('- [%s]' % (name,))
      if fr:
        if to:
          # Update from one commit to another.
          lines.extend([
            '  %s =>' % (fr,),
            '     %s' % (to,),
          ])
        else:
          # Added new pin.
          lines.append('  - Deleted (was %s)' % (fr,))
      elif to:
        # Deleted a pin.
        lines.append('  - Added => %s' % (to,))
    lines.append('')

    if self._bug:
      lines.append('BUG=%s' % (self._bug,))
    if self._reviewers:
      lines.append('TBR=%s' % (', '.join(self._reviewers)))
    return '\n'.join(lines)
