# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Base classes for Monorail servlets.

This base class provides HTTP get() and post() methods that
conveniently drive the process of parsing the request, checking base
permissions, gathering common page information, gathering
page-specific information, and adding on-page debugging information
(when appropriate).  Subclasses can simply implement the page-specific
logic.

Summary of page classes:
  Servlet: abstract base class for all Monorail servlets.
  _ContextDebugItem: displays page_data elements for on-page debugging.
"""

import httplib
import json
import logging
import os
import time
import urllib

from third_party import ezt
from third_party import httpagentparser

from google.appengine.api import users

import webapp2

import settings
from businesslogic import work_env
from features import savedqueries_helpers
from features import features_bizobj
from features import hotlist_views
from framework import actionlimit
from framework import alerts
from framework import captcha
from framework import exceptions
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_helpers
from framework import framework_views
from framework import monorailrequest
from framework import permissions
from framework import ratelimiter
from framework import servlet_helpers
from framework import template_helpers
from framework import urls
from framework import xsrf
from proto import project_pb2
from search import query2ast
from services import issue_svc
from services import project_svc
from services import secrets_svc
from services import user_svc
from services import usergroup_svc
from tracker import tracker_views

NONCE_LENGTH = 32

if not settings.unit_test_mode:
  import MySQLdb


class MethodNotSupportedError(NotImplementedError):
  """An exception class for indicating that the method is not supported.

  Used by GatherPageData and ProcessFormData to indicate that GET and POST,
  respectively, are not supported methods on the given Servlet.
  """
  pass


class Servlet(webapp2.RequestHandler):
  """Base class for all Monorail servlets.

  Defines a framework of methods that build up parts of the EZT page data.

  Subclasses should override GatherPageData and/or ProcessFormData to
  handle requests.
  """

  _MAIN_TAB_MODE = None  # Normally overriden in subclasses to be one of these:

  MAIN_TAB_NONE = 't0'
  MAIN_TAB_DASHBOARD = 't1'
  MAIN_TAB_ISSUES = 't2'
  MAIN_TAB_PEOPLE = 't3'
  MAIN_TAB_PROCESS = 't4'
  MAIN_TAB_UPDATES = 't5'
  MAIN_TAB_ADMIN = 't6'
  MAIN_TAB_DETAILS = 't7'
  PROCESS_TAB_SUMMARY = 'st1'
  PROCESS_TAB_STATUSES = 'st3'
  PROCESS_TAB_LABELS = 'st4'
  PROCESS_TAB_RULES = 'st5'
  PROCESS_TAB_TEMPLATES = 'st6'
  PROCESS_TAB_COMPONENTS = 'st7'
  PROCESS_TAB_VIEWS = 'st8'
  ADMIN_TAB_META = 'st1'
  ADMIN_TAB_ADVANCED = 'st9'
  HOTLIST_TAB_ISSUES = 'ht2'
  HOTLIST_TAB_PEOPLE = 'ht3'
  HOTLIST_TAB_DETAILS = 'ht4'

  # Most forms require a security token, however if a form is really
  # just redirecting to a search GET request without writing any data,
  # subclass can override this to allow anonymous use.
  CHECK_SECURITY_TOKEN = True

  # Most forms just ignore fields that have value "".  Subclasses can override
  # if needed.
  KEEP_BLANK_FORM_VALUES = False

  # Most forms use regular forms, but subclasses that accept attached files can
  # override this to be True.
  MULTIPART_POST_BODY = False

  # This value should not typically be overridden.
  _TEMPLATE_PATH = framework_constants.TEMPLATE_PATH

  _PAGE_TEMPLATE = None  # Normally overriden in subclasses.
  _ELIMINATE_BLANK_LINES = False

  _CAPTCHA_ACTION_TYPES = []  # Override this in subclass to add captcha.

  _MISSING_PERMISSIONS_TEMPLATE = 'sitewide/403-page.ezt'

  def __init__(self, request, response, services=None,
               content_type='text/html; charset=UTF-8'):
    """Load and parse the template, saving it for later use."""
    super(Servlet, self).__init__(request, response)
    if self._PAGE_TEMPLATE:  # specified in subclasses
      template_path = self._TEMPLATE_PATH + self._PAGE_TEMPLATE
      self.template = template_helpers.GetTemplate(
          template_path, eliminate_blank_lines=self._ELIMINATE_BLANK_LINES)
    else:
      self.template = None

    self._missing_permissions_template = template_helpers.MonorailTemplate(
        self._TEMPLATE_PATH + self._MISSING_PERMISSIONS_TEMPLATE)
    self.services = services or self.app.config.get('services')
    self.content_type = content_type
    self.mr = None
    self.ratelimiter = ratelimiter.RateLimiter()

  def dispatch(self):
    """Do common stuff then dispatch the request to get() or put() methods."""
    handler_start_time = time.time()

    logging.info('\n\n\nRequest handler: %r', self)

    self.mr = monorailrequest.MonorailRequest()

    self.ratelimiter.CheckStart(self.request)
    self.response.headers.add('Strict-Transport-Security',
        'max-age=31536000; includeSubDomains')

    if self.services.cache_manager:
      # TODO(jrobbins): don't do this step if invalidation_timestep was
      # passed via the request and matches our last timestep
      try:
        with self.mr.profiler.Phase('distributed invalidation'):
          self.services.cache_manager.DoDistributedInvalidation(self.mr.cnxn)

      except MySQLdb.OperationalError as e:
        logging.exception(e)
        page_data = {
          'http_response_code': httplib.SERVICE_UNAVAILABLE,
          'requested_url': self.request.url,
        }
        self.template = template_helpers.GetTemplate(
            'templates/framework/database-maintenance.ezt',
            eliminate_blank_lines=self._ELIMINATE_BLANK_LINES)
        self.template.WriteResponse(
          self.response, page_data, content_type='text/html')
        return

    try:
      with self.mr.profiler.Phase('parsing request and doing lookups'):
        self.mr.ParseRequest(self.request, self.services)

      self.response.headers['X-Frame-Options'] = 'SAMEORIGIN'
      webapp2.RequestHandler.dispatch(self)

    except user_svc.NoSuchUserException as e:
      logging.warning('Trapped NoSuchUserException %s', e)
      self.abort(404, 'user not found')

    except usergroup_svc.NoSuchGroupException as e:
      logging.warning('Trapped NoSuchGroupException %s', e)
      self.abort(404, 'user group not found')

    except exceptions.InputException as e:
      logging.info('Rejecting invalid input: %r', e)
      self.response.status = httplib.BAD_REQUEST

    except exceptions.NoSuchProjectException as e:
      logging.info('Rejecting invalid request: %r', e)
      self.response.status = httplib.BAD_REQUEST

    except xsrf.TokenIncorrect as e:
      logging.info('Bad XSRF token: %r', e.message)
      self.response.status = httplib.BAD_REQUEST

    except permissions.BannedUserException as e:
      logging.warning('The user has been banned')
      url = framework_helpers.FormatAbsoluteURL(
          self.mr, urls.BANNED, include_project=False, copy_params=False)
      self.redirect(url, abort=True)

    except actionlimit.ExcessiveActivityException:
      logging.info('Excessive Activity Exception %r', self.mr.auth.user_id)
      url = framework_helpers.FormatAbsoluteURL(
          self.mr, urls.EXCESSIVE_ACTIVITY,
          include_project=False, copy_params=False)
      self.redirect(url, abort=True)

    except ratelimiter.RateLimitExceeded as e:
      logging.info('RateLimitExceeded Exception %s', e)
      self.response.status = httplib.BAD_REQUEST
      self.response.body = 'Slow your roll.'

    finally:
      self.mr.CleanUp()
      self.ratelimiter.CheckEnd(self.request, time.time(), handler_start_time)

    total_processing_time = time.time() - handler_start_time
    logging.warn('Processed request in %d ms',
                 int(total_processing_time * 1000))
    if settings.enable_profiler_logging:
      self.mr.profiler.LogStats()

  def _AddHelpDebugPageData(self, page_data):
    with self.mr.profiler.Phase('help and debug data'):
      page_data.update(self.GatherHelpData(self.mr, page_data))
      page_data.update(self.GatherDebugData(self.mr, page_data))

  # pylint: disable=unused-argument
  def get(self, **kwargs):
    """Collect page-specific and generic info, then render the page.

    Args:
      Any path components parsed by webapp2 will be in kwargs, but we do
        our own parsing later anyway, so igore them for now.
    """
    page_data = {}
    nonce = framework_helpers.MakeRandomKey(length=NONCE_LENGTH)
    try:
      csp_header = 'Content-Security-Policy'
      csp_scheme = 'https:'
      if settings.dev_mode:
        csp_header = 'Content-Security-Policy-Report-Only'
        csp_scheme = 'http:'
      user_agent_str = self.mr.request.headers.get('User-Agent', '')
      ua = httpagentparser.detect(user_agent_str)
      browser, browser_major_version = 'Unknown browser', 0
      if ua.has_key('browser'):
        browser = ua['browser']['name']
        try:
          browser_major_version = int(ua['browser']['version'].split('.')[0])
        except ValueError:
          logging.warn('Could not parse version: %r', ua['browser']['version'])
      csp_supports_report_sample = (
        (browser == 'Chrome' and browser_major_version >= 59) or
        (browser == 'Opera' and browser_major_version >= 46))
      self.response.headers.add(csp_header,
           ("default-src %(scheme)s ; "
            "script-src"
            " %(rep_samp)s"  # Report 40 chars of any inline violation.
            " 'unsafe-inline'"  # Only counts in browsers that lack CSP2.
            " 'strict-dynamic'"  # Allows <script nonce> to load more.
            " https://www.gstatic.com/recaptcha/api2/"
            " 'self' 'nonce-%(nonce)s'; "
            "child-src https://www.google.com/recaptcha/; "
            "frame-src https://www.google.com/recaptcha/; "
            "img-src %(scheme)s data: blob: ; "
            "style-src %(scheme)s 'unsafe-inline'; "
            "object-src 'none'; "
            "base-uri 'none'; "
            "report-uri /csp.do" % {
            'nonce': nonce,
            'scheme': csp_scheme,
            'rep_samp': "'report-sample'" if csp_supports_report_sample else '',
            }))

      page_data.update(self._GatherFlagData(self.mr))

      # Page-specific work happens in this call.
      page_data.update(self._DoPageProcessing(self.mr, nonce))

      self._AddHelpDebugPageData(page_data)

      with self.mr.profiler.Phase('rendering template'):
        self._RenderResponse(page_data)

    except (MethodNotSupportedError, NotImplementedError) as e:
      # Instead of these pages throwing 500s display the 404 message and log.
      # The motivation of this is to minimize 500s on the site to keep alerts
      # meaningful during fuzzing. For more context see
      # https://bugs.chromium.org/p/monorail/issues/detail?id=659
      logging.warning('Trapped NotImplementedError %s', e)
      self.abort(404, 'invalid page')
    except query2ast.InvalidQueryError as e:
      logging.warning('Trapped InvalidQueryError: %s', e)
      logging.exception(e)
      msg = e.message if e.message else 'invalid query'
      self.abort(400, msg)
    except permissions.PermissionException as e:
      logging.warning('Trapped PermissionException %s', e)
      logging.warning('mr.auth.user_id is %s', self.mr.auth.user_id)
      logging.warning('mr.auth.effective_ids is %s', self.mr.auth.effective_ids)
      logging.warning('mr.perms is %s', self.mr.perms)
      if not self.mr.auth.user_id:
        # If not logged in, let them log in
        url = _SafeCreateLoginURL(self.mr)
        self.redirect(url, abort=True)
      else:
        # Display the missing permissions template.
        page_data = {
            'reason': e.message,
            'http_response_code': httplib.FORBIDDEN,
            }
        with self.mr.profiler.Phase('gather base data'):
          page_data.update(self.GatherBaseData(self.mr, nonce))
        self._AddHelpDebugPageData(page_data)
        self._missing_permissions_template.WriteResponse(
            self.response, page_data, content_type=self.content_type)

  def SetCacheHeaders(self, response):
    """Set headers to allow the response to be cached."""
    headers = framework_helpers.StaticCacheHeaders()
    for name, value in headers:
      response.headers[name] = value

  def GetTemplate(self, _page_data):
    """Get the template to use for writing the http response.

    Defaults to self.template.  This method can be overwritten in subclasses
    to allow dynamic template selection based on page_data.

    Args:
      _page_data: A dict of data for ezt rendering, containing base ezt
      data, captcha data, page data, and debug data.

    Returns:
      The template to be used for writing the http response.
    """
    return self.template

  def _GatherFlagData(self, mr):
    page_data = {
        'recaptcha_public_key': secrets_svc.GetRecaptchaPublicKey(),
        'project_stars_enabled': ezt.boolean(
            settings.enable_project_stars),
        'user_stars_enabled': ezt.boolean(settings.enable_user_stars),
        'can_create_project': ezt.boolean(
            permissions.CanCreateProject(mr.perms)),
        'can_create_group': ezt.boolean(
            permissions.CanCreateGroup(mr.perms)),
        }

    return page_data

  def _RenderResponse(self, page_data):
    logging.info('rendering response len(page_data) is %r', len(page_data))
    self.GetTemplate(page_data).WriteResponse(
        self.response, page_data, content_type=self.content_type)

  def ProcessFormData(self, mr, post_data):
    """Handle form data and redirect appropriately.

    Args:
      mr: commonly used info parsed from the request.
      post_data: HTML form data from the request.

    Returns:
      String URL to redirect the user to, or None if response was already sent.
    """
    raise MethodNotSupportedError()

  def post(self, **kwargs):
    """Parse the request, check base perms, and call form-specific code."""
    try:
      # Page-specific work happens in this call.
      self._DoFormProcessing(self.request, self.mr)

    except permissions.PermissionException as e:
      logging.warning('Trapped permission-related exception "%s".', e)
      # TODO(jrobbins): can we do better than an error page? not much.
      self.response.status = httplib.BAD_REQUEST

    except issue_svc.MidAirCollisionException as e:
      logging.info('Mid-air collision detected.')
      collision_page_url = urls.ARTIFACT_COLLISION
      url = framework_helpers.FormatAbsoluteURL(
          self.mr, collision_page_url, copy_params=False,
          name=e.name, continue_issue_id=e.continue_issue_id,
          ts=int(time.time()))
      self.redirect(url, abort=True)

  def _DoCommonRequestProcessing(self, request, mr):
    """Do common processing dependent on having the user and project pbs."""
    with mr.profiler.Phase('basic processing'):
      self._CheckForMovedProject(mr, request)
      self.AssertBasePermission(mr)

  def _DoPageProcessing(self, mr, nonce):
    """Do user lookups and gather page-specific ezt data."""
    with mr.profiler.Phase('common request data'):
      self._DoCommonRequestProcessing(self.request, mr)
      page_data = self.GatherBaseData(mr, nonce)
      page_data.update(self.GatherCaptchaData(mr))

    with mr.profiler.Phase('page processing'):
      page_data.update(self.GatherPageData(mr))
      page_data.update(mr.form_overrides)
      template_helpers.ExpandLabels(page_data)
      self._RecordVisitTime(mr)

    return page_data

  def _DoFormProcessing(self, request, mr):
    """Do user lookups and handle form data."""
    self._DoCommonRequestProcessing(request, mr)

    if self.CHECK_SECURITY_TOKEN:
      xsrf.ValidateToken(
        request.POST.get('token'), mr.auth.user_id, request.path)

    redirect_url = self.ProcessFormData(mr, request.POST)

    # Most forms redirect the user to a new URL on success.  If no
    # redirect_url was returned, the form handler must have already
    # sent a response.  E.g., bounced the user back to the form with
    # invalid form fields higlighted.
    if redirect_url:
      self.redirect(redirect_url, abort=True)
    else:
      assert self.response.body

  def _CheckForMovedProject(self, mr, request):
    """If the project moved, redirect there or to an informational page."""
    if not mr.project:
      return  # We are on a site-wide or user page.
    if not mr.project.moved_to:
      return  # This project has not moved.
    admin_url = '/p/%s%s' % (mr.project_name, urls.ADMIN_META)
    if request.path.startswith(admin_url):
      return  # It moved, but we are near the page that can un-move it.

    logging.info('project %s has moved: %s', mr.project.project_name,
                 mr.project.moved_to)

    moved_to = mr.project.moved_to
    if framework_bizobj.RE_PROJECT_NAME.match(moved_to):
      # Use the redir query parameter to avoid redirect loops.
      if mr.redir is None:
        url = framework_helpers.FormatMovedProjectURL(mr, moved_to)
        if '?' in url:
          url += '&redir=1'
        else:
          url += '?redir=1'
        logging.info('trusted move to a new project on our site')
        self.redirect(url, abort=True)

    logging.info('not a trusted move, will display link to user to click')
    # Attach the project name as a url param instead of generating a /p/
    # link to the destination project.
    url = framework_helpers.FormatAbsoluteURL(
        mr, urls.PROJECT_MOVED,
        include_project=False, copy_params=False, project=mr.project_name)
    self.redirect(url, abort=True)

  def CheckPerm(self, mr, perm, art=None, granted_perms=None):
    """Return True if the user can use the requested permission."""
    return servlet_helpers.CheckPerm(
        mr, perm, art=art, granted_perms=granted_perms)

  def MakePagePerms(self, mr, art, *perm_list, **kwargs):
    """Make an EZTItem with a set of permissions needed in a given template.

    Args:
      mr: commonly used info parsed from the request.
      art: a project artifact, such as an issue.
      *perm_list: any number of permission names that are referenced
          in the EZT template.
      **kwargs: dictionary that may include 'granted_perms' list of permissions
          granted to the current user specifically on the current page.

    Returns:
      An EZTItem with one attribute for each permission and the value
      of each attribute being an ezt.boolean().  True if the user
      is permitted to do that action on the given artifact, or
      False if not.
    """
    granted_perms = kwargs.get('granted_perms')
    page_perms = template_helpers.EZTItem()
    for perm in perm_list:
      setattr(
          page_perms, perm,
          ezt.boolean(self.CheckPerm(
              mr, perm, art=art, granted_perms=granted_perms)))

    return page_perms

  def AssertBasePermission(self, mr):
    """Make sure that the logged in user has permission to view this page.

    Subclasses should call super, then check additional permissions
    and raise a PermissionException if the user is not authorized to
    do something.

    Args:
      mr: commonly used info parsed from the request.

    Raises:
      PermissionException: If the user does not have permisssion to view
        the current page.
    """
    servlet_helpers.AssertBasePermission(mr)

  def GatherBaseData(self, mr, nonce):
    """Return a dict of info used on almost all pages."""
    project = mr.project

    project_summary = ''
    project_alert = None
    project_read_only = False
    project_home_page = ''
    project_thumbnail_url = ''
    if project:
      project_summary = project.summary
      project_alert = _CalcProjectAlert(project)
      project_read_only = project.read_only_reason
      project_home_page = project.home_page
      project_thumbnail_url = tracker_views.LogoView(project).thumbnail_url

    with work_env.WorkEnv(mr, self.services) as we:
      is_project_starred = we.IsProjectStarred(mr.project_id)

    project_view = None
    if mr.project:
      # TODO(jrobbins): should this be a ProjectView?
      project_view = template_helpers.PBProxy(mr.project)

    grid_x_attr = None
    grid_y_attr = None
    hotlist_view = None
    if mr.hotlist:
      users_by_id = framework_views.MakeAllUserViews(
          mr.cnxn, self.services.user,
          features_bizobj.UsersInvolvedInHotlists([mr.hotlist]))
      hotlist_view = hotlist_views.HotlistView(
          mr.hotlist, mr.auth, mr.viewed_user_auth.user_id,
          users_by_id, self.services.hotlist_star.IsItemStarredBy(
            mr.cnxn, mr.hotlist.hotlist_id, mr.auth.user_id))
      grid_x_attr = mr.x.lower()
      grid_y_attr = mr.y.lower()

    app_version = os.environ.get('CURRENT_VERSION_ID')

    viewed_username = None
    if mr.viewed_user_auth.user_view:
      viewed_username = mr.viewed_user_auth.user_view.username

    canned_query_views = []
    issue_entry_url = 'entry'
    config = None
    if mr.project_id and self.services.config:
      with mr.profiler.Phase('getting config'):
        config = self.services.config.GetProjectConfig(mr.cnxn, mr.project_id)
        canned_queries = self.services.features.GetCannedQueriesByProjectID(
            mr.cnxn, mr.project_id)
      grid_x_attr = (mr.x or config.default_x_attr).lower()
      grid_y_attr = (mr.y or config.default_y_attr).lower()
      canned_query_views = [
          savedqueries_helpers.SavedQueryView(sq, idx + 1, None, None)
          for idx, sq in enumerate(canned_queries)]
      issue_entry_url = _LoginOrIssueEntryURL(mr, config)

    if mr.auth.user_id and self.services.features:
      with mr.profiler.Phase('getting saved queries'):
        saved_queries = self.services.features.GetSavedQueriesByUserID(
            mr.cnxn, mr.me_user_id)
        saved_query_views = [
            savedqueries_helpers.SavedQueryView(sq, idx + 1, None, None)
            for idx, sq in enumerate(saved_queries)
            if (mr.project_id in sq.executes_in_project_ids or
                not mr.project_id)]
    else:
      saved_query_views = []

    viewing_self = mr.auth.user_id == mr.viewed_user_auth.user_id
    offer_saved_queries_subtab = (
        viewing_self or mr.auth.user_pb and mr.auth.user_pb.is_site_admin)

    login_url = _SafeCreateLoginURL(mr)
    logout_url = _SafeCreateLogoutURL(mr)
    logout_url_goto_home = users.create_logout_url('/')

    base_data = {
        # EZT does not have constants for True and False, so we pass them in.
        'True': ezt.boolean(True),
        'False': ezt.boolean(False),

        'site_name': settings.site_name,
        'show_search_metadata': ezt.boolean(False),
        'page_template': self._PAGE_TEMPLATE,
        'main_tab_mode': self._MAIN_TAB_MODE,
        'project_summary': project_summary,
        'project_home_page': project_home_page,
        'project_thumbnail_url': project_thumbnail_url,

        'hotlist_id': mr.hotlist_id,
        'hotlist': hotlist_view,

        'hostport': mr.request.host,
        'absolute_base_url': '%s://%s' % (mr.request.scheme, mr.request.host),
        'project_home_url': None,
        'link_rel_canonical': None,  # For specifying <link rel="canonical">
        'projectname': mr.project_name,
        'project': project_view,
        'project_is_restricted': ezt.boolean(_ProjectIsRestricted(mr)),
        'offer_contributor_list': ezt.boolean(
            permissions.CanViewContributorList(mr)),
        'logged_in_user': mr.auth.user_view,
        'form_token': None,  # Set to a value below iff the user is logged in.
        'form_token_path': None,
        'token_expires_sec': None,
        'xhr_token': None,  # Set to a value below iff the user is logged in.
        'flag_spam_token': None,
        'nonce': nonce,
        'perms': mr.perms,
        'warnings': mr.warnings,
        'errors': mr.errors,

        'viewed_username': viewed_username,
        'viewed_user': mr.viewed_user_auth.user_view,
        'viewed_user_pb': template_helpers.PBProxy(
            mr.viewed_user_auth.user_pb),
        'viewing_self': ezt.boolean(viewing_self),
        'viewed_user_id': mr.viewed_user_auth.user_id,
        'offer_saved_queries_subtab': ezt.boolean(offer_saved_queries_subtab),

        'currentPageURL': mr.current_page_url,
        'currentPageURLEncoded': mr.current_page_url_encoded,
        'login_url': login_url,
        'logout_url': logout_url,
        'logout_url_goto_home': logout_url_goto_home,
        'continue_issue_id': mr.continue_issue_id,
        'feedback_email': settings.feedback_email,
        'category_css': None,  # Used to specify a category of stylesheet
        'category2_css': None, # specify a 2nd category of stylesheet if needed.
        'page_css': None,  # Used to add a stylesheet to a specific page.

        'can': mr.can,
        'query': mr.query,
        'colspec': None,
        'sortspec': mr.sort_spec,

        'grid_x_attr': grid_x_attr,
        'grid_y_attr': grid_y_attr,
        'grid_cell_mode': mr.cells,
        'grid_mode': None,

        'issue_entry_url': issue_entry_url,
        'canned_queries': canned_query_views,
        'saved_queries': saved_query_views,
        'is_cross_project': ezt.boolean(False),

        # for project search (some also used in issue search)
        'start': mr.start,
        'num': mr.num,
        'groupby': mr.group_by_spec,
        'q_field_size': (
            min(framework_constants.MAX_ARTIFACT_SEARCH_FIELD_SIZE,
                max(framework_constants.MIN_ARTIFACT_SEARCH_FIELD_SIZE,
                    len(mr.query) + framework_constants.AUTOSIZE_STEP))),
        'mode': None,  # Display mode, e.g., grid mode.
        'ajah': mr.ajah,
        'table_title': mr.table_title,

        'alerts': alerts.AlertsView(mr),  # For alert.ezt
        'project_alert': project_alert,

        'title': None,  # First part of page title
        'title_summary': None,  # Appended to title on artifact detail pages

        # TODO(jrobbins): make sure that the templates use
        # project_read_only for project-mutative actions and if any
        # uses of read_only remain.
        'project_read_only': ezt.boolean(project_read_only),
        'site_read_only': ezt.boolean(settings.read_only),
        'banner_time': servlet_helpers.GetBannerTime(settings.banner_time),
        'read_only': ezt.boolean(settings.read_only or project_read_only),
        'site_banner_message': settings.banner_message,
        'robots_no_index': None,
        'analytics_id': settings.analytics_id,

        'is_project_starred': ezt.boolean(is_project_starred),

        'app_version': app_version,
        'viewing_user_page': ezt.boolean(False),

        'is_member': ezt.boolean(False),
        }

    if mr.project:
      base_data['project_home_url'] = '/p/%s' % mr.project_name

    # Always add an anti-xsrf token when the user is logged in.
    if mr.auth.user_id:
      form_token_path = self._FormHandlerURL(mr.request.path)
      base_data['form_token'] = xsrf.GenerateToken(
        mr.auth.user_id, form_token_path)
      base_data['form_token_path'] = form_token_path
      base_data['token_expires_sec'] = xsrf.TokenExpiresSec()
      base_data['xhr_token'] = xsrf.GenerateToken(
        mr.auth.user_id, xsrf.XHR_SERVLET_PATH)
      base_data['flag_spam_token'] = xsrf.GenerateToken(
         mr.auth.user_id, '/p/%s%s.do' % (
         mr.project_name, urls.ISSUE_FLAGSPAM_JSON))

    return base_data

  def _FormHandlerURL(self, path):
    """Return the form handler for the main form on a page."""
    if path.endswith('/'):
      return path + 'edit.do'
    elif path.endswith('.do'):
      return path  # This happens as part of PleaseCorrect().
    else:
      return path + '.do'

  def GatherCaptchaData(self, mr):
    """If this page needs a captcha, return captcha info for use in EZT."""
    if (mr.project and
        framework_bizobj.UserIsInProject(mr.project, mr.auth.effective_ids)):
      # Don't show users CAPTCHAs within their own projects.
      return {'show_captcha': ezt.boolean(False)}

    show_captcha = any(actionlimit.NeedCaptcha(mr.auth.user_pb, action_type)
                       for action_type in self._CAPTCHA_ACTION_TYPES)
    logging.info('show_captcha: %r', show_captcha)
    return {'show_captcha': ezt.boolean(show_captcha)}

  def GatherPageData(self, mr):
    """Return a dict of page-specific ezt data."""
    raise MethodNotSupportedError()

  # pylint: disable=unused-argument
  def GatherHelpData(self, mr, page_data):
    """Return a dict of values to drive on-page user help.

    Args:
      mr: common information parsed from the HTTP request.
      page_data: Dictionary of base and page template data.

    Returns:
      A dict of values to drive on-page user help, to be added to page_data.
    """
    help_data = {
        'cue': None,  # for cues.ezt
        }
    dismissed = []
    if mr.auth.user_pb:
      dismissed = mr.auth.user_pb.dismissed_cues
      if (mr.auth.user_pb.vacation_message and
          'you_are_on_vacation' not in dismissed):
        help_data['cue'] = 'you_are_on_vacation'
      if (mr.auth.user_pb.email_bounce_timestamp and
          'your_email_bounced' not in dismissed):
        help_data['cue'] = 'your_email_bounced'

    return help_data

  def GatherDebugData(self, mr, page_data):
    """Return debugging info for display at the very bottom of the page."""
    if mr.debug_enabled:
      debug = [_ContextDebugCollection('Page data', page_data)]
      return {
          'dbg': 'on',
          'debug': debug,
          'profiler': mr.profiler,
          }
    else:
      if '?' in mr.current_page_url:
        debug_url = mr.current_page_url + '&debug=1'
      else:
        debug_url = mr.current_page_url + '?debug=1'

      return {
          'debug_uri': debug_url,
          'dbg': 'off',
          'debug': [('none', 'recorded')],
          }

  def CheckCaptcha(self, mr, post_data):
    """Check the provided CAPTCHA solution and add an error if it is wrong."""
    if (mr.project and
        framework_bizobj.UserIsInProject(mr.project, mr.auth.effective_ids)):
      logging.info('Project member is exempt from CAPTCHA')
      return  # Don't check a user's actions within their own projects.

    if not any(actionlimit.NeedCaptcha(mr.auth.user_pb, action_type)
               for action_type in self._CAPTCHA_ACTION_TYPES):
      logging.info('No CAPTCHA was required')
      return  # no captcha was needed.

    remote_ip = mr.request.remote_addr
    captcha_response = post_data.get('g-recaptcha-response')
    correct, _msg = captcha.Verify(remote_ip, captcha_response)
    if correct:
      logging.info('CAPTCHA was solved')
    else:
      logging.info('BZzzz! Bad captcha solution.')
      mr.errors.captcha = 'Captcha check failed.'

  def CountRateLimitedActions(self, mr, action_counts):
    """Count attempted actions against non-member's action limits.

    Note that users can take any number of actions in their own projects.

    Args:
      mr: commonly used info parsed from the request.
      action_counts: {action_type: delta, ... }
        a dictionary mapping action type constants to the number of times
        that action was performed during the current request (usually 1).
    """
    if (mr.project and
        framework_bizobj.UserIsInProject(mr.project, mr.auth.effective_ids)):
      # Don't count a user's actions within their own projects...
      return

    for action_type in action_counts:
      actionlimit.CountAction(
          mr.auth.user_pb, action_type, delta=action_counts[action_type])

    self.services.user.UpdateUser(mr.cnxn, mr.auth.user_id, mr.auth.user_pb)

  def PleaseCorrect(self, mr, **echo_data):
    """Show the same form again so that the user can correct their input."""
    mr.PrepareForReentry(echo_data)
    self.get()

  def _RecordVisitTime(self, mr, now=None):
    """Record the signed in user's last visit time, if possible."""
    now = now or int(time.time())
    if not settings.read_only and mr.auth.user_id:
      user_pb = mr.auth.user_pb
      if (user_pb.last_visit_timestamp <
          now - framework_constants.VISIT_RESOLUTION):
        user_pb.last_visit_timestamp = now
        self.services.user.UpdateUser(mr.cnxn, user_pb.user_id, user_pb)


