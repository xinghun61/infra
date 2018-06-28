# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Constants that define the Monorail URL space."""

# URLs of site-wide Monorail pages
HOSTING_HOME = '/hosting/'  # the big search box w/ popular labels
PROJECT_CREATE = '/hosting/createProject'
USER_SETTINGS = '/hosting/settings'
PROJECT_MOVED = '/hosting/moved'
CHECK_PROJECT_NAME_JSON = '/hosting/createProject/checkProjectName'
GROUP_LIST = '/g/'
GROUP_CREATE = '/hosting/createGroup'
GROUP_DELETE = '/hosting/deleteGroup'
UPDATE_ISSUES_IN_HOTLISTS = '/hosting/updateHotlists'

# URLs of project pages
SUMMARY = '/'  # Now just a redirect to /issues/list
UPDATES_LIST = '/updates/list'
PEOPLE_LIST = '/people/list'
PEOPLE_DETAIL = '/people/detail'
PEOPLE_DETAIL_PREFS_JSON = '/people/detailPrefs'
ADMIN_META = '/admin'
ADMIN_ADVANCED = '/adminAdvanced'

# URLs for stars
STARS_JSON = '/hosting/stars'

# URLs for cue cards (dismissible on-page help)
CUES_JSON = '/hosting/cues'

# URLs of user pages, relative to either /u/userid or /u/username
# TODO(jrobbins): Add /u/userid as the canonical URL in metadata.
USER_PROFILE = '/'
USER_PROFILE_POLYMER = '/polymer'
USER_CLEAR_BOUNCING = '/clearBouncing'
BAN_USER = '/ban'
BAN_SPAMMER = '/banSpammer'

# URLs for User Updates pages
USER_UPDATES_PROJECTS = '/updates/projects'
USER_UPDATES_DEVELOPERS = '/updates/developers'
USER_UPDATES_MINE = '/updates'

# URLs of user group pages, relative to /g/groupname.
GROUP_DETAIL = '/'
GROUP_ADMIN = '/groupadmin'

# URL of JSON feed for the "My projects" menu
USER_PROJECTS_JSON = '/hosting/projects'

# URLs of issue tracker backend request handlers.  Called from the frontends.
BACKEND_SEARCH = '/_backend/search'
BACKEND_NONVIEWABLE = '/_backend/nonviewable'

# URLs of task queue request handlers.  Called asynchronously from frontends.
RECOMPUTE_DERIVED_FIELDS_TASK = '/_task/recomputeDerivedFields'
NOTIFY_ISSUE_CHANGE_TASK = '/_task/notifyIssueChange'
NOTIFY_BLOCKING_CHANGE_TASK = '/_task/notifyBlockingChange'
NOTIFY_BULK_CHANGE_TASK = '/_task/notifyBulkEdit'
NOTIFY_APPROVAL_CHANGE_TASK = '/_task/notifyApprovalChange'
OUTBOUND_EMAIL_TASK = '/_task/outboundEmail'
SPAM_DATA_EXPORT_TASK = '/_task/spamDataExport'
BAN_SPAMMER_TASK = '/_task/banSpammer'
ISSUE_DATE_ACTION_TASK = '/_task/issueDateAction'
COMPONENT_DATA_EXPORT_TASK = '/_task/componentDataExportTask'

# URLs of cron job request handlers.  Called from GAE via cron.yaml.
REINDEX_QUEUE_CRON = '/_cron/reindexQueue'
RAMCACHE_CONSOLIDATE_CRON = '/_cron/ramCacheConsolidate'
REAP_CRON = '/_cron/reap'
SPAM_DATA_EXPORT_CRON = '/_cron/spamDataExport'
LOAD_API_CLIENT_CONFIGS_CRON = '/_cron/loadApiClientConfigs'
TRIM_VISITED_PAGES_CRON = '/_cron/trimVisitedPages'
DATE_ACTION_CRON = '/_cron/dateAction'
SPAM_TRAINING_CRON = '/_cron/spamTraining'
COMPONENT_DATA_EXPORT_CRON = '/_cron/componentDataExport'
COMMIT_DATA_CRON = '/_cron/getCommitsCron'

# URLs of handlers needed for GAE instance management.
WARMUP = '/_ah/warmup'

# URLs of User pages
SAVED_QUERIES = '/queries'
DASHBOARD = '/dashboard'
HOTLISTS = '/hotlists'

