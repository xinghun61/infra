# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""This file sets up all the urls for monorail pages."""

import logging

import webapp2

import settings

from features import autolink
from features import dateaction
from features import banspammer
from features import hotlistcreate
from features import hotlistdetails
from features import hotlistissues
from features import hotlistissuescsv
from features import hotlistpeople
from features import filterrules
from features import userhotlists
from features import inboundemail
from features import notify
from features import rerankhotlist
from features import savedqueries
from features import spammodel
from features import spamtraining
from features import componentexport

from framework import artifactcollision
from framework import banned
from framework import clientmon
from framework import csp_report
from framework import excessiveactivity
from framework import trimvisitedpages
from framework import framework_bizobj
from framework import reap
from framework import registerpages_helpers
from framework import ts_mon_js
from framework import urls
from framework import warmup

from project import peopledetail
from project import peoplelist
from project import projectadmin
from project import projectadminadvanced
from project import projectexport
from project import projectsummary
from project import projectupdates
from project import redirects

from search import backendnonviewable
from search import backendsearch

from services import cachemanager_svc
from services import client_config_svc

from sitewide import custom_404
from sitewide import groupadmin
from sitewide import groupcreate
from sitewide import groupdetail
from sitewide import grouplist
from sitewide import hostinghome
from sitewide import moved
from sitewide import projectcreate
from sitewide import userprofile
from sitewide import usersettings
from sitewide import userclearbouncing
from sitewide import userupdates
from sitewide import usercommits

from tracker import componentcreate
from tracker import componentdetail
from tracker import fieldcreate
from tracker import fielddetail
from tracker import issueapproval
from tracker import issueadmin
from tracker import issueadvsearch
from tracker import issueattachment
from tracker import issueattachmenttext
from tracker import issuebulkedit
from tracker import issuedetail
from tracker import issueentry
from tracker import issueentryafterlogin
from tracker import issueexport
from tracker import issueimport
from tracker import issuelist
from tracker import issuelistcsv
from tracker import issueoriginal
from tracker import issuereindex
from tracker import issuetips
from tracker import spam
from tracker import templatecreate
from tracker import templatedetail

from api import api_service