def _CalcProjectAlert(project):
  """Return a string to be shown as red text explaning the project state."""

  project_alert = None

  if project.read_only_reason:
    project_alert = 'READ-ONLY: %s.' % project.read_only_reason
  if project.moved_to:
    project_alert = 'This project has moved to: %s.' % project.moved_to
  elif project.delete_time:
    delay_seconds = project.delete_time - time.time()
    delay_days = delay_seconds // framework_constants.SECS_PER_DAY
    if delay_days <= 0:
      project_alert = 'Scheduled for deletion today.'
    else:
      days_word = 'day' if delay_days == 1 else 'days'
      project_alert = (
          'Scheduled for deletion in %d %s.' % (delay_days, days_word))
  elif project.state == project_pb2.ProjectState.ARCHIVED:
    project_alert = 'Project is archived: read-only by members only.'

  return project_alert


class _ContextDebugItem(object):
  """Wrapper class to generate on-screen debugging output."""

  def __init__(self, key, val):
    """Store the key and generate a string for the value."""
    self.key = key
    if isinstance(val, list):
      nested_debug_strs = [self.StringRep(v) for v in val]
      self.val = '[%s]' % ', '.join(nested_debug_strs)
    else:
      self.val = self.StringRep(val)

  def StringRep(self, val):
    """Make a useful string representation of the given value."""
    try:
      return val.DebugString()
    except Exception:
      try:
        return str(val.__dict__)
      except Exception:
        return repr(val)