# URLS of User hotlist pages
HOTLIST_ISSUES = ''
HOTLIST_ISSUES_CSV = '/csv'
HOTLIST_PEOPLE = '/people'
HOTLIST_DETAIL = '/details'
HOTLIST_RERANK_JSON = '/rerank'
HOTLIST_NEW_NOTES_JSON = '/updatenote'

# URL of JSON feed for the "My hotlists" menu
USER_HOTLISTS_JSON = '/hosting/hotlists'

# URLs of issue tracker project pages
ISSUE_APPROVAL = '/issues/approval'
ISSUE_LIST = '/issues/list'
ISSUE_DETAIL = '/issues/detail'
ISSUE_DETAIL_FLIPPER_NEXT = '/issues/detail/next'
ISSUE_DETAIL_FLIPPER_PREV = '/issues/detail/previous'
ISSUE_DETAIL_FLIPPER_INDEX = '/issues/detail/flipper'
ISSUE_PEEK = '/issues/peek'  # not served, only used in issuepeek.py
ISSUE_COMMENT_DELETION_JSON = '/issues/delComment'
ISSUE_ATTACHMENT_DELETION_JSON = '/issues/delAttachment'
ISSUE_FLAGSPAM_JSON = '/issues/flagspam'
ISSUE_SETSTAR_JSON = '/issues/setstar'
ISSUE_DELETE_JSON = '/issues/delete'
ISSUE_PRESUBMIT_JSON = '/issues/presubmit'
ISSUE_ENTRY = '/issues/entry'
ISSUE_ENTRY_AFTER_LOGIN = '/issues/entryafterlogin'
ISSUE_OPTIONS_JSON = '/feeds/issueOptions'
ISSUE_OPTIONS_MEMBERS_JSON = '/feeds/issueOptionsMembers'
ISSUE_BULK_EDIT = '/issues/bulkedit'
ISSUE_ADVSEARCH = '/issues/advsearch'
ISSUE_TIPS = '/issues/searchtips'
ISSUE_ATTACHMENT = '/issues/attachment'
ISSUE_ATTACHMENT_TEXT = '/issues/attachmentText'
ISSUE_LIST_CSV = '/issues/csv'
COMPONENT_CHECKNAME_JSON = '/components/checkName'
COMPONENT_CREATE = '/components/create'
COMPONENT_DETAIL = '/components/detail'
FIELD_CHECKNAME_JSON = '/fields/checkName'
FIELD_CREATE = '/fields/create'
FIELD_DETAIL = '/fields/detail'
TEMPLATE_CREATE ='/templates/create'
TEMPLATE_DETAIL = '/templates/detail'
WIKI_LIST = '/w/list'  # Wiki urls are just redirects to project.docs_url
WIKI_PAGE = '/wiki/<wiki_page:.*>'
SOURCE_PAGE = '/source/<source_page:.*>'
ADMIN_INTRO = '/adminIntro'
# TODO(jrobbins): move some editing from /admin to /adminIntro.
ADMIN_COMPONENTS = '/adminComponents'
ADMIN_LABELS = '/adminLabels'
ADMIN_RULES = '/adminRules'
ADMIN_TEMPLATES = '/adminTemplates'
ADMIN_STATUSES = '/adminStatuses'
ADMIN_VIEWS = '/adminViews'
ADMIN_EXPORT = '/projectExport'
ADMIN_EXPORT_JSON = '/projectExport/json'
ISSUE_ORIGINAL = '/issues/original'
ISSUE_REINDEX = '/issues/reindex'
ISSUE_EXPORT = '/issues/export'
ISSUE_EXPORT_JSON = '/issues/export/json'
ISSUE_IMPORT = '/issues/import'
ISSUE_RERANK_BLOCKED_ON = '/issues/rerankBlockedOn'
COMPONENT_SUGGESTION = '/suggest/component'
COMPONENT_LOG = '/suggest/componentlog'

# URLs for hotlist features
HOTLIST_CREATE = '/hosting/createHotlist'

# URLs of site-wide pages referenced from the framework directory.
CAPTCHA_QUESTION = '/hosting/captcha'
EXCESSIVE_ACTIVITY = '/hosting/excessiveActivity'
BANNED = '/hosting/noAccess'
NONPROJECT_COLLISION = '/hosting/collision'
# This is for collisions that happen within a project, based at /p/projectname
ARTIFACT_COLLISION = '/collision'
CLIENT_MON = '/_/clientmon'

CSP_REPORT = '/csp'
TOKEN_REFRESH = '/hosting/tokenRefresh'

SPAM_MODERATION_QUEUE = '/spamqueue'
SNAPSHOT_COUNTS = '/feeds/snapshotCounts'
