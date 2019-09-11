# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Defines settings for monorail."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import os
import re

from google.appengine.api import app_identity

from framework import framework_constants
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
send_all_email_to = 'monorail-staging-emails+all+%(user)s+%(domain)s@google.com'

# For debugging when running the server locally: send all outbound
# email to this address rather than to the actual address that
# it would normally be sent to.
send_local_email_to = (
    send_all_email_to or
    'monorail-staging-emails+dev+%(user)s+%(domain)s@google.com')

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
# Replica names for -prod, -staging, and -dev may diverge if replicas ever fail.
# In such cases the db_replica_names list can be overwritten in Part 5.
db_database_name = 'monorail'
db_master_name = 'master-g2'
db_replica_names = [
        'replica-g2-00', 'replica-g2-01', 'replica-g2-02', 'replica-g2-03',
        'replica-g2-04', 'replica-g2-05', 'replica-g2-06', 'replica-g2-07',
        'replica-g2-08', 'replica-g2-09']
db_region = 'us-central1'

# The default connection pool size for mysql connections.
db_cnxn_pool_size = 5

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


# We only allow self-service account linking invites when the child account is
# linking to a parent account in an allowed domain.
linkable_domains = {
  # Child account domain: [parent account domains]
  'chromium.org': ['google.com'],
  'google.com': ['chromium.org'],
  # TODO(jrobbins): webrtc.org, etc.
}


####
# Part 2: Settings you would edit on certain occasions.

# Read-only mode prevents changes while we make server-side changes.
read_only = False

# Timestamp used to notify users when the read only mode or other status
# described in the banner message takes effect.  It is
# expressed as a tuple of ints: (year, month, day[, hour[, minute[, second]]])
# e.g. (2009, 3, 20, 21, 45) represents March 20 2009 9:45PM UTC.
banner_time = None

# Display a site maintenance banner on every monorail page.
banner_message = ''

# User accounts with email addresses at these domains are all banned.
banned_user_domains = []

# We only send subscription notifications to users who have visited the
# site in the last 6 months.
subscription_timeout_secs = 180 * framework_constants.SECS_PER_DAY

# Location of GCS spam classification staging trainer. Whenever the training
# code is changed, this should be updated to point to the new package.
trainer_staging = ('gs://monorail-staging-mlengine/spam_trainer_1517870972/'
                   'packages/befc9b29d9beb7e89d509bd1e9866183c138e3a32317cc'
                   'e253342ac9f8e7c375/trainer-0.1.tar.gz')

# Location of GCS spam classification prod trainer. Whenever the training
# code is changed, this should be updated to point to the new package.
trainer_prod = ('gs://monorail-prod-mlengine/spam_trainer_1521755738/packages/'
                '3339dfcb5d7b6c9d714fb9b332fd72d05823e9a1850ceaf16533a6124bcad'
                '6fd/trainer-0.1.tar.gz')
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

# local_mode makes the server slower and more dynamic for easier debugging.
# E.g., template files are reloaded on each request.
local_mode = os.environ['SERVER_SOFTWARE'].startswith('Development')
unit_test_mode = os.environ['SERVER_SOFTWARE'].startswith('test')

# If we assume 1KB each, then this would be 400 MB for this cache in frontends
# that have only 1024 MB total.
issue_cache_max_size = 400 * 1000

# If we assume 1KB each, then this would be 400 MB for this cache in frontends
# that have only 1024 MB total.
comment_cache_max_size = 400 * 1000

# 150K users should be enough for all the frequent daily users plus the
# occasional users that are mentioned on any popular pages.
user_cache_max_size = 150 * 1000

# Normally we use the default namespace, but during development it is
# sometimes useful to run a tainted version on staging that has a separate
# memcache namespace.  E.g., os.environ.get('CURRENT_VERSION_ID')
memcache_namespace = None  # Should be None when committed.

# Recompute derived issue fields via work items rather than while
# the user is waiting for a page to load.
recompute_derived_fields_in_worker = True

# The issue search SQL queries have a LIMIT clause with this amount.
search_limit_per_shard = 10 * 1000  # This is more than all open in chromium.

# The GAE search feature is slow, so don't request too many results.
# This limit is approximately the most results that we can get from
# the fulltext engine in 1s.  If we reach this limit in any shard,
# the user will see a message explaining that results were capped.
fulltext_limit_per_shard = 1 * 2000

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
enable_profiler_logging = True

# Mail sending domain.  Normally set this to None and it will be computed
# automatically from your AppEngine APP_ID. But, it can be overridden below.
mail_domain = None

# URL format to browse source code revisions.  This can be overridden
# in specific projects by setting project.revision_url_format.
# The format string may include "{revnum}" for the revision number.
revision_url_format = 'https://crrev.com/{revnum}'

# Users with emails in the "priviledged" domains do NOT get any advantage
# but they do default their preference to show unobscured email addresses.
priviledged_user_domains = [
  'google.com', 'chromium.org', 'webrtc.org',
  ]

# Branded domains:  Any UI GET to a project listed below on prod or staging
# should have the specified host, otherwise it will be redirected such that
# the specified host is used.
branded_domains_prod = {
  'fuchsia': 'bugs.fuchsia.dev',
  '*': 'bugs.chromium.org',
  }