class _ContextDebugCollection(object):
  """Attach a title to a dictionary for exporting as a table of debug info."""

  def __init__(self, title, collection):
    self.title = title
    self.collection = [_ContextDebugItem(key, collection[key])
                       for key in sorted(collection.iterkeys())]


def _ProjectIsRestricted(mr):
  """Return True if the mr has a 'private' project."""
  return (mr.project and
          mr.project.access != project_pb2.ProjectAccess.ANYONE)


def _LoginOrIssueEntryURL(mr, config):
  """Make a URL to sign in, if needed, on the way to entering an issue."""
  issue_entry_url = servlet_helpers.ComputeIssueEntryURL(mr, config)
  if mr.auth.user_id:
    return issue_entry_url
  else:
    after_login_url = framework_helpers.FormatAbsoluteURL(
        mr, urls.ISSUE_ENTRY_AFTER_LOGIN)
    return _SafeCreateLoginURL(mr, after_login_url)


def _SafeCreateLoginURL(mr, continue_url=None):
  """Make a login URL w/ a detailed continue URL, otherwise use a short one."""
  continue_url = continue_url or mr.current_page_url
  try:
    url = users.create_login_url(continue_url)
  except users.RedirectTooLongError:
    if mr.project_name:
      url = users.create_login_url('/p/%s' % mr.project_name)
    else:
      url = users.create_login_url('/')

  # Give the user a choice of existing accounts in their session
  # or the option to add an account, even if they are currently
  # signed in to exactly one account.
  if mr.auth.user_id:
    url = url.replace('/accounts/ServiceLogin', '/accounts/AccountChooser', 1)
  return url


def _SafeCreateLogoutURL(mr):
  """Make a logout URL w/ a detailed continue URL, otherwise use a short one."""
  try:
    return users.create_logout_url(mr.current_page_url)
  except users.RedirectTooLongError:
    if mr.project_name:
      return users.create_logout_url('/p/%s' % mr.project_name)
    else:
      return users.create_logout_url('/')
