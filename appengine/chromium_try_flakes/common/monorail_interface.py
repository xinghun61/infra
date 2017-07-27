# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
import urllib2

from monorail_api import IssueTrackerAPI, Issue as MonorailIssue

PROJECT_CONFIG = {
    'chromium': {
        'monorail_project': 'chromium',
        'queue_label': 'Sheriff-Chromium',
    },
    'webrtc': {
        'monorail_project': 'webrtc',
        'queue_label': 'Sheriff-WebRTC',
    },
}

SUMMARY_TEMPLATE = (
    'New flaky failures have been detected for %(flake_types_count)d flake '
    'types.'
)
# TODO(ehmaldonado): Put a real URL below
RECENT_FLAKES_URL_TEMPLATE = (
    'http://fake_url/recent_flakes'
    '?project=%(project)s'
    '&step_name=%(step_name)s'
    '&test_name=%(test_name)s'
    '&config=%(config)s'
    # Highlight the last |highlight| flaky failures...
    '&highlight=%(highlight)s'
    # ... updated before the |updated_before| timestamp.
    '&updated_before=%(updated_before)s'
)
FLAKE_TYPE_DESCRIPTION_TEMPLATE = (
    '  Step Name:      %(step_name)s\n'
    '  Test Name:      %(test_name)s\n'
    '  Config:         %(config)s\n'
)
FLAKE_INFO_DESCRIPTION_TEMPLATE = (
    '%(flakes_count)d new flaky failures for:\n'
    '%(flake_type_description)s'
    'To see them point your browser to:\n'
    '  %(recent_flakes_url)s\n'
)
NEW_FLAKES_DESCRIPTION_TEMPLATE = (
    'We have detected %(new_flakes_count)d recent flakes for the following '
    'flake types:\n\n'
    '%(flake_types_description)s\n'
)
# TODO(ehmaldonado): Put a real URL below
NEW_ISSUE_TEMPLATE = (
    '%(summary)s\n\n'
    'This issue was created automatically by the chromium-try-flakes app. '
    'Please find the right owner to fix the respective test/step and assign '
    'this issue to them.\n\n'
    '%(new_flakes_description)s\n'
    'The mapping of issues to flake types can be edited at [Generic URL where '
    'the user can look for the issue, since we dont know issue number yet].\n\n'
)
# TODO(ehmaldonado): Put a real URL below
RECREATE_ISSUE_TEMPLATE = (
    '%(summary)s\n\n'
    'This issue was created automatically by the chromium-try-flakes app. '
    'Please find the right owner to fix the respective test/step and assign '
    'this issue to them.\n\n'
    '%(flake_types_description)s\n'
    'The mapping of issues to flake types can be edited at [Generic URL where '
    'the user can look for the issue, since we dont know issue number yet].\n\n'
    'This issue was re-created after issue %(old_issue_id)s was closed.\n\n'
)
# TODO(ehmaldonado): Put a real URL below
ISSUE_IS_NOW_USED_BY_CHROMIUM_TRY_FLAKES_NOTICE = (
    'This issue is now used by Chromium Try Flakes to track the following '
    'flake types:\n\n'
    '%(flake_types_description)s\n'
    'The mapping of issues to flake types can be edited at [Generic URL where '
    'the user can look for the issue, since we dont know issue number yet].\n\n'
)
FLAKY_RUNS_TEMPLATE = (
    '%(new_flakes_count)s flaky runs have been detected.'
)
DAYS_TO_REOPEN_ISSUE = 3


def _get_flake_type_description(flake_type):
  return FLAKE_TYPE_DESCRIPTION_TEMPLATE % {
      'step_name': flake_type.step_name,
      'test_name': flake_type.test_name,
      'config': flake_type.config,
  }

def _get_flake_info_description(flake_info):
  last_updated_timestamp = str(calendar.timegm(
      flake_info.flake_type.last_updated.utctimetuple()))
  recent_flakes_url = RECENT_FLAKES_URL_TEMPLATE % {
      'project': urllib2.quote(flake_info.flake_type.project),
      'step_name': urllib2.quote(flake_info.flake_type.step_name),
      'test_name': urllib2.quote(flake_info.flake_type.test_name or ''),
      'config': urllib2.quote(flake_info.flake_type.config or ''),
      'highlight': urllib2.quote(str(flake_info.flakes_count)),
      'updated_before': urllib2.quote(last_updated_timestamp),
  }
  flake_type_description = _get_flake_type_description(flake_info.flake_type)

  return FLAKE_INFO_DESCRIPTION_TEMPLATE % {
      'flakes_count': flake_info.flakes_count,
      'flake_type_description': flake_type_description,
      'recent_flakes_url': recent_flakes_url,
  }


