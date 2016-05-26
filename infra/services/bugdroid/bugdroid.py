# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Update bug trackers with information from repository commits."""

import argparse
import datetime
import json
import logging
import os
import sys
import threading
import time

import infra.services.bugdroid.branch_utils as branch_utils
import infra.services.bugdroid.config_service as config_service
import infra.services.bugdroid.gerrit_poller as gerrit_poller
import infra.services.bugdroid.gitiles_poller as gitiles_poller
import infra.services.bugdroid.IssueTrackerManager as IssueTrackerManager
import infra.services.bugdroid.log_parser as log_parser
import infra.services.bugdroid.poller_handlers as poller_handlers
import infra.services.bugdroid.scm_helper as scm_helper


# pylint: disable=C0301
URL_TEMPLATES = {
    'cr': 'http://src.chromium.org/viewvc/chrome?view=rev&revision=%d',
    'cr_int': ('http://goto.ext.google.com/viewvc/'
               'chrome-internal?view=rev&revision=%d'),
    'nacl': 'http://src.chromium.org/viewvc/native_client?view=rev&revision=%d'
    }

PATH_URL_TEMPLATES = {
    'viewvc': 'http://src.chromium.org/viewvc/%s%s?r1=%d&r2=%d&pathrev=%d',
    'viewvc_int': 'http://goto.google.com/viewvc/%s%s?r1=%d&r2=%d&pathrev=%d'
    }
# pylint: enable=C0301

CODESITE_PROJECTS = [
    'brillo', 'chrome-os-partner',
]


loggers = {}


def GetLogger(logger_id):
  """Logging setup for pollers."""
  # pylint: disable=global-variable-not-assigned
  global loggers
  if loggers.get(logger_id):
    return loggers.get(logger_id)
  else:
    logger = logging.getLogger(logger_id)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    sh = logging.StreamHandler()
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    loggers[logger_id] = logger
    return logger


class BugdroidPollerHandler(poller_handlers.BasePollerHandler):
  """Handler for updating bugs with information from commits."""

  def __init__(self, bugdroid, default_project,
               no_merge=None, public_bugs=True, test_mode=False,
               issues_labels=None, *args, **kwargs):
    self.bugdroid = bugdroid
    self.default_project = default_project
    self.no_merge = no_merge or []
    self.public_bugs = public_bugs
    self.test_mode = test_mode
    if issues_labels:
      self.issues_labels = dict((p.key, p.value) for p in issues_labels)
    else:
      self.issues_labels = {}
    super(BugdroidPollerHandler, self).__init__(*args, **kwargs)

  def WarmUp(self):
    try:
      self.bugdroid.Reset(self.default_project)
    except Exception:  # pylint: disable=W0703
      self.logger.exception('Unhandled Exception')

  def _ApplyMergeMergedLabel(self, issue, branch):
    if not branch or not issue:
      return

    label = '%s-%s' % (self.issues_labels.get('merge', 'merge-merged'), branch)
    issue.addLabel(label)
    if self.logger:
      self.logger.debug('Adding %s', label)

    label = self.issues_labels.get('approved', 'merge-approved')
    if issue.hasLabel(label):
      issue.removeLabel(label)
      if self.logger:
        self.logger.debug('Removing %s', label)

    mstone = branch_utils.get_mstone(branch, False)
    if mstone:
      label = 'merge-approved-%s' % mstone
      if issue.hasLabel(label):
        issue.removeLabel(label)
        if self.logger:
          self.logger.debug('Removing %s' % label)

  def ProcessLogEntry(self, log_entry):

    project_bugs = log_parser.get_issues(
        log_entry, default_project=self.default_project)
    if self.logger:
      self.logger.info('Processing commit %s : bugs %s' %
                       (log_entry.revision, str(project_bugs)))
    if project_bugs:
      comment = self._CreateMessage(log_entry)
      if self.logger:
        self.logger.debug(comment)

      for project, bugs in project_bugs.iteritems():
        itm = self.bugdroid.GetItm(project)
        for bug in bugs:
          issue = itm.getIssue(bug)
          issue.comment = comment[:24 * 1024]
          branch = scm_helper.GetBranch(log_entry)
          # Apply merge labels if this commit landed on a branch.
          if branch and not (log_entry.scm in ['git', 'gerrit'] and
                             scm_helper.GetBranch(log_entry, full=True) in
                             self.no_merge):
            self._ApplyMergeMergedLabel(issue, branch)
          if self.logger:
            self.logger.debug('Attempting to save issue: %d' % issue.id)
          if not self.test_mode:
            issue.save()

  def _CreateMessage(self, log_entry):  # pylint: disable=W0613,R0201
    raise NotImplementedError


