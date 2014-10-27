#!/usr/bin/env python
# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fetch the latest results for a pre-selected set of builders we care about.
If we find a 'good' revision -- based on criteria explained below -- we
mark the revision as LKGR, and POST it to the LKGR server:

http://chromium-status.appspot.com/lkgr

We're looking for a sequence in the revision history that looks something
like this:

  Revision        Builder1        Builder2        Builder3
 -----------------------------------------------------------
     12357         green

     12355                                         green

     12352                         green

     12349                                         green

     12345         green


Given this revision history, we mark 12352 as LKGR.  Why?

  - We know 12352 is good for Builder2.
  - Since Builder1 had two green builds in a row, we can be reasonably
    confident that all revisions between the two builds (12346 - 12356,
    including 12352), are also green for Builder1.
  - Same reasoning for Builder3.

To find a revision that meets these criteria, we can walk backward through
the revision history until we get a green build for every builder.  When
that happens, we mark a revision as *possibly* LKGR.  We then continue
backward looking for a second green build on all builders (and no failures).
For all builders that are green on the LKGR candidate itself (12352 in the
example), that revision counts as BOTH the first and second green builds.
Hence, in the example above, we don't look for an actual second green build
of Builder2.

Note that this arrangement is symmetrical; we could also walk forward through
the revisions and run the same algorithm.  Since we are only interested in the
*latest* good revision, we start with the most recent revision and walk
backward.
"""

import argparse
import json
import logging
import os
import sys

import requests

from infra.libs import git
from infra.services.lkgr_finder import lkgr_lib, status_generator


LOGGER = logging.getLogger(__name__)


class NOTSET(object):
  """Singleton class for argument parser defaults."""
  @staticmethod
  def __str__():
    return '<Not Set>'
NOTSET = NOTSET()


def ParseArgs(argv):
  parser = argparse.ArgumentParser('python -m %s' % __package__)

  log_group = parser.add_mutually_exclusive_group()
  log_group.add_argument('--quiet', '-q', dest='loglevel',
                         action='store_const', const='CRITICAL', default='INFO')
  log_group.add_argument('--verbose', '-v', dest='loglevel',
                         action='store_const', const='DEBUG', default='INFO')

  input_group = parser.add_argument_group('Input data sources')
  input_group.add_argument('--buildbot', action='store_true', default=True,
                           help='Get data from Buildbot JSON (default).')
  input_group.add_argument('--build-data', metavar='FILE',
                           help='Get data from the specified file.')
  input_group.add_argument('--manual', metavar='VALUE',
                           help='Bypass logic and manually specify LKGR.')
  input_group.add_argument('--max-threads', '-j', type=int, default=4,
                           help='Maximum number of parallel json requests. A '
                                'value of zero means full parallelism.')

  output_group = parser.add_argument_group('Output data formats')
  output_group.add_argument('--dry-run', '-n', action='store_true',
                            help='Don\'t actually do any real output actions.')
  output_group.add_argument('--post', action='store_true',
                            help='Post the LKGR to the configured status app.')
  output_group.add_argument('--tag', action='store_true',
                            help='Update the lkgr tag (Git repos only)')
  output_group.add_argument('--write-to-file', metavar='FILE',
                            help='Write the LKGR to the specified file.')
  output_group.add_argument('--dump-build-data', metavar='FILE',
                            help='Dump the build data to the specified file.')
  output_group.add_argument('--html', metavar='FILE',
                            help='Output data in HTML format for debugging.')
  output_group.add_argument('--email-errors', action='store_true',
                            help='Send email to LKGR admins upon error (cron).')

  config_group = parser.add_argument_group('Project configuration overrides')
  config_group.add_argument('--password-file',
                            default=NOTSET,
                            help='File containing password for status app.')
  config_group.add_argument('--error-recipients', metavar='EMAILS',
                            default=NOTSET,
                            help='Send email to these addresses upon error.')
  config_group.add_argument('--update-recipients', metavar='EMAILS',
                            default=NOTSET,
                            help='Send email to these address upon success.')
  config_group.add_argument('--allowed-gap', type=int, metavar='GAP',
                            default=NOTSET,
                            help='How many revisions to allow between head and'
                                 ' LKGR before it\'s considered out-of-date.')
  config_group.add_argument('--allowed-lag', type=int, metavar='LAG',
                            default=NOTSET,
                            help='How many hours to allow since an LKGR update'
                                 ' before it\'s considered out-of-date. This '
                                 'is a minimum and will be increased when '
                                 'commit activity slows.')
  config_arg_names = ['password_file', 'error_recipients', 'update_recipients',
                      'allowed_gap', 'allowed_lag']

  parser.add_argument('--project', required=True,
                      help='Project for which to calculate the LKGR.Currently '
                           'accepted projects are those with a <project>.cfg '
                           'file in this directory.')
  parser.add_argument('--force', action='store_true',
                      help='Force updating the lkgr to the found (or manually '
                           'specified) value. Skips checking for validity '
                           'against the current LKGR.')

  args = parser.parse_args(argv)
  return args, config_arg_names


def main(argv):
  # TODO(agable): Refactor this into multiple sequential helper functions.

  args, config_arg_names = ParseArgs(argv)

  global LOGGER
  logging.basicConfig(
      # %(levelname)s is formatted to min-width 8 since CRITICAL is 8 letters.
      format='%(asctime)s | %(levelname)8s | %(name)s | %(message)s',
      level=args.loglevel)
  LOGGER = logging.getLogger(__name__)
  LOGGER.addFilter(lkgr_lib.RunLogger())

  config = lkgr_lib.GetProjectConfig(args.project)
  for name in config_arg_names:
    cmd_line_config = getattr(args, name, NOTSET)
    if cmd_line_config is not NOTSET:
      config[name] = cmd_line_config

  # Calculate new candidate LKGR.
  LOGGER.info('Calculating LKGR for project %s', args.project)

  repo = lkgr_lib.VCSWrapper.new(
      config['source_vcs'], config['source_url'],
      os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'workdir', args.project))

  monkeypatch_rev_map = config.get('monkeypatch_rev_map')
  if monkeypatch_rev_map:
    repo._position_cache.update(monkeypatch_rev_map)

  if args.manual:
    candidate = args.manual
    LOGGER.info('Using manually specified candidate %s', args.manual)
    if not repo.check_rev(candidate):
      LOGGER.fatal('Manually specified revision %s is not a valid revision for'
                   ' project %s' % (args.manual, args.project))
      return 1
  else:
    lkgr_builders = config['masters']
    if args.build_data:
      builds = lkgr_lib.ReadBuildData(args.build_data)
    else:
      builds = lkgr_lib.FetchBuildData(lkgr_builders, args.max_threads)

    if args.dump_build_data:
      try:
        with open(args.dump_build_data, 'w') as fh:
          json.dump(builds, fh, indent=2)
      except IOError, e:
        LOGGER.warn('Could not dump to %s:\n%s\n' %
                    (args.dump_build_data, repr(e)))

    (build_history, revisions) = lkgr_lib.CollateRevisionHistory(
        builds, lkgr_builders, repo)

    status_gen = status_generator.StatusGeneratorStub()
    if args.html:
      viewvc = config.get('viewvc_url', config['source_url'] + '/+/%s')
      status_gen = status_generator.HTMLStatusGenerator(viewvc=viewvc)

    candidate = lkgr_lib.FindLKGRCandidate(
        build_history, revisions, repo.keyfunc, status_gen)

    if args.html:
      lkgr_lib.WriteHTML(status_gen, args.html, args.dry_run)

  LOGGER.info('Candidate LKGR is %s', candidate)

  lkgr = None
  if not args.force:
    # Get old/current LKGR.
    if args.write_to_file:
      # If the new lkgr should be written to a file, read the current one from
      # the same file.
      lkgr = lkgr_lib.ReadLKGR(args.write_to_file)
      if lkgr is None:
        if args.email_errors:
          lkgr_lib.SendMail(config['error_recipients'],
                            'Failed to read %s LKGR. Please seed an initial '
                            'LKGR in file %s' %
                            (args.project, args.write_to_file),
                            '\n'.join(lkgr_lib.RunLogger.log), args.dry_run)
        LOGGER.fatal('Failed to read current %s LKGR. Please seed an initial '
                     'LKGR in file %s' % (args.project, args.write_to_file))
        return 1
    else:
      lkgr = lkgr_lib.FetchLKGR(config['status_url'] + repo.status_path)
      if lkgr is None:
        if args.email_errors:
          lkgr_lib.SendMail(config['error_recipients'],
                            'Failed to fetch %s LKGR' % args.project,
                            '\n'.join(lkgr_lib.RunLogger.log), args.dry_run)
        LOGGER.fatal('Failed to fetch current %s LKGR' % args.project)
        return 1

    if not repo.check_rev(lkgr):
      if args.email_errors:
        lkgr_lib.SendMail(config['error_recipients'],
                          'Fetched bad current %s LKGR' % args.project,
                          '\n'.join(lkgr_lib.RunLogger.log), args.dry_run)
      LOGGER.fatal('Fetched bad current %s LKGR: %s' % (args.project, lkgr))
      return 1

    LOGGER.info('Current LKGR is %s', lkgr)

  if candidate and (args.force or repo.keyfunc(candidate) > repo.keyfunc(lkgr)):
    # We found a new LKGR!
    LOGGER.info('Candidate is%snewer than current %s LKGR!',
                ' (forcefully) ' if args.force else ' ', args.project)

    if args.write_to_file:
      lkgr_lib.WriteLKGR(candidate, args.write_to_file, args.dry_run)

    if args.post:
      lkgr_lib.PostLKGR(
          config['status_url'], candidate, repo.keyfunc(candidate),
          config['source_vcs'], config['password_file'], args.dry_run)
      if config['update_recipients']:
        subject = 'Updated %s LKGR to %s' % (args.project, candidate)
        message = subject + '.\n'
        lkgr_lib.SendMail(config['update_recipients'],
                          subject, message, args.dry_run)

    if args.tag and config['source_vcs'] == 'git':
      lkgr_lib.UpdateTag(candidate, config['source_url'], args.dry_run)

  else:
    # No new LKGR found.
    LOGGER.info('Candidate is not newer than current %s LKGR.', args.project)

    if not args.manual and lkgr:
      rev_behind = repo.get_gap(revisions, lkgr)
      LOGGER.info('LKGR is %d revisions behind', rev_behind)

      if rev_behind > config['allowed_gap']:
        if args.email_errors:
          lkgr_lib.SendMail(
              config['error_recipients'],
              '%s LKGR (%s) > %s revisions behind' % (
                  args.project, lkgr, config['allowed_gap']),
              '\n'.join(lkgr_lib.RunLogger.log), args.dry_run)
        LOGGER.fatal('LKGR exceeds allowed gap (%s > %s)', rev_behind,
                     config['allowed_gap'])
        return 1

      time_behind = repo.get_lag(lkgr)
      LOGGER.info('LKGR is %s behind', time_behind)

      if not lkgr_lib.CheckLKGRLag(time_behind, rev_behind,
                                   config['allowed_lag'],
                                   config['allowed_gap']):
        if args.email_errors:
          lkgr_lib.SendMail(
              config['error_recipients'],
              '%s LKGR (%s) exceeds lag threshold' % (args.project, lkgr),
              '\n'.join(lkgr_lib.RunLogger.log), args.dry_run)
        LOGGER.fatal('LKGR exceeds lag threshold (%s > %s)', time_behind,
                     config['allowed_lag'])
        return 1

  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
