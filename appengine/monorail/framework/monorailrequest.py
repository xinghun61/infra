# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes to hold information parsed from a request.

To simplify our servlets and avoid duplication of code, we parse some
info out of the request as soon as we get it and then pass a MonorailRequest
object to the servlet-specific request handler methods.
"""

import endpoints
import logging
import re
import urllib

from third_party import ezt

from google.appengine.api import app_identity
from google.appengine.api import oauth
from google.appengine.api import users

import webapp2

import settings
from businesslogic import work_env
from features import features_constants
from framework import exceptions
from framework import framework_bizobj
from framework import framework_constants
from framework import framework_views
from framework import permissions
from framework import profiler
from framework import sql
from framework import template_helpers
from proto import api_pb2_v1
from proto import user_pb2
from services import user_svc
from tracker import tracker_bizobj
from tracker import tracker_constants


_HOSTPORT_RE = re.compile('^[-a-z0-9.]+(:\d+)?$', re.I)


class AuthData(object):
  """This object holds authentication data about a user.

  This is used by MonorailRequest as it determines which user the
  requester is authenticated as and fetches the user's data.  It can
  also be used to lookup perms for user IDs specified in issue fields.

  Attributes:
    user_id: The user ID of the user (or 0 if not signed in).
    effective_ids: A set of user IDs that includes the signed in user's
        direct user ID and the user IDs of all their user groups.
        This set will be empty for anonymous users.
    user_view: UserView object for the signed-in user.
    user_pb: User object for the signed-in user.
    email: email address for the user, or None.
  """

  def __init__(self):
    self.user_id = 0
    self.effective_ids = set()
    self.user_view = None
    self.user_pb = user_pb2.MakeUser(0)
    self.email = None

  @classmethod
  def FromRequest(cls, cnxn, services):
    """Determine auth information from the request and fetches user data.

    If everything works and the user is signed in, then all of the public
    attributes of the AuthData instance will be filled in appropriately.

    Args:
      cnxn: connection to the SQL database.
      services: Interface to all persistence storage backends.

    Returns:
      A new AuthData object.
    """
    user = users.get_current_user()
    if user is None:
      return cls()
    else:
      # We create a User row for each user who visits the site.
      # TODO(jrobbins): we should really only do it when they take action.
      return cls.FromEmail(cnxn, user.email(), services, autocreate=True)

  @classmethod
  def FromEmail(cls, cnxn, email, services, autocreate=False):
    """Determine auth information for the given user email address.

    Args:
      cnxn: monorail connection to the database.
      email: string email address of the user.
      services: connections to backend servers.
      autocreate: set to True to create a new row in the Users table if needed.

    Returns:
      A new AuthData object.

    Raises:
      user_svc.NoSuchUserException: If the user of the email does not exist.
    """
    auth = cls()
    auth.email = email
    if email:
      auth.user_id = services.user.LookupUserID(
          cnxn, email, autocreate=autocreate)
      assert auth.user_id

    cls._FinishInitialization(cnxn, auth, services)
    return auth

  @classmethod
  def FromUserID(cls, cnxn, user_id, services):
    """Determine auth information for the given user ID.

    Args:
      cnxn: monorail connection to the database.
      user_id: int user ID of the user.
      services: connections to backend servers.

    Returns:
      A new AuthData object.
    """
    auth = cls()
    auth.user_id = user_id
    if auth.user_id:
      auth.email = services.user.LookupUserEmail(cnxn, user_id)

    cls._FinishInitialization(cnxn, auth, services)
    return auth

  @classmethod
  def _FinishInitialization(cls, cnxn, auth, services):
    """Fill in the test of the fields based on the user_id."""
    # TODO(jrobbins): re-implement same_org
    if auth.user_id:
      auth.effective_ids = services.usergroup.LookupMemberships(
          cnxn, auth.user_id)
      auth.effective_ids.add(auth.user_id)
      auth.user_pb = services.user.GetUser(cnxn, auth.user_id)
      if auth.user_pb:
        auth.user_view = framework_views.UserView(auth.user_pb)


class MonorailRequestBase(object):
  """A base class with common attributes for internal and external requests."""

  def __init__(
      self, services=None, user_id=None, user_email=None, cnxn=None):
    self.cnxn = cnxn or sql.MonorailConnection()
    self.profiler = profiler.Profiler()
    if user_id:
      assert services
      self.auth = AuthData.FromUserID(self.cnxn, user_id, services)
    elif user_email:
      assert services
      self.auth = AuthData.FromEmail(self.cnxn, user_email, services)
    else:
      self.auth = AuthData()

    self.project_name = None
    self.project = None
    self.config = None
    self.warnings = []
    self.errors = template_helpers.EZTError()
    self.perms = None

  def LookupLoggedInUserPerms(self):
    """Once we have the user and project, calculate their permissions."""
    with self.profiler.Phase('looking up signed in user permissions'):
      self.perms = permissions.GetPermissions(
          self.auth.user_pb, self.auth.effective_ids, self.project)

  @property
  def project_id(self):
    return self.project.project_id if self.project else None

  def CleanUp(self):
    """Close the database connection so that the app does not run out."""
    if self.cnxn:
      self.cnxn.Close()
      self.cnxn = None


class MonorailApiRequest(MonorailRequestBase):
  """A class to hold information parsed from the Endpoints API request."""

  # pylint: disable=attribute-defined-outside-init
  def __init__(self, request, services):
    requester = (
        endpoints.get_current_user() or
        oauth.get_current_user(
            framework_constants.OAUTH_SCOPE))
    requester_email = requester.email().lower()
    super(MonorailApiRequest, self).__init__(
        services=services, user_email=requester_email)
    self.me_user_id = self.auth.user_id
    self.viewed_username = None
    self.viewed_user_auth = None
    self.issue = None
    self.granted_perms = set()

    # query parameters
    self.params = {
      'can': 1,
      'start': 0,
      'num': 100,
      'q': '',
      'sort': '',
      'groupby': '',
      'projects': [],
      'hotlists':[]}
    self.use_cached_searches = True
    self.mode = None

    if hasattr(request, 'projectId'):
      self.project_name = request.projectId
      with work_env.WorkEnv(self, services) as we:
        self.project = we.GetProjectByName(self.project_name)
        self.params['projects'].append(self.project_name)
        self.config = we.GetProjectConfig(self.project_id)
        if hasattr(request, 'additionalProject'):
          self.params['projects'].extend(request.additionalProject)
          self.params['projects'] = list(set(self.params['projects']))
        if hasattr(request, 'issueId'):
          self.issue = we.GetIssueByLocalID(
              self.project_id, request.issueId, use_cache=False)
          self.granted_perms = tracker_bizobj.GetGrantedPerms(
              self.issue, self.auth.effective_ids, self.config)
    if hasattr(request, 'userId'):
      self.viewed_username = request.userId.lower()
      if self.viewed_username == 'me':
        self.viewed_username = requester_email
      self.viewed_user_auth = AuthData.FromEmail(
          self.cnxn, self.viewed_username, services)
    elif hasattr(request, 'groupName'):
      self.viewed_username = request.groupName.lower()
      try:
        self.viewed_user_auth = AuthData.FromEmail(
            self.cnxn, self.viewed_username, services)
      except user_svc.NoSuchUserException:
        self.viewed_user_auth = None
    self.LookupLoggedInUserPerms()

    # Build q.
    if hasattr(request, 'q') and request.q:
      self.params['q'] = request.q
    if hasattr(request, 'publishedMax') and request.publishedMax:
      self.params['q'] += ' opened<=%d' % request.publishedMax
    if hasattr(request, 'publishedMin') and request.publishedMin:
      self.params['q'] += ' opened>=%d' % request.publishedMin
    if hasattr(request, 'updatedMax') and request.updatedMax:
      self.params['q'] += ' modified<=%d' % request.updatedMax
    if hasattr(request, 'updatedMin') and request.updatedMin:
      self.params['q'] += ' modified>=%d' % request.updatedMin
    if hasattr(request, 'owner') and request.owner:
      self.params['q'] += ' owner:%s' % request.owner
    if hasattr(request, 'status') and request.status:
      self.params['q'] += ' status:%s' % request.status
    if hasattr(request, 'label') and request.label:
      self.params['q'] += ' label:%s' % request.label

    if hasattr(request, 'can') and request.can:
      if request.can == api_pb2_v1.CannedQuery.all:
        self.params['can'] = 1
      elif request.can == api_pb2_v1.CannedQuery.new:
        self.params['can'] = 6
      elif request.can == api_pb2_v1.CannedQuery.open:
        self.params['can'] = 2
      elif request.can == api_pb2_v1.CannedQuery.owned:
        self.params['can'] = 3
      elif request.can == api_pb2_v1.CannedQuery.reported:
        self.params['can'] = 4
      elif request.can == api_pb2_v1.CannedQuery.starred:
        self.params['can'] = 5
      elif request.can == api_pb2_v1.CannedQuery.to_verify:
        self.params['can'] = 7
      else: # Endpoints should have caught this.
        raise exceptions.InputException(
            'Canned query %s is not supported.', request.can)
    if hasattr(request, 'startIndex') and request.startIndex:
      self.params['start'] = request.startIndex
    if hasattr(request, 'maxResults') and request.maxResults:
      self.params['num'] = request.maxResults
    if hasattr(request, 'sort') and request.sort:
      self.params['sort'] = request.sort

    self.query_project_names = self.GetParam('projects')
    self.group_by_spec = self.GetParam('groupby')
    self.sort_spec = self.GetParam('sort')
    self.query = self.GetParam('q')
    self.can = self.GetParam('can')
    self.start = self.GetParam('start')
    self.num = self.GetParam('num')

  def GetParam(self, query_param_name, default_value=None,
               _antitamper_re=None):
    return self.params.get(query_param_name, default_value)

  def GetPositiveIntParam(self, query_param_name, default_value=None):
    """Returns 0 if the user-provided value is less than 0."""
    return max(self.GetParam(query_param_name, default_value=default_value),
               0)


class MonorailRequest(MonorailRequestBase):
  """A class to hold information parsed from the HTTP request.

  The goal of MonorailRequest is to do almost all URL path and query string
  procesing in one place, which makes the servlet code simpler.

  Attributes:
   cnxn: connection to the SQL databases.
   logged_in_user_id: int user ID of the signed-in user, or None.
   effective_ids: set of signed-in user ID and all their user group IDs.
   user_pb: User object for the signed in user.
   project_name: string name of the current project.
   project_id: int ID of the current projet.
   viewed_username: string username of the user whose profile is being viewed.
   can: int "canned query" number to scope the user's search.
   num: int number of results to show per pagination page.
   start: int position in result set to show on this pagination page.
   etc: there are many more, all read-only.
  """

  # pylint: disable=attribute-defined-outside-init
  def __init__(self, params=None):
    """Initialize the MonorailRequest object."""
    super(MonorailRequest, self).__init__()
    self.form_overrides = {}
    if params:
      self.form_overrides.update(params)
    self.debug_enabled = False
    self.use_cached_searches = True

    self.hotlist_id = None
    self.hotlist = None
    self.hotlist_name = None

    self.viewed_username = None
    self.viewed_user_auth = AuthData()

  def ParseRequest(self, request, services, do_user_lookups=True):
    """Parse tons of useful info from the given request object.

    Args:
      request: webapp2 Request object w/ path and query params.
      services: connections to backend servers including DB.
      do_user_lookups: Set to False to disable lookups during testing.
    """
    with self.profiler.Phase('basic parsing'):
      self.request = request
      self.current_page_url = request.url
      self.current_page_url_encoded = urllib.quote_plus(self.current_page_url)

      # Only accept a hostport from the request that looks valid.
      if not _HOSTPORT_RE.match(request.host):
        raise exceptions.InputException(
            'request.host looks funny: %r', request.host)

      logging.info('Request: %s', self.current_page_url)

    with self.profiler.Phase('path parsing'):
      (viewed_user_val, self.project_name,
       self.hotlist_id, self.hotlist_name) = _ParsePathIdentifiers(
           self.request.path)
      self.viewed_username = _GetViewedEmail(
          viewed_user_val, self.cnxn, services)
    with self.profiler.Phase('qs parsing'):
      self._ParseQueryParameters()
    with self.profiler.Phase('overrides parsing'):
      self._ParseFormOverrides()

    if not self.project:  # It can be already set in unit tests.
      self._LookupProject(services)
    if self.project_id and services.config:
      self.config = services.config.GetProjectConfig(self.cnxn, self.project_id)

    if do_user_lookups:
      if self.viewed_username:
        self._LookupViewedUser(services)
      self._LookupLoggedInUser(services)
      # TODO(jrobbins): re-implement HandleLurkerViewingSelf()

    if not self.hotlist:
      self._LookupHotlist(services)

    if self.query is None:
      self.query = self._CalcDefaultQuery()

    prod_debug_allowed = self.perms.HasPerm(
        permissions.VIEW_DEBUG, self.auth.user_id, None)
    self.debug_enabled = (request.params.get('debug') and
                          (settings.dev_mode or prod_debug_allowed))
    # temporary option for perf testing on staging instance.
    if request.params.get('disable_cache'):
      if settings.dev_mode or 'staging' in request.host:
        self.use_cached_searches = False

  def _CalcDefaultQuery(self):
    """When URL has no q= param, return the default for members or ''."""
    if (self.can == 2 and self.project and self.auth.effective_ids and
        framework_bizobj.UserIsInProject(self.project, self.auth.effective_ids)
        and self.config):
      return self.config.member_default_query
    else:
      return ''

  def _ParseQueryParameters(self):
    """Parse and convert all the query string params used in any servlet."""
    self.start = self.GetPositiveIntParam('start', default_value=0)
    self.num = self.GetPositiveIntParam('num', default_value=100)
    # Prevent DoS attacks that try to make us serve really huge result pages.
    self.num = min(self.num, settings.max_artifact_search_results_per_page)

    self.invalidation_timestep = self.GetIntParam(
        'invalidation_timestep', default_value=0)

    self.continue_issue_id = self.GetIntParam(
        'continue_issue_id', default_value=0)
    self.redir = self.GetParam('redir')

    # Search scope, a.k.a., canned query ID
    # TODO(jrobbins): make configurable
    self.can = self.GetIntParam(
        'can', default_value=tracker_constants.OPEN_ISSUES_CAN)

    # Search query
    self.query = self.GetParam('q')

    # Sorting of search results (needed for result list and flipper)
    self.sort_spec = self.GetParam(
        'sort', default_value='',
        antitamper_re=framework_constants.SORTSPEC_RE)

    # Note: This is set later in request handling by ComputeColSpec().
    self.col_spec = None

    # Grouping of search results (needed for result list and flipper)
    self.group_by_spec = self.GetParam(
        'groupby', default_value='',
        antitamper_re=framework_constants.SORTSPEC_RE)

    # For issue list and grid mode.
    self.cursor = self.GetParam('cursor')
    self.preview = self.GetParam('preview')
    self.mode = self.GetParam('mode', default_value='list')
    self.x = self.GetParam('x', default_value='')
    self.y = self.GetParam('y', default_value='')
    self.cells = self.GetParam('cells', default_value='ids')

    # For the dashboard and issue lists included in the dashboard.
    self.ajah = self.GetParam('ajah')  # AJAH = Asychronous Javascript And HTML
    self.table_title = self.GetParam('table_title')
    self.panel_id = self.GetIntParam('panel')

    # For pagination of updates lists
    self.before = self.GetPositiveIntParam('before')
    self.after = self.GetPositiveIntParam('after')

    # For cron tasks and backend calls
    self.lower_bound = self.GetIntParam('lower_bound')
    self.upper_bound = self.GetIntParam('upper_bound')
    self.shard_id = self.GetIntParam('shard_id')

    # For specifying which objects to operate on
    self.local_id = self.GetIntParam('id')
    self.local_id_list = self.GetIntListParam('ids')
    self.seq = self.GetIntParam('seq')
    self.aid = self.GetIntParam('aid')
    self.specified_user_id = self.GetIntParam('u', default_value=0)
    self.specified_logged_in_user_id = self.GetIntParam(
        'logged_in_user_id', default_value=0)
    self.specified_me_user_id = self.GetIntParam(
        'me_user_id', default_value=0)
    self.specified_project = self.GetParam('project')
    self.specified_project_id = self.GetIntParam('project_id')
    self.query_project_names = self.GetListParam('projects', default_value=[])
    self.template_name = self.GetParam('template')
    self.component_path = self.GetParam('component')
    self.field_name = self.GetParam('field')

    # For image attachments
    self.inline = bool(self.GetParam('inline'))
    self.thumb = bool(self.GetParam('thumb'))

    # For JS callbacks
    self.token = self.GetParam('token')
    self.starred = bool(self.GetIntParam('starred'))

    # For issue reindexing utility servlet
    self.auto_submit = self.GetParam('auto_submit')

    # For issue dependency reranking servlet
    self.parent_id = self.GetIntParam('parent_id')
    self.target_id = self.GetIntParam('target_id')
    self.moved_ids = self.GetIntListParam('moved_ids')
    self.split_above = self.GetBoolParam('split_above')

    # For adding issues to hotlists servlet
    self.hotlist_ids_remove = self.GetIntListParam('hotlist_ids_remove')
    self.hotlist_ids_add = self.GetIntListParam('hotlist_ids_add')
    self.issue_refs = self.GetListParam('issue_refs')

  def _ParseFormOverrides(self):
    """Support deep linking by allowing the user to set form fields via QS."""
    allowed_overrides = {
        'template_name': self.GetParam('template_name'),
        'initial_summary': self.GetParam('summary'),
        'initial_description': (self.GetParam('description') or
                                self.GetParam('comment')),
        'initial_comment': self.GetParam('comment'),
        'initial_status': self.GetParam('status'),
        'initial_owner': self.GetParam('owner'),
        'initial_cc': self.GetParam('cc'),
        'initial_blocked_on': self.GetParam('blockedon'),
        'initial_blocking': self.GetParam('blocking'),
        'initial_merge_into': self.GetIntParam('mergeinto'),
        'initial_components': self.GetParam('components'),
        'initial_hotlists': self.GetParam('hotlists'),

        # For the people pages
        'initial_add_members': self.GetParam('add_members'),
        'initially_expanded_form': ezt.boolean(self.GetParam('expand_form')),

        # For user group admin pages
        'initial_name': (self.GetParam('group_name') or
                         self.GetParam('proposed_project_name')),
        }

    # Only keep the overrides that were actually provided in the query string.
    self.form_overrides.update(
        (k, v) for (k, v) in allowed_overrides.iteritems()
        if v is not None)

  def _LookupViewedUser(self, services):
    """Get information about the viewed user (if any) from the request."""
    try:
      with self.profiler.Phase('get viewed user, if any'):
        self.viewed_user_auth = AuthData.FromEmail(
            self.cnxn, self.viewed_username, services, autocreate=False)
    except user_svc.NoSuchUserException:
      logging.info('could not find user %r', self.viewed_username)
      webapp2.abort(404, 'user not found')

    if not self.viewed_user_auth.user_id:
      webapp2.abort(404, 'user not found')

  def _LookupProject(self, services):
    """Get information about the current project (if any) from the request.

    Raises:
      NoSuchProjectException if there is no project with that name.
    """
    with work_env.WorkEnv(
        self, services, phase='get current project, if any') as we:
      if not self.project_name:
        logging.info('no project_name, so no project')
      else:
        self.project = we.GetProjectByName(self.project_name)

  def _LookupHotlist(self, services):
    """Get information about the current hotlist (if any) from the request."""
    with self.profiler.Phase('get current hotlist, if any'):
      if self.hotlist_name:
        hotlist_id_dict = services.features.LookupHotlistIDs(
            self.cnxn, [self.hotlist_name], [self.viewed_user_auth.user_id])
        try:
          self.hotlist_id = hotlist_id_dict[(
              self.hotlist_name, self.viewed_user_auth.user_id)]
        except KeyError:
          webapp2.abort(404, 'invalid hotlist')

      if not self.hotlist_id:
        logging.info('no hotlist_id or bad hotlist_name, so no hotlist')
      else:
        self.hotlist = services.features.GetHotlistByID(
            self.cnxn, self.hotlist_id)
        if (not self.hotlist) or (self.viewed_user_auth.user_id not in
                                  self.hotlist.owner_ids):
          webapp2.abort(404, 'invalid hotlist')

  def _LookupLoggedInUser(self, services):
    """Get information about the signed-in user (if any) from the request."""
    with self.profiler.Phase('get user info, if any'):
      self.auth = AuthData.FromRequest(self.cnxn, services)
    self.me_user_id = (self.GetIntParam('me') or
                       self.viewed_user_auth.user_id or self.auth.user_id)

    self.LookupLoggedInUserPerms()

  def ComputeColSpec(self, config):
    """Set col_spec based on param, default in the config, or site default."""
    if self.col_spec is not None:
      return  # Already set.
    default_col_spec = ''
    if config:
      default_col_spec = config.default_col_spec

    col_spec = self.GetParam(
        'colspec', default_value=default_col_spec,
        antitamper_re=framework_constants.COLSPEC_RE)
    cols_lower = col_spec.lower().split()
    if self.project and any(
        hotlist_col in cols_lower for hotlist_col in [
            'rank', 'adder', 'added']):
      # if the the list is a project list and the 'colspec' is a carry-over
      # from hotlists, set col_spec to None so it will be set to default in
      # in the next if statement
      col_spec = None

    if not col_spec:
      # If col spec is still empty then default to the global col spec.
      col_spec = tracker_constants.DEFAULT_COL_SPEC

    self.col_spec = ' '.join(ParseColSpec(col_spec))

  def PrepareForReentry(self, echo_data):
    """Expose the results of form processing as if it was a new GET.

    This method is called only when the user submits a form with invalid
    information which they are being asked to correct it.  Updating the MR
    object allows the normal servlet get() method to populate the form with
    the entered values and error messages.

    Args:
      echo_data: dict of {page_data_key: value_to_reoffer, ...} that will
          override whatever HTML form values are nomally shown to the
          user when they initially view the form.  This allows them to
          fix user input that was not valid.
    """
    self.form_overrides.update(echo_data)

  def GetParam(self, query_param_name, default_value=None,
               antitamper_re=None):
    """Get a query parameter from the URL as a utf8 string."""
    value = self.request.params.get(query_param_name)
    assert value is None or isinstance(value, unicode)
    using_default = value is None
    if using_default:
      value = default_value

    if antitamper_re and not antitamper_re.match(value):
      if using_default:
        logging.error('Default value fails antitamper for %s field: %s',
                      query_param_name, value)
      else:
        logging.info('User seems to have tampered with %s field: %s',
                     query_param_name, value)
      raise exceptions.InputException()

    return value

  def GetIntParam(self, query_param_name, default_value=None):
    """Get an integer param from the URL or default."""
    value = self.request.params.get(query_param_name)
    if value is None or value == '':
      return default_value

    try:
      return int(value)
    except (TypeError, ValueError):
      raise exceptions.InputException('Invalid value for integer param')

  def GetPositiveIntParam(self, query_param_name, default_value=None):
    """Returns 0 if the user-provided value is less than 0."""
    return max(self.GetIntParam(query_param_name, default_value=default_value),
               0)

  def GetListParam(self, query_param_name, default_value=None):
    """Get a list of strings from the URL or default."""
    params = self.request.params.get(query_param_name)
    if params is None:
      return default_value
    if not params:
      return []
    return params.split(',')

  def GetIntListParam(self, query_param_name, default_value=None):
    """Get a list of ints from the URL or default."""
    param_list = self.GetListParam(query_param_name)
    if param_list is None:
      return default_value

    try:
      return [int(p) for p in param_list]
    except (TypeError, ValueError):
      raise exceptions.InputException('Invalid value for integer list param')

  def GetBoolParam(self, query_param_name, default_value=None):
    """Get a boolean param from the URL or default."""
    value = self.request.params.get(query_param_name)
    if value is None:
      return default_value

    if (not value) or (value.lower() == 'false'):
      return False
    return True


def _ParsePathIdentifiers(path):
  """Parse out the workspace being requested (if any).

  Args:
    path: A string beginning with the request's path info.

  Returns:
    (viewed_user_val, project_name).
  """
  viewed_user_val = None
  project_name = None
  hotlist_id = None
  hotlist_name = None

  # Strip off any query params
  split_path = path.lstrip('/').split('?')[0].split('/')
  if len(split_path) >= 2:
    if split_path[0] == 'p':
      project_name = split_path[1]
    if split_path[0] == 'u':
      viewed_user_val = urllib.unquote(split_path[1])
      if len(split_path) >= 4 and split_path[2] == 'hotlists':
        try:
          hotlist_id = int(
              urllib.unquote(split_path[3].split('.')[0]))
        except ValueError:
          raw_last_path = (split_path[3][:-3] if
                        split_path[3].endswith('.do') else split_path[3])
          last_path = urllib.unquote(raw_last_path)
          match = framework_bizobj.RE_HOTLIST_NAME.match(
              last_path)
          if not match:
            raise exceptions.InputException(
                'Could not parse hotlist id or name')
          else:
            hotlist_name = last_path.lower()

    if split_path[0] == 'g':
      viewed_user_val = urllib.unquote(split_path[1])

  return viewed_user_val, project_name, hotlist_id, hotlist_name


def _GetViewedEmail(viewed_user_val, cnxn, services):
  """Returns the viewed user's email.

  Args:
    viewed_user_val: Could be either int (user_id) or str (email).
    cnxn: connection to the SQL database.
    services: Interface to all persistence storage backends.

  Returns:
    viewed_email
  """
  if not viewed_user_val:
    return None

  try:
    viewed_userid = int(viewed_user_val)
    viewed_email = services.user.LookupUserEmail(cnxn, viewed_userid)
    if not viewed_email:
      logging.info('userID %s not found', viewed_userid)
      webapp2.abort(404, 'user not found')
  except ValueError:
    viewed_email = viewed_user_val

  return viewed_email


def ParseColSpec(col_spec):
  """Split a string column spec into a list of column names.

  Args:
    col_spec: a unicode string containing a list of labels.

  Returns:
    A list of the extracted labels. Non-alphanumeric
    characters other than the period will be stripped from the text.
  """
  return framework_constants.COLSPEC_COL_RE.findall(col_spec)