class BugdroidSVNPollerHandler(BugdroidPollerHandler):
  """Handler for updating bugs with information from svn commits."""

  def __init__(self, url_template, path_url_template, svn_project, *args,
               **kwargs):
    self.url_template = url_template
    self.path_url_template = path_url_template
    self.svn_project = svn_project
    super(BugdroidSVNPollerHandler, self).__init__(*args, **kwargs)

  def _CreateMessage(self, log_entry):
    msg = ''
    # If the url_template matches the Chromium URL template, then the
    # preamble we would use is redundant with the "r12345" linkification
    # that codesite does, which points by default to the Chromium ViewVC
    # instance.  In the cases where the URL template is for another
    # project, include the preamble.
    if self.url_template != URL_TEMPLATES['cr']:
      msg += 'The following revision refers to this bug:\n'
      msg += '  %s\n\n' % (self.url_template % log_entry.revision)
    msg += self._BuildLogSpecial(log_entry)
    return msg

  def _BuildLogSpecial(self, log_entry):
    """Generate svn-log style message, with links to files in the Web UI."""
    rtn = '------------------------------------------------------------------\n'
    rtn += 'r%d | %s | %s\n\n' % (log_entry.revision, log_entry.author,
                                  log_entry.date)
    if self.public_bugs:
      rtn += 'Changed paths:\n'
      for path in log_entry.paths:
        filename = self.path_url_template % (self.svn_project, path.filename,
                                             log_entry.revision,
                                             log_entry.revision - 1,
                                             log_entry.revision)
        rtn += '   %s %s\n' % (path.action, filename)

      rtn += '\n%s\n' % log_entry.msg
    rtn += '-----------------------------------------------------------------'
    return rtn


class BugdroidGitPollerHandler(BugdroidPollerHandler):
  """Handler for updating bugs with information from git commits."""

  def _CreateMessage(self, log_entry):
    msg = ''
    msg += 'The following revision refers to this bug:\n'
    msg += '  %s\n\n' % log_entry.GetCommitUrl()
    msg += self._BuildLogSpecial(log_entry)
    return msg

  def _BuildLogSpecial(self, log_entry):
    """Generate git-log style message, with links to files in the Web UI."""
    rtn = 'commit %s\n' % log_entry.commit
    rtn += 'Author: %s <%s>\n' % (log_entry.author_name, log_entry.author_email)
    rtn += 'Date: %s\n' % log_entry.author_date
    if self.public_bugs:
      rtn += '\n%s\n' % log_entry.msg
      for path in log_entry.paths:
        if path.action == 'delete':
          # Use parent and copy_from_path for deletions, otherwise we get links
          # to https://.../<commit>//dev/null
          rtn += '[%s] %s\n' % (
              path.action, log_entry.GetPathUrl(
                  path.copy_from_path, parent=True, universal=True))
        else:
          rtn += '[%s] %s\n' % (
              path.action, log_entry.GetPathUrl(
                  path.filename, universal=True))
    return rtn


