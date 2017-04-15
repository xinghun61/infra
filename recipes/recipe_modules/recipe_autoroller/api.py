# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import datetime
import hashlib
import re

from recipe_engine import recipe_api


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


def get_reviewers(commit_infos):
  """Get a set of authors and reviewers from 'recipes.py autoroll' commit infos.
  """
  reviewers = set()
  for commits in commit_infos.values():
    for commit in commits:
      reviewers.add(commit['author_email'])
  return reviewers


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


_AUTH_REFRESH_TOKEN_FLAG = (
    '--auth-refresh-token-json=/creds/refresh_tokens/recipe-roller')


_ROLL_STALE_THRESHOLD = datetime.timedelta(hours=2)


def get_commit_message(roll_result, tbrs=(), extra_reviewers=()):
  """Construct a roll commit message from 'recipes.py autoroll' result.
  """
  trivial = roll_result['trivial']
  message = 'Roll recipe dependencies (%s).\n' % (
      'trivial' if trivial else 'nontrivial')
  message += COMMIT_MESSAGE_HEADER
  if not trivial:
    message += NON_TRIVIAL_MESSAGE
  message += COMMIT_MESSAGE_INFO

  commit_infos = roll_result['picked_roll_details']['commit_infos']

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
  if not trivial:
    message += 'R=%s\n' % ','.join(sorted(
      get_reviewers(commit_infos) | set(extra_reviewers)
    ))
  if tbrs:
    message += 'TBR=%s\n' % ','.join(sorted(tbrs))
  message += COMMIT_MESSAGE_FOOTER
  return message


