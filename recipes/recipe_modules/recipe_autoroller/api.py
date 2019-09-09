# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import datetime
import hashlib
import re

from google.protobuf import json_format as jsonpb

from recipe_engine import recipe_api
from PB.recipe_engine.recipes_cfg import RepoSpec


class RepoData(object):
  _TIME_FORMAT = '%Y-%m-%dT%H:%M:%S'

  def __init__(self, issue, issue_url, trivial, last_roll_ts_utc):
    assert isinstance(issue, str)
    assert isinstance(issue_url, str)
    assert isinstance(trivial, bool)
    assert isinstance(last_roll_ts_utc, datetime.datetime)

    self.issue = issue
    self.issue_url = issue_url
    self.trivial = trivial
    self.last_roll_ts_utc = last_roll_ts_utc

  @classmethod
  def from_json(cls, obj):
    return cls(
      obj['issue'],
      obj['issue_url'],
      obj['trivial'],
      datetime.datetime.strptime(obj['last_roll_ts_utc'], cls._TIME_FORMAT),
    )

  def to_json(self):
    return {
      'issue': self.issue,
      'issue_url': self.issue_url,
      'trivial': self.trivial,
      'last_roll_ts_utc': self.last_roll_ts_utc.strftime(self._TIME_FORMAT),
    }


COMMIT_MESSAGE_HEADER = (
"""
This is an automated CL created by the recipe roller. This CL rolls recipe
changes from upstream projects (e.g. depot_tools) into downstream projects
(e.g. tools/build).
""")


NON_TRIVIAL_MESSAGE = (
"""

Please review the expectation changes, and LGTM+CQ.
"""
)

COMMIT_MESSAGE_INFO = (
"""

More info is at https://goo.gl/zkKdpD. Use https://goo.gl/noib3a to file a bug.
""")

COMMIT_MESSAGE_FOOTER = (
"""
Recipe-Tryjob-Bypass-Reason: Autoroller
Bugdroid-Send-Email: False
""")


# These are different results of a roll attempt:
#   - success means we have a working non-empty roll
#   - empty means the repo is using latest revision of its dependencies
#   - failure means there are roll candidates but none of them are suitable
#     for an automated roll
#   - skip means that the roll was skipped (not processed). This can happen if
#     the repo has a 'disable_message' in its autoroll_recipe_options.
ROLL_SUCCESS, ROLL_EMPTY, ROLL_FAILURE, ROLL_SKIP = range(4)


_ROLL_STALE_THRESHOLD = datetime.timedelta(hours=2)


_GS_BUCKET = 'recipe-mega-roller-crappy-db'


def _gs_path(project_url):
  return 'repo_metadata/%s' % base64.urlsafe_b64encode(project_url)


def get_commit_message(roll_result):
  """Construct a roll commit message from 'recipes.py autoroll' result.
  """
  picked = roll_result['picked_roll_details']

  trivial = roll_result['trivial']
  message = 'Roll recipe dependencies (%s).\n' % (
      'trivial' if trivial else 'nontrivial')
  message += COMMIT_MESSAGE_HEADER
  if not trivial:
    message += NON_TRIVIAL_MESSAGE
  message += COMMIT_MESSAGE_INFO

  commit_infos = picked['commit_infos']

  def get_blame(commit_infos):
    blame = []
    for project, commits in commit_infos.iteritems():
      blame.append('%s:' % project)
      for commit in commits:
        message = commit['message_lines']
        # TODO(phajdan.jr): truncate long messages.
        message = message[0] if message else 'n/a'
        blame.append('  https://crrev.com/%s %s (%s)' % (
            commit['revision'], message, commit['author_email']))
    return blame

  message += '%s\n' % '\n'.join(get_blame(commit_infos))
  message += '\n'
  message += COMMIT_MESSAGE_FOOTER
  return message


