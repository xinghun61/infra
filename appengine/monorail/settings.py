# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Defines settings for monorail."""

import os
import re

from google.appengine.api import app_identity

from proto import project_pb2
from proto import site_pb2


# This file is divided into the following parts:
# 1. Settings you must edit before deploying your site.
# 2. Settings you would edit on certain occasions while maintaining your site.
# 3. Settings enable specific features.
# 4. Settings that you can usually leave as-is.

# TODO(jrobbins): Store these settings in the database and implement
# servlets for domain admins to edit them without needing to redeploy the
# app.


####
# Part 1: settings that you must edit before deploying your site.

# Email address that is offered to users who might need help using the tool.
feedback_email = 'jrobbins+monorail.feedback@chromium.org'

# For debugging when running in staging: send all outbound
# email to this address rather than to the actual address that
# it would normally be sent to.
send_all_email_to = 'jrobbins+all+%(user)s+%(domain)s@chromium.org'

# For debugging when running the dev server locally: send all outbound
# email to this address rather than to the actual address that
# it would normally be sent to.
send_dev_email_to = (send_all_email_to or
                     'jrobbins+dev+%(user)s+%(domain)s@chromium.org')

# User to send emails from Monorail as. The reply_to sections of emails will be
# set to appspotmail addresses.
# Note: If configuring a new monorail instance without DNS records and reserved
#       email addresses then setting these values to
#       'reply@${app_id}.appspotmail.com' and 'noreply@{app_id}.appspotmail.com'
#       is likely the best option.
send_email_as = 'monorail@chromium.org'
send_noreply_email_as = 'monorail+noreply@chromium.org'

# The default is to look for a database named "monorail" in replicas
# named "replica-00" .. "replica-09"
db_database_name = 'monorail'
db_replica_prefix = 'replica-'

# The number of logical database shards used.  Each replica is complete copy
# of the master, so any replica DB can answer queries about any logical shard.
num_logical_shards = 10

# "Learn more" link for the site home page
# TODO(agable): Update this when we have publicly visible documentation.
learn_more_link = None

# Site name, displayed above the search box on the site home page.
site_name = 'Monorail'

# Who is allowed to create new projects?  Set to ANYONE or ADMIN_ONLY.
project_creation_restriction = site_pb2.UserTypeRestriction.ADMIN_ONLY

# Default access level when creating a new project.
default_access_level = project_pb2.ProjectAccess.ANYONE

# Possible access levels to offer when creating a new project.
allowed_access_levels = [
    project_pb2.ProjectAccess.ANYONE,
    project_pb2.ProjectAccess.MEMBERS_ONLY]

# Who is allowed to create user groups?  Set to ANYONE or ADMIN_ONLY.
group_creation_restriction = site_pb2.UserTypeRestriction.ADMIN_ONLY

# Who is allowed to create hotlists? Set to ANYONE or ADMIN_ONLY.
hotlist_creation_restriction = site_pb2.UserTypeRestriction.ANYONE

# Text that mentions these words as shorthand host names will be autolinked
# regardless of the lack of "https://" or ".com".
autolink_shorthand_hosts = [
    'go', 'g', 'shortn', 'who', 'teams',
    ]
autolink_numeric_shorthand_hosts = [
    'b', 't', 'o', 'omg', 'cl', 'cr',
    ]


####
# Part 2: Settings you would edit on certain occasions.

# Read-only mode prevents changes while we make server-side changes.
read_only = False

# Timestamp used to notify users when the read only mode or other status
# described in the banner message takes effect.  It is
# expressed as a 5-tuple of ints: (year, month, day, hour, minute),
# e.g. (2009, 3, 20, 21, 45) represents March 20 2009 9:45PM.
banner_time = None

# Display a site maintenance banner on every monorail page.
banner_message = ''

# User accounts with email addresses at these domains are all banned.
banned_user_domains = []


####
# Part 3: Settings that enable specific features