class RecipeAutorollerApi(recipe_api.RecipeApi):
  def roll_projects(self, projects):
    """Attempts to roll each project from the provided list.

    If rolling any of the projects leads to failures, other
    projects are not affected.
    """
    project_data = self.m.luci_config.get_projects()

    with self.m.tempfile.temp_dir('recipes') as recipes_dir:
      self.m.cipd.ensure(recipes_dir, {
          'infra/recipes-py': 'latest',
      })

      results = []
      with recipe_api.defer_results():
        for project in projects:
          with self.m.step.nest(str(project)):
            results.append(self._roll_project(
                project_data[project], recipes_dir))

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

  def _prepare_checkout(self, project_data):
    # Keep persistent checkout. Speeds up the roller for large repos
    # like chromium/src.
    workdir = self.m.path['cache'].join(
        'recipe_autoroller', project_data['id'])

    self.m.git.checkout(
        project_data['repo_url'], dir_path=workdir, submodules=False)

    with self.m.step.context({'cwd': workdir}):
      # Introduce ourselves to git - also needed for git cl upload to work.
      self.m.git('config', 'user.email', 'recipe-roller@chromium.org')
      self.m.git('config', 'user.name', 'recipe-roller')

      # Clean up possibly left over roll branch. Ignore errors.
      self.m.git('branch', '-D', 'roll', ok_ret='any')

      # git cl upload cannot work with detached HEAD, it requires a branch.
      self.m.git('checkout', '-t', '-b', 'roll', 'origin/master')

    return workdir

  def _check_previous_roll(self, project_data, workdir):
    # Check status of last known CL for this repo. Ensure there's always
    # at most one roll CL in flight.
    repo_data, cl_status = self._get_pending_cl_status(
        project_data['repo_url'], workdir)
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

      # We're about to upload a new CL, so close the old one.
      # Pass --gerrit flag to match upload args below.
      with self.m.step.context({'cwd': workdir}):
        self.m.git('cl', 'set-close',
                   '--issue', repo_data.issue,
                   '--gerrit',
                   _AUTH_REFRESH_TOKEN_FLAG,
                   # TODO(phajdan.jr): make set-close fatal after Gerrit switch.
                   ok_ret='any')
    return None

  def _read_autoroller_settings(self, recipes_cfg_path):
    current_cfg = self.m.json.read(
      'read recipes.cfg',
      recipes_cfg_path, step_test_data=lambda: self.m.json.test_api.output({}))

    return current_cfg.json.output['autoroll_recipe_options']

  def _roll_project(self, project_data, recipes_dir):
    """
    Args:
      project_data - The JSON form of a project_config, e.g. {
          "repo_type": "GITILES",
          "id": "foof",
          "repo_url": "https://chromium.googlesource.com/foof",
          "name": "Foof"
        }
    """
    # Keep persistent checkout. Speeds up the roller for large repos
    # like chromium/src.
    workdir = self._prepare_checkout(project_data)

    status = self._check_previous_roll(project_data, workdir)
    if status is not None:
      # This means that the previous roll is still going, or similar. In this
      # situation we're done with this repo, for now.
      return status

    recipes_cfg_path = workdir.join('infra', 'config', 'recipes.cfg')

    autoroll_settings = self._read_autoroller_settings(recipes_cfg_path)

    disable_reason = autoroll_settings.get('disable_reason')
    if disable_reason:
      rslt = self.m.python.succeeding_step('disabled', disable_reason)
      rslt.presentation.status = self.m.step.WARNING
      return ROLL_SKIP

    # Use the recipes bootstrap to checkout coverage.
    roll_step = self.m.step(
        'roll',
        [recipes_dir.join('recipes.py'), '--use-bootstrap', '--package',
         recipes_cfg_path, 'autoroll', '--output-json', self.m.json.output()])
    roll_result = roll_step.json.output

    if roll_result['success'] and roll_result['picked_roll_details']:
      self._process_successful_roll(
          project_data['repo_url'], roll_step, workdir, autoroll_settings)
      return ROLL_SUCCESS

    num_rejected = roll_result['rejected_candidates_count']
    if not roll_result['roll_details'] and num_rejected == 0:
      roll_step.presentation.step_text += ' (already at latest revisions)'
      return ROLL_EMPTY

    for i, roll_candidate in enumerate(roll_result['roll_details']):
      roll_step.presentation.logs['candidate #%d' % (i+1)] = (
        self.m.json.dumps(roll_candidate['spec']).splitlines())

    return ROLL_FAILURE

  def _process_successful_roll(self, repo_url, roll_step, workdir,
                               autoroll_settings):
    """
    Args:
      roll_step - The StepResult of the actual roll command. This is used to
        adjust presentation and obtain the json output.
      autoroll_settings - a AutorollRecipeOptions message from the recipe
        engine, in jsonish form (i.e. a python dict).
    """
    roll_result = roll_step.json.output

    tbrs = []
    extra_reviewers = []
    upload_args =  []
    if roll_result['trivial']:
      s = autoroll_settings['trivial']
      tbrs = s.get('tbr_emails', [])
      if s.get('automatic_commit'):
        upload_args.append('--use-commit-queue')
    else:
      s = autoroll_settings['nontrivial']
      upload_args.append('--send-mail')
      extra_reviewers = s.get('extra_reviewers', [])
      if s.get('automatic_commit_dry_run'):
        upload_args.append('--cq-dry-run')

    commit_message = get_commit_message(
      roll_result, tbrs=tbrs, extra_reviewers=extra_reviewers)

    roll_step.presentation.logs['commit_message'] = commit_message.splitlines()
    if roll_result['trivial']:
      roll_step.presentation.step_text += ' (trivial)'
    else:
      roll_step.presentation.status = self.m.step.FAILURE

    with self.m.step.context({'cwd': workdir}):
      self.m.git('commit', '-a', '-m', 'roll recipes.cfg')

    upload_args.extend(['--bypass-hooks', '-f'])
    upload_args.extend(['--gerrit'])
    upload_args.extend([_AUTH_REFRESH_TOKEN_FLAG])
    with self.m.step.context({'cwd': workdir}):
      self.m.git_cl.upload(
          commit_message, upload_args, name='git cl upload')
      issue_step = self.m.git(
          'cl', 'issue', '--json', self.m.json.output(),
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
        'recipe-roller-cl-uploads',
        'repo_metadata/%s' % base64.urlsafe_b64encode(repo_url))

  def _get_pending_cl_status(self, repo_url, workdir):
    """Returns (current_repo_data, git_cl_status_string) of the last known
    roll CL for given repo.

    If no such CL has been recorded, returns (None, None).
    """
    cat_result = self.m.gsutil.cat(
        'gs://recipe-roller-cl-uploads/repo_metadata/%s' % (
            base64.urlsafe_b64encode(repo_url)),
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

    with self.m.step.context({'cwd': workdir}):
      # We need to explicitly pass --gerrit for git cl status --issue .
      # To keep things concistent, we also pass --gerrit for all other
      # git cl calls in the autoroller.
      status_result = self.m.git(
          'cl', 'status',
          '--issue', repo_data.issue,
          '--gerrit',
          '--field', 'status',
          _AUTH_REFRESH_TOKEN_FLAG,
          name='git cl status', stdout=self.m.raw_io.output(),
          step_test_data=lambda: self.m.raw_io.test_api.stream_output(
              'foo')
      ).stdout.strip()

    return repo_data, status_result