branded_domains_staging = {
  'fuchsia': 'bugs-staging.fuchsia.dev',
  '*': 'bugs-staging.chromium.org',
  }
branded_domains = {}  # empty for dev

# The site home page will immediately redirect to a default project for these
# domains, if the project can be viewed.  Structure is {hostport: project_name}.
domain_to_default_project = {}  # empty for dev and localhost
domain_to_default_project_prod = {'bugs.fuchsia.dev': 'fuchsia'}
domain_to_default_project_staging = {'bugs-staging.fuchsia.dev': 'fuchsia'}


# Names of projects on code.google.com which we allow cross-linking to.
recognized_codesite_projects = [
  'chromium-os',
  'chrome-os-partner',
]

####
# Part 5:  Instance-specific settings that override lines above.
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
    branded_domains = branded_domains_staging
    domain_to_default_project = domain_to_default_project_staging

  elif app_id == 'monorail-dev':
    site_name = 'Monorail Dev'
    banner_message = 'This dev site does not send emails.'
    # The Google Cloud SQL databases to use.
    db_cloud_project = app_id

  elif app_id == 'monorail-prod':
    send_all_email_to = None  # Deliver it to the intended users.
    # The Google Cloud SQL databases to use.
    db_cloud_project = app_id
    analytics_id = 'UA-55762617-14'
    branded_domains = branded_domains_prod
    domain_to_default_project = domain_to_default_project_prod

if local_mode:
  site_name = 'Monorail Local'
  num_logical_shards = 10

# Combine the customized info above to make the name of the master DB instance.
db_instance = db_cloud_project + ':' + db_region + ':' + db_master_name

# Format string for the name of the physical database replicas.
physical_db_name_format = (db_cloud_project + ':' + db_region + ':%s')

# preferred domains to display
preferred_domains = {
    'monorail-prod.appspot.com': 'bugs.chromium.org',
    'monorail-staging.appspot.com': 'bugs-staging.chromium.org',
    'monorail-dev.appspot.com': 'bugs-dev.chromium.org'}

# Borg robot service account
borg_service_account = 'chrome-infra-prod-borg@system.gserviceaccount.com'

# Prediction API params.
classifier_project_id = 'project-id-testing-only'

# Necessary for tests.
if 'APPLICATION_ID' not in os.environ:
  os.environ['APPLICATION_ID'] = 'testing-app'

if local_mode:
  # There is no local stub for ML Engine.
  classifier_project_id = 'monorail-staging'
else:
  classifier_project_id = app_identity.get_application_id()

classifier_model_id = '20170302'

# Number of distinct users who have to flag an issue before it
# is automatically removed as spam.
# Currently effectively disabled.
spam_flag_thresh = 1000

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

# These users default to getting a UX that is more similar to
# corporate systems that they are familiar with.
corp_mode_user_groups = [
  'chromeos-all@google.com',
  'chromeos-acl@google.com',
  'chromeos-fte-tvc@google.com',
  'create-team@google.com',
  'test-corp-mode@google.com',
  ]

# These email suffixes are allowed to create new alert bugs via email.
alert_whitelisted_suffixes = (
  '@google.com',
)

# The person who is notified if there is an unexpected problem in the alert
# pipeline.
alert_escalation_email = 'zhangtiff@google.com'

# Bugs autogenerated from alert emails are created through this account.
alert_service_account = 'chrome-trooper-alerts@google.com'

# The number of hash buckets to use when vectorizing text from Issues and
# Comments. This should be the same value that the model was trained with.
spam_feature_hashes = 500

# The number of features to use when vectorizing text from Issues and
# Comments. This should be the same value that the model was trained with.
component_features = 5000

# The name of the spam model in ML Engine.
spam_model_name = 'spam_only_words'

# The name of the component model in ML Engine
component_model_name = 'component_top_words'

# The name of the gcs bucket containing component predicition trainer code.
component_ml_bucket = classifier_project_id + '-mlengine'

ratelimiting_enabled = False

# Requests that hit ratelimiting_cost_thresh_sec get one extra count
# added to their bucket at the end of the request for each additional
# multiple of this latency.
ratelimiting_ms_per_count = 1000

api_ratelimiting_enabled = True

# When we post an auto-ping comment, it is posted by this user @ the preferred
# domain name.  E.g., 'monorail@bugs.chromium.org'.
date_action_ping_author = 'monorail'

# Hard-coding this so that we don't rely on sys.maxint, which could
# potentially differ. It is equal to the maximum unsigned 32 bit integer,
# because the `int(10) unsigned` column type in MySQL is 32 bits.
maximum_snapshot_period_end = 4294967295

# Percent of requests to report to cloud tracing.
trace_fraction = 0.1

# The maximum number of rows chart queries can scan.
chart_query_max_rows = 10000

# Client ID to use for loading the Google API client, gapi.js.
if app_identity.get_application_id() == 'monorail-prod':
  gapi_client_id = (
    '679746765624-tqaakho939p2mc7eb65t4ecrj3gj08rt.apps.googleusercontent.com')
else:
  gapi_client_id = (
    '52759169022-6918fl1hd1qoul985cs1ohgedeb8c9a0.apps.googleusercontent.com')