# Enables "My projects" drop down menu
enable_my_projects_menu = True

# Enables stars in the UI for projects
enable_project_stars = True

# Enables stars in the UI for users
enable_user_stars = True

# Enable quick edit mode in issue peek dialog and show dialog on hover
enable_quick_edit = True


####
# Part 4: Settings that you can usually leave as-is.

# dev_mode makes the server slower and more dynamic for easier debugging.
# E.g., template files are reloaded on each request.
dev_mode = os.environ['SERVER_SOFTWARE'].startswith('Development')
unit_test_mode = os.environ['SERVER_SOFTWARE'].startswith('test')

# If we assume 1KB each, then this would be 400 MB for this cache in frontends
# that have only 1024 MB total.
issue_cache_max_size = 400 * 1000

# 150K users should be enough for all the frequent daily users plus the
# occasional users that are mentioned on any popular pages.
user_cache_max_size = 150 * 1000

# Recompute derived issue fields via work items rather than while
# the user is waiting for a page to load.
recompute_derived_fields_in_worker = True

# The issue search SQL queries have a LIMIT clause with this amount.
search_limit_per_shard = 10 * 1000  # This is more than all open in chromium.

# The GAE search feature is slow, so don't request too many results.
fulltext_limit_per_shard = 1 * 1000

# Retrieve at most this many issues from the DB when showing an issue grid.
max_issues_in_grid = 6000
# This is the most tiles that we show in grid view.  If the number of results
# is larger than this, we display IDs instead.
max_tiles_in_grid = 1000

# Maximum number of project results to display on a single pagination page
max_project_search_results_per_page = 100

# Maxium number of results per pagination page, regardless of what
# the user specified in his/her request.  This exists to prevent someone
# from doing a DoS attack that makes our servers do a huge amount of work.
max_artifact_search_results_per_page = 1000

# Maximum number of comments to display on a single pagination page
max_comments_per_page = 500

# Max number of issue starrers to notify via email.  Issues with more
# that this many starrers will only notify the last N of them after a
# comment from a project member.
max_starrers_to_notify = 4000

# In projects that have more than this many issues the next and prev
# links on the issue detail page will not be shown when the user comes
# directly to an issue without specifying any query terms.
threshold_to_suppress_prev_next = 10000

# Format string for the name of the FTS index shards for issues.
search_index_name_format = 'issues%02d'

# Name of the FTS index for projects (not sharded).
project_search_index_name = 'projects'

# Each backend has this many seconds to respond, otherwise frontend gives up
# on that shard.
backend_deadline = 45

# If the initial call to a backend fails, try again this many times.
# Initial backend calls are failfast, meaning that they fail immediately rather
# than queue behind other requests.  The last 2 retries will wait in queue.
backend_retries = 3

# Do various extra logging at INFO level.
enable_profiler_logging = False

# Mail sending domain.  Normally set this to None and it will be computed
# automatically from your AppEngine APP_ID. But, it can be overridden below.
mail_domain = None

# URL format to browse source code revisions.  This can be overridden
# in specific projects by setting project.revision_url_format.
# The format string may include "{revnum}" for the revision number.
revision_url_format = 'https://crrev.com/{revnum}'

# Users with emails in the priviledged domains see unobscured email addresses.
priviledged_user_domains = [
  'google.com', 'chromium.org', 'webrtc.org',
  ]

# Names of projects on code.google.com which we allow cross-linking to.
recognized_codesite_projects = [
  'chromium-os',
  'chrome-os-partner',
]

####
# Part 5:  Instance-specific settings that override lines above.

# We usually use a DB instance named "master" for writes.
db_master_name = 'master'
# This ID is for -staging and other misc deployments. Prod is defined below.
analytics_id = 'UA-55762617-20'

if unit_test_mode:
  db_cloud_project = ''  # No real database is used during unit testing.