def _get_new_flakes_description(flake_infos):
  flakes_count = sum(flake_info.flakes_count for flake_info in flake_infos)

  flake_types_description = '\n'.join(
      _get_flake_info_description(flake_info)
      for flake_info in flake_infos)

  return NEW_FLAKES_DESCRIPTION_TEMPLATE % {
      'new_flakes_count': flakes_count,
      'flake_types_description': flake_types_description,
  }


def follow_duplication_chain(project, issue_id):
  seen_issues = []
  # TODO(sergiyb): Pass api from the caller instead of creating it here. Also
  # make sure to pass in use_staging=True for staging version of the app.
  api = IssueTrackerAPI(PROJECT_CONFIG[project]['monorail_project'])
  current_issue = api.getIssue(issue_id, project)
  # We need to check both status and merged_into, since it's possible to
  # create an issue with Duplicate status but without merged_into field set
  # and vice versa (see http://crbug.com/669054 and http://crbug.com/669056).
  while current_issue.status == 'Duplicate' and current_issue.merged_into:
    seen_issues.append(current_issue.id)
    if current_issue.merged_into in seen_issues:
      return None
    current_issue = api.getIssue(current_issue.merged_into,
                                 current_issue.merged_into_project)
  return current_issue


def recreate_issue(project, old_issue_id, flake_types):
  # TODO(sergiyb): Pass api from the caller instead of creating it here. Also
  # make sure to pass in use_staging=True for staging version of the app.
  api = IssueTrackerAPI(PROJECT_CONFIG[project]['monorail_project'])

  summary = SUMMARY_TEMPLATE % {'flake_types_count': len(flake_types)}

  flake_types_description = '\n'.join(_get_flake_type_description(flake_type)
                                      for flake_type in flake_types)

  description = RECREATE_ISSUE_TEMPLATE % {
      'summary': summary,
      'flake_types_description': flake_types_description,
      'old_issue_id': old_issue_id,
  }

  queue_label = PROJECT_CONFIG[project]['queue_label']
  labels = ['Type-Bug', 'Pri-1', 'Via-TryFlakes', queue_label]

  new_issue = api.create(MonorailIssue({
      'summary': summary,
      'description': description,
      'status': 'Untriaged',
      'labels': labels,
      'components': ['Tests>Flaky']
  }))

  return new_issue.id


def post_notice(project, issue_id, flake_types):
  # TODO(sergiyb): Pass api from the caller instead of creating it here. Also
  # make sure to pass in use_staging=True for staging version of the app.
  api = IssueTrackerAPI(PROJECT_CONFIG[project]['monorail_project'])
  # TODO(ehmaldonado): Add logic to re-add the queue label if not present.
  flake_types_description = '\n'.join(_get_flake_type_description(flake_type)
                                      for flake_type in flake_types)
  comment = ISSUE_IS_NOW_USED_BY_CHROMIUM_TRY_FLAKES_NOTICE % {
      'flake_types_description': flake_types_description,
  }
  api.postComment(issue_id, comment)


def create_issue(project, new_flake_infos):
  # TODO(sergiyb): Pass api from the caller instead of creating it here. Also
  # make sure to pass in use_staging=True for staging version of the app.
  api = IssueTrackerAPI(PROJECT_CONFIG[project]['monorail_project'])

  summary = SUMMARY_TEMPLATE % {'flake_types_count': len(new_flake_infos)}

  description = NEW_ISSUE_TEMPLATE % {
      'summary': summary,
      'new_flakes_description': _get_new_flakes_description(new_flake_infos)
  }

  queue_label = PROJECT_CONFIG[project]['queue_label']
  labels = ['Type-Bug', 'Pri-1', 'Via-TryFlakes', queue_label]

  new_issue = api.create(MonorailIssue({
      'summary': summary,
      'description': description,
      'status': 'Untriaged',
      'labels': labels,
      'components': ['Tests>Flaky']
  }))

  return new_issue.id


def update_issue(project, issue_id, new_flakes):
  # TODO(sergiyb): Pass api from the caller instead of creating it here. Also
  # make sure to pass in use_staging=True for staging version of the app.
  api = IssueTrackerAPI(PROJECT_CONFIG[project]['monorail_project'])
  # TODO(ehmaldonado): Add logic to re-add the queue label if not present.
  comment = _get_new_flakes_description(new_flakes)
  api.postComment(issue_id, comment)