class ServletRegistry(object):

  _PROJECT_NAME_REGEX = r'[a-z0-9][-a-z0-9]*[a-z0-9]'
  _USERNAME_REGEX = r'[-+\w=.%]+(@([-a-z0-9]+\.)*[a-z0-9]+)?'
  _HOTLIST_ID_NAME_REGEX = r'\d+|[a-zA-Z][-0-9a-zA-Z\.]*'

  def __init__(self):
    self.routes = []

  def _AddRoute(self, path_regex, servlet_class, method, does_write=False):
    """Add a GET or POST handler to our webapp2 route list.

    Args:
      path_regex: string with webapp2 URL template regex.
      servlet_class: a subclass of class Servlet.
      method: string 'GET' or 'POST'.
      does_write: True if the servlet could write to the database, we skip
          registering such servlets when the site is in read_only mode. GET
          handlers never write. Most, but not all, POST handlers do write.
    """
    if settings.read_only and does_write:
      logging.info('Not registring %r because site is read-only', path_regex)
      # TODO(jrobbins): register a helpful error page instead.
    else:
      self.routes.append(
          webapp2.Route(path_regex, handler=servlet_class, methods=[method]))

  def _SetupServlets(self, spec_dict, base='', post_does_write=True):
    """Register each of the given servlets."""
    for get_uri, servlet_class in spec_dict.items():
      self._AddRoute(base + get_uri, servlet_class, 'GET')
      post_uri = get_uri + ('edit.do' if get_uri.endswith('/') else '.do')
      self._AddRoute(base + post_uri, servlet_class, 'POST',
                     does_write=post_does_write)

  def _SetupProjectServlets(self, spec_dict, post_does_write=True):
    """Register each of the given servlets in the project URI space."""
    self._SetupServlets(
        spec_dict, base='/p/<project_name:%s>' % self._PROJECT_NAME_REGEX,
        post_does_write=post_does_write)

  def _SetupUserServlets(self, spec_dict, post_does_write=True):
    """Register each of the given servlets in the user URI space."""
    self._SetupServlets(
        spec_dict, base='/u/<viewed_username:%s>' % self._USERNAME_REGEX,
        post_does_write=post_does_write)

  def _SetupGroupServlets(self, spec_dict, post_does_write=True):
    """Register each of the given servlets in the user group URI space."""
    self._SetupServlets(
        spec_dict, base='/g/<viewed_username:%s>' % self._USERNAME_REGEX,
        post_does_write=post_does_write)

  def _SetupUserHotlistServlets(self, spec_dict, post_does_write=True):
    """ Register given user hotlist servlets in the user URI space."""
    self._SetupServlets(
        spec_dict,
        base ='/u/<viewed_username:%s>/hotlists/<hotlist_id:%s>'
        % (self._USERNAME_REGEX, self._HOTLIST_ID_NAME_REGEX),
        post_does_write=post_does_write)

  def Register(self, services):
    """Register all the monorail request handlers."""
    self._RegisterFrameworkHandlers()
    self._RegisterSitewideHandlers()
    self._RegisterProjectHandlers()
    self._RegisterIssueHandlers()
    self._RegisterRedirects()
    self._RegisterInboundMail()
    api_service.RegisterApiHandlers(self, services)
    autolink.RegisterAutolink(services)
    # Error pages should be the last to register.
    self._RegisterErrorPages()
    logging.info('Finished registering monorail handlers.')
    return self.routes

  def _RegisterProjectHandlers(self):
    """Register page and form handlers that operate within a project."""
    self._SetupProjectServlets({
        urls.ADMIN_INTRO: projectsummary.ProjectSummary,
        urls.PEOPLE_LIST: peoplelist.PeopleList,
        urls.PEOPLE_DETAIL: peopledetail.PeopleDetail,
        urls.PEOPLE_DETAIL_PREFS_JSON: peopledetail.PagePrefs,
        urls.UPDATES_LIST: projectupdates.ProjectUpdates,
        urls.ADMIN_META: projectadmin.ProjectAdmin,
        urls.ADMIN_ADVANCED: projectadminadvanced.ProjectAdminAdvanced,
        urls.ADMIN_EXPORT: projectexport.ProjectExport,
        urls.ADMIN_EXPORT_JSON: projectexport.ProjectExportJSON,
        })

  def _RegisterIssueHandlers(self):
    """Register page and form handlers for the issue tracker."""
    self._SetupServlets({
        # Note: there is both a site-wide and per-project issue list.
        urls.ISSUE_LIST: issuelist.IssueList,

        # Note: the following are at URLs that are not externaly accessible.
        urls.BACKEND_SEARCH: backendsearch.BackendSearch,
        urls.BACKEND_NONVIEWABLE: backendnonviewable.BackendNonviewable,
        urls.RECOMPUTE_DERIVED_FIELDS_TASK:
            filterrules.RecomputeDerivedFieldsTask,
        urls.REINDEX_QUEUE_CRON: filterrules.ReindexQueueCron,
        urls.NOTIFY_ISSUE_CHANGE_TASK: notify.NotifyIssueChangeTask,
        urls.NOTIFY_BLOCKING_CHANGE_TASK: notify.NotifyBlockingChangeTask,
        urls.NOTIFY_BULK_CHANGE_TASK: notify.NotifyBulkChangeTask,
        urls.NOTIFY_APPROVAL_CHANGE_TASK: notify.NotifyApprovalChangeTask,
        urls.OUTBOUND_EMAIL_TASK: notify.OutboundEmailTask,
        urls.SPAM_DATA_EXPORT_TASK: spammodel.TrainingDataExportTask,
        urls.DATE_ACTION_CRON: dateaction.DateActionCron,
        urls.SPAM_TRAINING_CRON: spamtraining.TrainSpamModelCron,
        urls.ISSUE_DATE_ACTION_TASK: dateaction.IssueDateActionTask,
        urls.COMPONENT_DATA_EXPORT_CRON:
          componentexport.ComponentTrainingDataExport,
        urls.COMPONENT_DATA_EXPORT_TASK:
          componentexport.ComponentTrainingDataExportTask,
        urls.COMMIT_DATA_CRON: usercommits.GetCommitsCron
        })

    self._SetupProjectServlets({
        urls.ISSUE_APPROVAL: issueapproval.IssueApproval,
        urls.ISSUE_LIST: issuelist.IssueList,
        urls.ISSUE_LIST_CSV: issuelistcsv.IssueListCsv,
        urls.ISSUE_REINDEX: issuereindex.IssueReindex,
        urls.ISSUE_DETAIL: issuedetail.IssueDetail,
        urls.ISSUE_DETAIL_FLIPPER_NEXT: issuedetail.FlipperNext,
        urls.ISSUE_DETAIL_FLIPPER_PREV: issuedetail.FlipperPrev,
        urls.ISSUE_DETAIL_FLIPPER_INDEX: issuedetail.FlipperIndex,
        urls.ISSUE_COMMENT_DELETION_JSON: issuedetail.IssueCommentDeletion,
        urls.ISSUE_ATTACHMENT_DELETION_JSON:
            issueattachment.IssueAttachmentDeletion,
        urls.ISSUE_FLAGSPAM_JSON: spam.FlagSpamForm,
        urls.ISSUE_DELETE_JSON: issuedetail.IssueDeleteForm,
        urls.ISSUE_ENTRY: issueentry.IssueEntry,
        urls.ISSUE_ENTRY_AFTER_LOGIN: issueentryafterlogin.IssueEntryAfterLogin,
        urls.ISSUE_TIPS: issuetips.IssueSearchTips,
        urls.ISSUE_ATTACHMENT: issueattachment.AttachmentPage,
        urls.ISSUE_ATTACHMENT_TEXT: issueattachmenttext.AttachmentText,
        urls.ISSUE_BULK_EDIT: issuebulkedit.IssueBulkEdit,
        urls.COMPONENT_CREATE: componentcreate.ComponentCreate,
        urls.COMPONENT_DETAIL: componentdetail.ComponentDetail,
        urls.FIELD_CREATE: fieldcreate.FieldCreate,
        urls.FIELD_DETAIL: fielddetail.FieldDetail,
        urls.TEMPLATE_CREATE: templatecreate.TemplateCreate,
        urls.TEMPLATE_DETAIL: templatedetail.TemplateDetail,
        urls.WIKI_LIST: redirects.WikiRedirect,
        urls.WIKI_PAGE: redirects.WikiRedirect,
        urls.SOURCE_PAGE: redirects.SourceRedirect,
        urls.ADMIN_STATUSES: issueadmin.AdminStatuses,
        urls.ADMIN_LABELS: issueadmin.AdminLabels,
        urls.ADMIN_RULES: issueadmin.AdminRules,
        urls.ADMIN_TEMPLATES: issueadmin.AdminTemplates,
        urls.ADMIN_COMPONENTS: issueadmin.AdminComponents,
        urls.ADMIN_VIEWS: issueadmin.AdminViews,
        urls.ISSUE_ORIGINAL: issueoriginal.IssueOriginal,
        urls.ISSUE_EXPORT: issueexport.IssueExport,
        urls.ISSUE_EXPORT_JSON: issueexport.IssueExportJSON,
        urls.ISSUE_IMPORT: issueimport.IssueImport,
        urls.SPAM_MODERATION_QUEUE: spam.ModerationQueue,
        })

    self._SetupUserServlets({
        urls.SAVED_QUERIES: savedqueries.SavedQueries,
        urls.HOTLISTS: userhotlists.UserHotlists,
        })

    user_hotlists_redir = registerpages_helpers.MakeRedirectInScope(
        urls.HOTLISTS, 'u', keep_qs=True)
    self._SetupUserServlets({
        '/hotlists/': user_hotlists_redir,
        })

    # These servlets accept POST, but never write to the database, so they can
    # still be used when the site is read-only.
    self._SetupProjectServlets({
        urls.ISSUE_ADVSEARCH: issueadvsearch.IssueAdvancedSearch,
        }, post_does_write=False)

    list_redir = registerpages_helpers.MakeRedirectInScope(
        urls.ISSUE_LIST, 'p', keep_qs=True)
    self._SetupProjectServlets({
        '': list_redir,
        '/': list_redir,
        '/issues': list_redir,
        '/issues/': list_redir,
        })

    list_redir = registerpages_helpers.MakeRedirect(urls.ISSUE_LIST)
    self._SetupServlets({
        '/issues': list_redir,
        '/issues/': list_redir,
        })

  def _RegisterFrameworkHandlers(self):
    """Register page and form handlers for framework functionality."""
    self._SetupServlets({
        urls.CSP_REPORT: csp_report.CSPReportPage,

        # These are only shown to users if specific conditions are met.
        urls.NONPROJECT_COLLISION: artifactcollision.ArtifactCollision,
        urls.EXCESSIVE_ACTIVITY: excessiveactivity.ExcessiveActivity,
        urls.BANNED: banned.Banned,
        urls.PROJECT_MOVED: moved.ProjectMoved,

        # These are not externally accessible
        urls.RAMCACHE_CONSOLIDATE_CRON: cachemanager_svc.RamCacheConsolidate,
        urls.REAP_CRON: reap.Reap,
        urls.SPAM_DATA_EXPORT_CRON: spammodel.TrainingDataExport,
        urls.LOAD_API_CLIENT_CONFIGS_CRON: (
            client_config_svc.LoadApiClientConfigs),
        urls.CLIENT_MON: clientmon.ClientMonitor,
        urls.TRIM_VISITED_PAGES_CRON: trimvisitedpages.TrimVisitedPages,
        urls.TS_MON_JS: ts_mon_js.MonorailTSMonJSHandler,
        urls.WARMUP: warmup.Warmup,
        urls.START: warmup.Start,
        urls.STOP: warmup.Stop
        })

    self._SetupProjectServlets({
        # Collisions can happen on artifacts within a project or outside.
        urls.ARTIFACT_COLLISION: artifactcollision.ArtifactCollision,
        })

  def _RegisterSitewideHandlers(self):
    """Register page and form handlers that aren't associated with projects."""
    self._SetupServlets({
        urls.PROJECT_CREATE: projectcreate.ProjectCreate,
        # The user settings page is a site-wide servlet, not under /u/.
        urls.USER_SETTINGS: usersettings.UserSettings,
        urls.HOSTING_HOME: hostinghome.HostingHome,
        urls.GROUP_CREATE: groupcreate.GroupCreate,
        urls.GROUP_LIST: grouplist.GroupList,
        urls.GROUP_DELETE: grouplist.GroupList,
        urls.HOTLIST_CREATE: hotlistcreate.HotlistCreate,
        urls.BAN_SPAMMER_TASK: banspammer.BanSpammerTask,
        })

    self._SetupUserServlets({
        urls.USER_PROFILE: userprofile.UserProfile,
        urls.USER_PROFILE_POLYMER: userprofile.UserProfilePolymer,
        urls.BAN_USER: userprofile.BanUser,
        urls.BAN_SPAMMER: banspammer.BanSpammer,
        urls.USER_CLEAR_BOUNCING: userclearbouncing.UserClearBouncing,
        urls.USER_UPDATES_PROJECTS: userupdates.UserUpdatesProjects,
        urls.USER_UPDATES_DEVELOPERS: userupdates.UserUpdatesDevelopers,
        urls.USER_UPDATES_MINE: userupdates.UserUpdatesIndividual,
        })

    self._SetupUserHotlistServlets({
        urls.HOTLIST_ISSUES: hotlistissues.HotlistIssues,
        urls.HOTLIST_ISSUES_CSV: hotlistissuescsv.HotlistIssuesCsv,
        urls.HOTLIST_PEOPLE: hotlistpeople.HotlistPeopleList,
        urls.HOTLIST_DETAIL: hotlistdetails.HotlistDetails,
        urls.HOTLIST_RERANK_JSON: rerankhotlist.RerankHotlistIssue,
        })

    profile_redir = registerpages_helpers.MakeRedirectInScope(
        urls.USER_PROFILE, 'u')
    self._SetupUserServlets({'': profile_redir})

    self._SetupGroupServlets({
        urls.GROUP_DETAIL: groupdetail.GroupDetail,
        urls.GROUP_ADMIN: groupadmin.GroupAdmin,
        })

  def _RegisterRedirects(self):
    """Register redirects among pages inside monorail."""
    redirect = registerpages_helpers.MakeRedirect('/hosting/')
    self._SetupServlets({
        '/hosting': redirect,
        '/p': redirect,
        '/p/': redirect,
        '/u': redirect,
        '/u/': redirect,
        '/': redirect,
        })

    redirect = registerpages_helpers.MakeRedirectInScope(
        urls.PEOPLE_LIST, 'p')
    self._SetupProjectServlets({
        '/people': redirect,
        '/people/': redirect,
        })

    redirect = registerpages_helpers.MakeRedirect(urls.GROUP_LIST)
    self._SetupServlets({'/g': redirect})

    group_redir = registerpages_helpers.MakeRedirectInScope(
        urls.USER_PROFILE, 'g')
    self._SetupGroupServlets({'': group_redir})

  def _RegisterInboundMail(self):
    """Register a handler for inbound email and email bounces."""
    self.routes.append(webapp2.Route(
        '/_ah/mail/<project_addr:.+>',
        handler=inboundemail.InboundEmail,
        methods=['POST', 'GET']))
    self.routes.append(webapp2.Route(
        '/_ah/bounce',
        handler=inboundemail.BouncedEmail,
        methods=['POST', 'GET']))

  def _RegisterErrorPages(self):
    """Register handlers for errors."""
    self._AddRoute(
        '/p/<project_name:%s>/<unrecognized:.+>' % self._PROJECT_NAME_REGEX,
        custom_404.ErrorPage, 'GET')