else:
  app_id = app_identity.get_application_id()

  if app_id == 'monorail-staging':
    site_name = 'Monorail Staging'
    banner_message = 'This staging site does not send emails.'
    # The Google Cloud SQL databases to use.
    db_cloud_project = app_id
    db_replica_prefix = 'replica-9-'

  elif app_id == 'monorail-prod':
    send_all_email_to = None  # Deliver it to the intended users.
    # The Google Cloud SQL databases to use.
    db_cloud_project = app_id
    analytics_id = 'UA-55762617-14'

if dev_mode:
  site_name = 'Monorail Dev'
  num_logical_shards = 10

# Combine the customized info above to make the name of the master DB instance.
db_instance = db_cloud_project + ':' + db_master_name

# Format string for the name of the physical database replicas.
physical_db_name_format = db_cloud_project + ':' + db_replica_prefix + '%02d'

# preferred domains to display
preferred_domains = {
    'monorail-prod.appspot.com': 'bugs.chromium.org',
    'monorail-staging.appspot.com': 'bugs-staging.chromium.org'}

# Borg robot service account
borg_service_account = 'chrome-infra-prod-borg@system.gserviceaccount.com'

# Prediction API params.
classifier_project_id = 'project-id-testing-only'

# Necessary for tests.
if 'APPLICATION_ID' not in os.environ:
  os.environ['APPLICATION_ID'] = 'testing-app'

if dev_mode:
  # There is no local stub for ML Engine.
  classifier_project_id = 'monorail-staging'
else:
  classifier_project_id = app_identity.get_application_id()

classifier_model_id = '20170302'

# Number of distinct users who have to flag an issue before it
# is automatically removed as spam.
# 5 is an arbitrarily chosen value.  Set it to something really high
# to effectively disable spam flag threshhold checking.
spam_flag_thresh = 5

# If the classifier's confidence is less than this value, the
# item will show up in the spam moderation queue for manual
# review.
classifier_moderation_thresh = 1.0

# If the classifier's confidence is greater than this value,
# and the label is 'spam', the item will automatically be created
# with is_spam=True, and will be filtered out from search results.
classifier_spam_thresh = 0.995

# Users with email addresses ending with these will not be subject to
# spam filtering.
spam_whitelisted_suffixes = (
  '@chromium.org',
  '.gserviceaccount.com',
  '@google.com',
  '@webrtc.org',
)

# These email suffixes are allowed to create new alert bugs via email.
alert_whitelisted_suffixes = (
  '@google.com',
)

# The person who is notified if there is an unexpected problem in the alert
# pipeline.
alert_escalation_email = 'zhangtiff@google.com'

# Bugs autogenerated from alert emails are created through this account.
alert_service_account = 'chrome-trooper-alerts@google.com'

# The nubmer of hash buckets to use when vectorizing text from Issues and
# Comments. This should be the same value that the model was trained with.
spam_feature_hashes = 500

ratelimiting_enabled = False

# Enable cost-based rate limiting. This only applies if
# ratelimiting_enabled = True
ratelimiting_cost_enabled = True

# Requests that take longer than this are hit with extra
# counts added to their bucket at the end of the request.
ratelimiting_cost_thresh_ms = 2000

# Requests that hit ratelimiting_cost_thresh_sec get this
# extra amount added to their bucket at the end of the request.
ratelimiting_cost_penalty = 1

api_ratelimiting_enabled = False

# Enable cost-based api rate limiting. This only applies if
# api_ratelimiting_enabled = True
api_ratelimiting_cost_enabled = True

# API requests that take longer than this are hit with extra
# counts added to their bucket at the end of the request.
api_ratelimiting_cost_thresh_ms = 5000

# API requests that hit ratelimiting_cost_thresh_sec get this
# extra amount added to their bucket at the end of the request.
api_ratelimiting_cost_penalty = 1

# When we post an auto-ping comment, it is posted by this user @ the preferred
# domain name.  E.g., 'monorail@bugs.chromium.org'.
date_action_ping_author = 'monorail'