class RecipeAutorollerApi(recipe_api.RecipeApi):
  def __init__(self, **kwargs):
    super(RecipeAutorollerApi, self).__init__(**kwargs)

  def roll_projects(self, projects):
    """Attempts to roll each project from the provided list.

    If rolling any of the projects leads to failures, other
    projects are not affected.

    Args:
      projects: list of tuples of
        project_id (string): id as found in recipes.cfg.
        project_url (string): Git repository URL of the project.
    """
    recipes_dir = self.m.path['cache'].join('builder', 'recipe_engine')
    self.m.file.rmtree('ensure recipe_dir gone', recipes_dir)
    self.m.file.ensure_directory(
        'ensure builder cache dir exists',
        self.m.path['cache'].join('builder'))

    with self.m.context(cwd=self.m.path['cache'].join('builder')):
      # Git clone really wants to have cwd set to something other than None.
      self.m.git('clone', '--depth', '1',
                 'https://chromium.googlesource.com/infra/luci/recipes-py',
                 recipes_dir, name='clone recipe engine')

    results = []
    with recipe_api.defer_results():
      for project_id, project_url in projects:
        with self.m.step.nest(str(project_id)):
          results.append(
              self._roll_project(project_id, project_url, recipes_dir))

    # We need to unwrap |DeferredResult|s.
    results = [r.get_result() for r in results]

    # Failures to roll are OK as long as at least one of the repos is moving
    # forward. For example, with repos with following dependencies:
    #
    #   A    <- B
    #   A, B <- C
    #
    # New commit in A repo will need to get rolled into B first. However,
    # it'd also appear as a candidate for C roll, leading to a failure there.
    if ROLL_FAILURE in results and ROLL_SUCCESS not in results:
      self.m.python.failing_step(
          'roll result',
          'manual intervention needed: automated roll attempt failed')

  def _prepare_checkout(self, project_id, project_url):
    # Keep persistent checkout. Speeds up the roller for large repos
    # like chromium/src.
    workdir = self.m.path['cache'].join(
        'builder', 'recipe_autoroller', project_id)
    self.m.git.checkout(project_url, dir_path=workdir, submodules=False)

    with self.m.context(cwd=workdir):
      # On LUCI user.email is already configured to match that of task service
      # account with which we'll be authenticating to Git/Gerrit.
      # Set a nicer name than service account's long email.
      self.m.git('config', 'user.name', 'recipe-roller')

      # Clean up possibly left over roll branch. Ignore errors.
      self.m.git('branch', '-D', 'roll', ok_ret='any')

      # git cl upload cannot work with detached HEAD, it requires a branch.
      self.m.git('checkout', '-t', '-b', 'roll', 'origin/master')

    return workdir

  def _check_previous_roll(self, project_url, workdir):
    # Check status of last known CL for this repo. Ensure there's always
    # at most one roll CL in flight.
    repo_data, cl_status = self._get_pending_cl_status(project_url, workdir)
    if repo_data:
      last_roll_elapsed = self.m.time.utcnow() - repo_data.last_roll_ts_utc

      # Allow trivial rolls in CQ to finish.
      if repo_data.trivial and cl_status == 'commit':
        if (last_roll_elapsed and
            last_roll_elapsed > _ROLL_STALE_THRESHOLD):
          self.m.python.failing_step(
              'stale roll',
              'manual intervention needed: automated roll attempt is stale')

        return ROLL_SUCCESS

      # Allow non-trivial rolls to wait for review comments.
      if not repo_data.trivial and cl_status != 'closed':
        if (last_roll_elapsed and
            last_roll_elapsed > _ROLL_STALE_THRESHOLD):
          self.m.python.failing_step(
              'stale roll',
              'manual intervention needed: automated roll attempt is stale')

        return ROLL_SUCCESS

      # TODO(phajdan.jr): detect staleness by creating CLs in a loop.
      # It's possible that the roller keeps creating new CLs (especially
      # trivial rolls), but they e.g. fail to land, causing staleness.

      # We're about to upload a new CL, so make sure the old one is closed.
      # Pass --gerrit flag to match upload args below.
      if cl_status != 'closed':
        with self.m.context(cwd=workdir):
          self.m.git_cl('set-close', ['--issue', repo_data.issue, '--gerrit'],
                        name='git cl set-close')
    return None

  def _get_disable_reason(self, recipes_cfg_path):
    current_cfg = self.m.json.read(
      'read recipes.cfg',
      recipes_cfg_path, step_test_data=lambda: self.m.json.test_api.output({}))

    return current_cfg.json.output.get(
        'autoroll_recipe_options', {}
    ).get('disable_reason')

  def _roll_project(self, project_id, project_url, recipes_dir):
    # Keep persistent checkout. Speeds up the roller for large repos
    # like chromium/src.
    workdir = self._prepare_checkout(project_id, project_url)

    recipes_cfg_path = workdir.join('infra', 'config', 'recipes.cfg')

    disable_reason = self._get_disable_reason(recipes_cfg_path)
    if disable_reason:
      rslt = self.m.python.succeeding_step('disabled', disable_reason)
      rslt.presentation.status = self.m.step.WARNING
      return ROLL_SKIP

    status = self._check_previous_roll(project_url, workdir)
    if status is not None:
      # This means that the previous roll is still going, or similar. In this
      # situation we're done with this repo, for now.
      return status

    roll_step = self.m.python(
        'roll',
        recipes_dir.join('recipes.py'), [
          '--package', recipes_cfg_path,
          'autoroll',
          '--output-json', self.m.json.output()],
        venv=True)
    roll_result = roll_step.json.output

    if roll_result['success'] and roll_result['picked_roll_details']:
      self._process_successful_roll(project_url, roll_step, workdir)
      return ROLL_SUCCESS

    num_rejected = roll_result['rejected_candidates_count']
    if not roll_result['roll_details'] and num_rejected == 0:
      roll_step.presentation.step_text += ' (already at latest revisions)'
      return ROLL_EMPTY

    for i, roll_candidate in enumerate(roll_result['roll_details']):
      roll_step.presentation.logs['candidate #%d' % (i+1)] = (
        self.m.json.dumps(roll_candidate['spec']).splitlines())

    return ROLL_FAILURE

  def _process_successful_roll(self, project_url, roll_step, workdir):
    """
    Args:
      roll_step - The StepResult of the actual roll command. This is used to
        adjust presentation and obtain the json output.
    """
    roll_result = roll_step.json.output
    picked_details = roll_result['picked_roll_details']

    spec = jsonpb.ParseDict(picked_details['spec'], RepoSpec())

    upload_args = ['--send-mail']
    if roll_result['trivial']:
      s = spec.autoroll_recipe_options.trivial
      if s.tbr_emails:
        upload_args.append('--tbrs=%s' % (','.join(s.tbr_emails)))

      upload_args.append('--tbr-owners')

      if s.automatic_commit:
        upload_args.append('--use-commit-queue')
    else:
      s = spec.autoroll_recipe_options.nontrivial
      if s.extra_reviewer_emails:
        upload_args.append('--reviewers=%s' % ','.join(s.extra_reviewer_emails))

      upload_args.append('--r-owners')

      if s.automatic_commit_dry_run:
        upload_args.append('--cq-dry-run')

    cc_list = set()
    for commits in picked_details['commit_infos'].itervalues():
      for commit in commits:
        cc_list.add(commit['author_email'])
    upload_args.append('--cc=%s' % ','.join(sorted(cc_list)))
    upload_args.extend(['--bypass-hooks', '-f'])
    upload_args.extend(['--gerrit'])

    commit_message = get_commit_message(roll_result)

    roll_step.presentation.logs['commit_message'] = commit_message.splitlines()
    if roll_result['trivial']:
      roll_step.presentation.step_text += ' (trivial)'
    else:
      roll_step.presentation.status = self.m.step.FAILURE

    with self.m.context(cwd=workdir):
      self.m.git('commit', '-a', '-m', 'roll recipes.cfg')
      self.m.git_cl.upload(
          commit_message, upload_args, name='git cl upload')
      issue_step = self.m.git_cl(
          'issue', ['--json', self.m.json.output()],
          name='git cl issue',
          step_test_data=lambda: self.m.json.test_api.output({
              'issue': 123456789,
              'issue_url': 'https://codereview.chromium.org/123456789'}))
    issue_result = issue_step.json.output

    if not issue_result['issue'] or not issue_result['issue_url']:
      self.m.python.failing_step(
          'git cl upload failed', 'no issue metadata returned')

    repo_data = RepoData(
      str(issue_result['issue']),
      issue_result['issue_url'],
      roll_result['trivial'],
      self.m.time.utcnow(),
    )

    issue_step.presentation.links['Issue %s' % repo_data.issue] = (
        repo_data.issue_url)

    self.m.gsutil.upload(
        self.m.json.input(repo_data.to_json()),
        _GS_BUCKET, _gs_path(project_url))

  def _get_pending_cl_status(self, project_url, workdir):
    """Returns (current_repo_data, git_cl_status_string) of the last known
    roll CL for given repo.

    If no such CL has been recorded, returns (None, None).
    """
    cat_result = self.m.gsutil.cat(
        'gs://%s/%s' % (_GS_BUCKET, _gs_path(project_url)),
        stdout=self.m.raw_io.output(),
        stderr=self.m.raw_io.output(),
        ok_ret=(0,1),
        name='repo_state',
        step_test_data=lambda: self.m.raw_io.test_api.stream_output(
            'No URLs matched', stream='stderr', retcode=1))

    if cat_result.retcode:
      cat_result.presentation.logs['stderr'] = [
          self.m.step.active_result.stderr]
      if not re.search('No URLs matched', cat_result.stderr): # pragma: no cover
        raise Exception('gsutil failed in an unexpected way; see stderr log')
      return None, None

    repo_data = RepoData.from_json(self.m.json.loads(cat_result.stdout))
    cat_result.presentation.links['Issue %s' % repo_data.issue] = (
        repo_data.issue_url)
    if repo_data.trivial:
      cat_result.presentation.step_text += ' (trivial)'

    with self.m.context(cwd=workdir):
      # We need to explicitly pass --gerrit for git cl status --issue .
      # To keep things concistent, we also pass --gerrit for all other
      # git cl calls in the autoroller.
      status_result = self.m.git_cl(
          'status',
          ['--issue', repo_data.issue, '--gerrit', '--field', 'status'],
          name='git cl status', stdout=self.m.raw_io.output(),
          step_test_data=lambda: self.m.raw_io.test_api.stream_output(
              'foo')
      ).stdout.strip()
      self.m.step.active_result.presentation.step_text = status_result

    return repo_data, status_result