class Bugdroid(object):
  """App to setup and run repository pollers and bug updating handlers."""

  def __init__(self, configfile, credentials_db, run_once, datadir):
    self.pollers = []
    self.trackers = {}
    self.credentials_db = credentials_db
    self.run_once = run_once

    if not os.path.isdir(datadir):
      if os.path.exists(datadir):
        raise ConfigsException(
          'datadir "%s" is not a directory.' % datadir)
      os.makedirs(datadir)
    self.datadir = datadir

    logging.basicConfig(level=logging.DEBUG)

    configs = config_service.get_repos(self.credentials_db, configfile)

    if not configs:
      logging.critical('Failed to load poller configs. Aborting.')
      raise ConfigsException()

    for config in configs.repos:
      if config.refs_regex and config.filter_regex:
        if len(config.refs_regex) != len(config.filter_regex):
          logging.critical(
              'Config error (%s): "refs_regex" and "filter_regex" '
              'cannot have different numbers of items.', config.repo_name)

          raise ConfigsException()
      poller = self.InitPoller(config.repo_name, config)
      self.pollers.append(poller)

  def Reset(self, project_name=None):
    if project_name:
      if project_name in self.trackers:
        del self.trackers[project_name]
    else:
      self.trackers.clear()

  def GetItm(self, project, use_cache=True):
    """Get (or create) the IssueTrackerManager for the given project."""
    # Lazy load all of the trackers (so nothing gets specified up front)
    if not use_cache or project not in self.trackers:
      if project in CODESITE_PROJECTS:
        itm = IssueTrackerManager.IssueTrackerManager(
            client_id=None, client_secret=None,
            project_name=project, credential_store=self.credentials_db)
      else:
        itm = IssueTrackerManager.MonorailIssueTrackerManager(
            client_id=None, client_secret=None,
            project_name=project, credential_store=self.credentials_db)
      self.trackers[project] = itm
    return self.trackers[project]

  def InitPoller(self, name, config):
    """Create a repository poller based on the given config."""

    poller = None
    t = config_service.decode_repo_type(config.repo_type)
    interval_minutes = 1
    default_project = config.default_project
    logger = GetLogger(name)
    if t == 'git':
      poller = gitiles_poller.GitilesPoller(
          config.repo_url,
          name,
          refs_regex=config.refs_regex,
          paths_regex=config.paths_regex,
          filter_regex=config.filter_regex,
          interval_in_minutes=interval_minutes,
          logger=logger,
          run_once=self.run_once,
          datadir=self.datadir)

      h = BugdroidGitPollerHandler(
          bugdroid=self,
          default_project=default_project,
          public_bugs=config.public_bugs,
          test_mode=config.test_mode,
          issues_labels=config.issues_labels,
          no_merge=config.no_merge_refs)
      poller.add_handler(h)
    elif t == 'gerrit':
      poller = gerrit_poller.GerritPoller(
          config.repo_url,
          name,
          interval_in_minutes=interval_minutes,
          logger=logger,
          run_once=self.run_once,
          datadir=self.datadir)

      h = BugdroidGitPollerHandler(
          bugdroid=self,
          default_project=default_project,
          public_bugs=config.public_bugs,
          test_mode=config.test_mode,
          issues_labels=config.issues_labels,
          no_merge=config.no_merge_refs)
      poller.add_handler(h)

    else:
      logging.error('Unknown poller type: %s', t)

    if poller:
      poller.saved_config = config
      poller.daemon = True
    return poller

  def Execute(self):
    for poller in self.pollers:
      if poller.logger:
        poller.logger.info('Starting Poller "%s".', poller.poller_id)
      poller.start()
    # While any pollers are alive, try to keep them all alive. If they all die
    # for some reason (only the main thread left), something is probably
    # terribly wrong, so just let the program exit.
    while threading.active_count() > 1 and not self.run_once:
      # Polling intervals are in minutes, so check that they're alive a little
      # more frequently than that.
      time.sleep(55)
      logging.debug('Checking pollers ...')
      for poller in self.pollers[:]:
        if not poller.isAlive():
          # TODO(mmoss): Maybe send an alert email, so these failures can be
          # investigated (without needing to discover them in the logs)? Or
          # maybe only if the same poller dies too frequently or too quickly?
          logging.error('Poller "%s" died. Restarting ...', poller.poller_id)
          self.pollers.remove(poller)
          poller = self.InitPoller(poller.poller_id, poller.saved_config)
          self.pollers.append(poller)
          poller.start()


def inner_loop(opts):
  try:
    bug = Bugdroid(opts.configfile, opts.credentials_db, True, opts.datadir)
    bug.Execute()
    return True
  except ConfigsException:
    return False


class Error(Exception):
  """Base exception class."""
  pass


class ConfigsException(Error):
  """The repo configs cannot be used."""
  pass