# Copyright 2008 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""App Engine data model (schema) definition for Rietveld."""

import calendar
import datetime
import itertools
import json
import logging
import md5
import os
import re
import sys
import time

from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.api.users import User
from google.appengine.ext import db
from google.appengine.ext import ndb

from django.conf import settings

from codereview import auth_utils
from codereview import committer_list
from codereview import engine_utils
from codereview import patching
from codereview import utils
from codereview.exceptions import FetchError


REQUIRED_REVIEWER_PREFIX = '*'
CONTEXT_CHOICES = (3, 10, 25, 50, 75, 100)
PRIVILEGED_USER_DOMAINS = ('@chromium.org', '@google.com', '@webrtc.org')
AVAILABLE_CQS_MEMCACHE_KEY = 'available_cqs'

# When reverted, CLs older than this will not skip CQ checks.
# Please ensure this value is always in multiple of days or change
# the templates accordingly.
REVERT_MAX_AGE_FOR_CHECKS_BYPASSING = datetime.timedelta(days=1)

# Poor man way to find when a CL was landed.
COMMITTED_MSG_RE = re.compile(
    r'Committed patchset #(\d)+ \(id:(\d)+\)( manually)?( as)?')

def format_reviewer(reviewer, required_reviewers, reviewer_func=None):
  """Adds the required prefix if the reviewer is a required reviewer."""
  # Use a trivial function that returns the reviewer if none has been specified.
  reviewer_func = reviewer_func if reviewer_func else lambda r: r
  if reviewer in required_reviewers:
    return '%s%s' % (REQUIRED_REVIEWER_PREFIX, reviewer_func(reviewer))
  else:
    return reviewer_func(reviewer)


def is_privileged_user(user):
  """Returns True if user is permitted special access rights.

  Users are privileged if they are using an account from
  a certain domain or they are a Chromium committer, regardless
  of domain.
  """
  if not user:
    return False
  email = user.email().lower()
  return (email.endswith(PRIVILEGED_USER_DOMAINS) or
          email in committer_list.Committers())


### CQList ###

class CQList(ndb.Model):
  """Stores the last known list of available CQs."""
  names = ndb.StringProperty(repeated=True)


### Issues, PatchSets, Patches, Contents, Comments, Messages ###

class Issue(ndb.Model):
  """The major top-level entity.

  It has one or more PatchSets as its descendants.
  """

  subject = ndb.StringProperty(required=True)
  description = ndb.TextProperty()
  project = ndb.StringProperty()
  #: in Subversion - repository path (URL) for files in patch set
  base = ndb.StringProperty()
  target_ref = ndb.StringProperty()
  repo_guid = ndb.StringProperty()
  owner = auth_utils.AnyAuthUserProperty(auto_current_user_add=True,
                                         required=True)
  created = ndb.DateTimeProperty(auto_now_add=True)
  modified = ndb.DateTimeProperty(auto_now=True)
  reviewers = ndb.StringProperty(repeated=True)
  required_reviewers = ndb.StringProperty(repeated=True)
  all_required_reviewers_approved = ndb.BooleanProperty(default=True)
  cc = ndb.StringProperty(repeated=True)
  closed = ndb.BooleanProperty(default=False)
  private = ndb.BooleanProperty(default=False)
  n_comments = ndb.IntegerProperty()
  commit = ndb.BooleanProperty(default=False)
  cq_dry_run = ndb.BooleanProperty(default=False)
  cq_dry_run_last_triggered_by = ndb.StringProperty()

  # NOTE: Use num_messages instead of using n_messages_sent directly.
  n_messages_sent = ndb.IntegerProperty()

  # List of emails that this issue has updates for.
  updates_for = ndb.StringProperty(repeated=True)

  # JSON: {reviewer_email -> [bool|None]}
  reviewer_approval = ndb.TextProperty()

  # Approvers to notify by email if a new patchset is uploaded after their LGTM
  # and the CQ bit is checked.
  approvers_to_notify = ndb.StringProperty(repeated=True)

  # JSON: {reviewer_email -> int}
  draft_count_by_user = ndb.TextProperty()

  _is_starred = None
  _has_updates_for_current_user = None
  _original_subject = None

  @property
  def is_cq_available(self):
    """Return true if this issue is part of a project that has a CQ."""
    available_cqs = memcache.get(AVAILABLE_CQS_MEMCACHE_KEY)
    if not available_cqs:
      cq_list = ndb.Key(CQList, 'singleton').get()
      if cq_list:
        available_cqs = cq_list.names
        memcache.set(AVAILABLE_CQS_MEMCACHE_KEY, available_cqs, 600)

    if available_cqs:
      return self.project in available_cqs
    return True

  @property
  def is_starred(self):
    """Whether the current user has this issue starred."""
    if self._is_starred is not None:
      return self._is_starred
    account = Account.current_user_account
    self._is_starred = account is not None and self.key.id() in account.stars
    return self._is_starred

  def user_can_edit(self, user):
    """Returns True if the given user has permission to edit this issue."""
    return user and (user.email() == self.owner.email() or
                     self.is_collaborator(user) or
                     auth_utils.is_current_user_admin() or
                     auth_utils.is_curent_user_whitelisted_oauth_email() or
                     is_privileged_user(user))

  @property
  def edit_allowed(self):
    """Whether the current user can edit this issue."""
    return self.user_can_edit(auth_utils.get_current_user())

  def user_can_upload(self, user):
    """Returns True if the user may upload a patchset to this issue.

    This is stricter than user_can_edit because users cannot qualify just based
    on their email address domain."""
    return user and (user.email() == self.owner.email() or
                     self.is_collaborator(user) or
                     auth_utils.is_current_user_admin())

  @property
  def upload_allowed(self):
    """Whether the current user can upload a patchset to this issue."""
    return self.user_can_upload(auth_utils.get_current_user())

  def user_can_view(self, user):
    """Returns True if the given user has permission to view this issue."""
    if not self.private:
      return True
    if user is None:
      return False
    email = user.email().lower()
    return (self.user_can_edit(user) or
            email in self.cc or
            email in self.reviewers)

  @property
  def view_allowed(self):
    """Whether the current user can view this issue."""
    return self.user_can_view(auth_utils.get_current_user())

  @property
  def num_messages(self):
    """Get and/or calculate the number of messages sent for this issue."""
    if self.n_messages_sent is None:
      self.calculate_updates_for()
    return self.n_messages_sent

  @num_messages.setter
  def num_messages(self, val):
    """Setter for num_messages."""
    self.n_messages_sent = val

  @property
  def patchsets(self):
    return PatchSet.query(ancestor=self.key).order(Issue.created)

  def most_recent_patchset_query(self):
    return PatchSet.query(ancestor=self.key).order(-Issue.created)

  def most_recent_patchset_key(self):
    query = self.most_recent_patchset_query()
    ps_key = query.get(keys_only=True)
    return ps_key

  @property
  def messages(self):
    return Message.query(ancestor=self.key).order(Message.date)

  def update_comment_count(self, n):
    """Increment the n_comments property by n.

    If n_comments in None, compute the count through a query.  (This
    is a transitional strategy while the database contains Issues
    created using a previous version of the schema.)
    """
    if self.n_comments is None:
      self.n_comments = self._get_num_comments()
    self.n_comments += n

  @property
  def num_comments(self):
    """The number of non-draft comments for this issue.

    This is almost an alias for self.n_comments, except that if
    n_comments is None, it is computed through a query, and stored,
    using n_comments as a cache.
    """
    if self.n_comments is None:
      self.n_comments = self._get_num_comments()
    return self.n_comments

  def _get_num_comments(self):
    """Helper to compute the number of comments through a query."""
    return Comment.query(Comment.draft == False, ancestor=self.key).count()

  _num_drafts = None

  def get_num_drafts(self, user):
    """The number of draft comments on this issue for the user.

    The value is expensive to compute, so it is cached.
    """
    if user is None:
      return 0
    assert isinstance(user, User), 'Expected User, got %r instead.' % user
    if self._num_drafts is None:
      if self.draft_count_by_user is None:
        self.calculate_draft_count_by_user()
      else:
        self._num_drafts = json.loads(self.draft_count_by_user)
    return self._num_drafts.get(user.email(), 0)

  def calculate_draft_count_by_user(self):
    """Computes the number of drafts by user and returns the put future.

    Initializes _num_drafts as a side effect.
    """
    self._num_drafts = {}
    query = Comment.query(Comment.draft == True, ancestor=self.key)
    for comment in query:
      if not comment.author:
        logging.info('Ignoring authorless comment: %r', comment)
        continue
      cur = self._num_drafts.setdefault(comment.author.email(), 0)
      self._num_drafts[comment.author.email()] = cur + 1
    self.draft_count_by_user = json.dumps(self._num_drafts)

  def collaborator_emails(self):
    """Returns a possibly empty list of emails specified in
    COLLABORATOR= lines.

    Note that one COLLABORATOR= lines is required per address.
    """
    return []  # TODO(jrobbins): add a distinct collaborators field.

  def is_collaborator(self, user):
    """Returns true if the given user is a collaborator on this issue.

    This is determined by checking if the user's email is listed as a
    collaborator email.
    """
    if not user:
      return False
    return user.email() in self.collaborator_emails()

  @property
  def formatted_reviewers(self):
    """Returns a dict from the reviewer to their approval status."""
    if self.reviewer_approval:
      return json.loads(self.reviewer_approval)
    else:
      # Don't have reviewer_approval calculated, so return all reviewers with
      # no approval status.
      return {r: None for r in self.reviewers}

  @property
  def has_updates(self):
    """Returns True if there have been recent updates on this issue for the
    current user.

    If the current user is an owner, this will return True if there are any
    messages after the last message from the owner.
    If the current user is not the owner, this will return True if there has
    been a message from the owner (but not other reviewers) after the
    last message from the current user."""
    if self._has_updates_for_current_user is None:
      user = auth_utils.get_current_user()
      if not user:
        return False
      self._has_updates_for_current_user = (user.email() in self.updates_for)
    return self._has_updates_for_current_user

  def calculate_updates_for(self, *msgs):
    """Recalculates updates_for, reviewer_approval, and draft_count_by_user,
    factoring in msgs which haven't been sent.

    This only updates this Issue object. You'll still need to put() it to
    the data store for it to take effect.
    """
    updates_for_set = set(self.updates_for)
    approval_dict = {r: None for r in self.reviewers}
    self.num_messages = 0
    old_messages = Message.query(
        Message.draft == False,
        ancestor=self.key).order(Message.date)
    # We cannot put this condition in the query because:
    # (a) auto_generated == False does not return legacy messages
    # and (b) auto_generated != True conflicts with sorting.
    old_messages = [
      msg for msg in old_messages if not msg.auto_generated]

    for msg in itertools.chain(old_messages, msgs):
      if self._original_subject is None:
        self._original_subject = msg.subject
      self.num_messages += 1
      if msg.sender == self.owner.email():
        updates_for_set.update(self.reviewers, self.cc,
                               self.collaborator_emails())
      else:
        updates_for_set.add(self.owner.email())
        if msg.approval:
          approval_dict[msg.sender] = True
          patchset_id = msg.patchset_key.id() if msg.patchset_key else None
          if (not patchset_id or
              self.most_recent_patchset_key().id() == patchset_id):
            if msg.sender in self.approvers_to_notify:
              self.approvers_to_notify.remove(msg.sender)
        elif msg.disapproval:
          approval_dict[msg.sender] = False
          patchset_id = msg.patchset_key.id() if msg.patchset_key else None
          if (not patchset_id or
              self.most_recent_patchset_key().id() == patchset_id):
            if msg.sender in self.approvers_to_notify:
              self.approvers_to_notify.remove(msg.sender)
      updates_for_set.discard(msg.sender)
      self.modified = msg.date
    self.updates_for = updates_for_set
    self.reviewer_approval = json.dumps(approval_dict)

    # If required reviewers have been specified then check to see if they have
    # all approved the issue.
    self.all_required_reviewers_approved = all(
        approval_dict.get(rr) for rr in self.required_reviewers)

  def calculate_and_save_updates_if_None(self):
    """If this Issue doesn't have a valid updates_for or n_messages_sent,
    calculate them and save them back to the datastore.

    Returns a future for the put() operation or None if this issue is up to
    date."""
    if self.n_messages_sent is None:
      if self.draft_count_by_user is None:
        self.calculate_draft_count_by_user()
      self.calculate_updates_for()
      try:
        # Don't change self.modified when filling cache values. AFAICT, there's
        # no better way...
        self.__class__.modified.auto_now = False
        return self.put_async()
      finally:
        self.__class__.modified.auto_now = True

  def get_patchset_info(self, user, patchset_id):
    """Returns a list of patchsets for the issue, and calculates/caches data
    into the |patchset_id|'th one with a variety of non-standard attributes.

    Args:
      user (User) - The user to include drafts for.
      patchset_id (int) - The ID of the PatchSet to calculated info for.
        If this is None, it defaults to the newest PatchSet for this Issue.
    """
    patchsets = list(self.patchsets)
    try:
      if not patchset_id and patchsets:
        patchset_id = patchsets[-1].key.id()

      if user:
        drafts = list(Comment.query(
            Comment.draft == True, Comment.author == user, ancestor=self.key))
      else:
        drafts = []
      comments = list(Comment.query(Comment.draft == False, ancestor=self.key))
      for c in drafts:
        c.ps_key = c.patch_key.get().patchset_key
      patchset_id_mapping = {}  # Maps from patchset id to its ordering number.
      for patchset in patchsets:
        patchset_id_mapping[patchset.key.id()] = len(patchset_id_mapping) + 1
        patchset.n_drafts = sum(c.ps_key == patchset.key for c in drafts)
        patchset.patches_cache = None
        patchset.parsed_patches = None
        patchset.total_added = 0
        patchset.total_removed = 0
        if patchset_id == patchset.key.id():
          patchset.patches_cache = list(patchset.patches)
          for patch in patchset.patches_cache:
            pkey = patch.key
            patch._num_comments = sum(c.patch_key == pkey for c in comments)
            if user:
              patch._num_my_comments = sum(
                  c.patch_key == pkey and c.author == user
                  for c in comments)
            else:
              patch._num_my_comments = 0
            patch._num_drafts = sum(c.patch_key == pkey for c in drafts)
            # Reduce memory usage: if this patchset has lots of added/removed
            # files (i.e. > 100) then we'll get MemoryError when rendering the
            # response.  Each Patch entity is using a lot of memory if the
            # files are large, since it holds the entire contents.  Call
            # num_chunks and num_drafts first though since they depend on text.
            # These are 'active' properties and have side-effects when looked
            # up.
            # pylint: disable=W0104
            patch.num_chunks
            patch.num_drafts
            patch.num_added
            patch.num_removed
            patch.text = None
            patch._lines = None
            patch.parsed_deltas = []
            for delta in patch.delta:
              # If delta is not in patchset_id_mapping, it's because of internal
              # corruption.
              if delta in patchset_id_mapping:
                patch.parsed_deltas.append([patchset_id_mapping[delta], delta])
              else:
                logging.error(
                    'Issue %d: %d is missing from %s',
                    self.key.id(), delta, patchset_id_mapping)
            if not patch.is_binary:
              patchset.total_added += patch.num_added
              patchset.total_removed += patch.num_removed
      return patchsets
    finally:
      # Reduce memory usage (see above comment).
      for patchset in patchsets:
        patchset.parsed_patches = None

  def get_landed_date(self):
    """Returns approximate date when original_issue was landed or None."""
    for message in reversed(list(self.messages)):
      if not message.issue_was_closed:
        continue
      for l in message.text.splitlines():
        if COMMITTED_MSG_RE.match(l):
          return message.date
    return None

  def get_time_since_landed(self):
    """Returns approximate time since issue was landed or None."""
    landed = self.get_landed_date()
    if landed:
      return datetime.datetime.now() - landed
    return None


def _calculate_delta(patch, patchset_id, patchsets):
  """Calculates which files in earlier patchsets this file differs from.

  Args:
    patch: The file to compare.
    patchset_id: The file's patchset's key id.
    patchsets: A list of existing patchsets.

  Returns:
    A list of patchset ids.
  """
  delta = []
  for other in patchsets:
    if patchset_id == other.key.id():
      break
    if not hasattr(other, 'parsed_patches'):
      other.parsed_patches = None  # cache variable for already parsed patches
    if other.data or other.parsed_patches:
      # Loading all the Patch entities in every PatchSet takes too long
      # (DeadLineExceeded) and consumes a lot of memory (MemoryError) so instead
      # just parse the patchset's data.  Note we can only do this if the
      # patchset was small enough to fit in the data property.
      if other.parsed_patches is None:
        # PatchSet.data is stored as ndb.Blob (str). Try to convert it
        # to unicode so that Python doesn't need to do this conversion
        # when comparing text and patch.text, which is unicode.
        try:
          other.parsed_patches = engine_utils.SplitPatch(
              other.data.decode('utf-8'))
        except UnicodeDecodeError:  # Fallback to str - unicode comparison.
          other.parsed_patches = engine_utils.SplitPatch(other.data)
        other.data = None  # Reduce memory usage.
      for filename, text in other.parsed_patches:
        if filename == patch.filename:
          if text != patch.text:
            delta.append(other.key.id())
          break
      else:
        # We could not find the file in the previous patchset. It must
        # be new wrt that patchset.
        delta.append(other.key.id())
    else:
      # other (patchset) is too big to hold all the patches inside itself, so
      # we need to go to the datastore.  Use the index to see if there's a
      # patch against our current file in other.
      query = Patch.query(
          Patch.filename == patch.filename, ancestor=other.key)
      other_patches = query.fetch(100)
      if other_patches and len(other_patches) > 1:
        logging.info("Got %s patches with the same filename for a patchset",
                     len(other_patches))
      for op in other_patches:
        if op.text != patch.text:
          delta.append(other.key.id())
          break
      else:
        # We could not find the file in the previous patchset. It must
        # be new wrt that patchset.
        delta.append(other.key.id())

  return delta


class TryJobResult(ndb.Model):
  """Try jobs are associated to a patchset.

  Multiple try jobs can be associated to a single patchset.
  """
  # The first 6 values come from buildbot/status/results.py, and should remain
  # sync'ed.  The last is used internally to make a try job that should be
  # tried with the commit queue, but has not been sent yet.
  SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY, TRYPENDING = range(7)
  STARTED = -1

  OK = (SUCCESS, WARNINGS, SKIPPED)
  FAIL = (FAILURE, EXCEPTION)
  # Define the priority level of result value when updating it.
  PRIORITIES = (
      (TRYPENDING,),
      (STARTED, None),
      (RETRY,),
      OK,
      FAIL,
  )

  # Parent is PatchSet
  url = ndb.StringProperty()
  result = ndb.IntegerProperty()
  master = ndb.StringProperty()
  builder = ndb.StringProperty()
  parent_name = ndb.StringProperty()
  slave = ndb.StringProperty()
  buildnumber = ndb.IntegerProperty()
  reason = ndb.StringProperty()
  revision = ndb.StringProperty()
  timestamp = ndb.DateTimeProperty(auto_now_add=True)
  clobber = ndb.BooleanProperty()
  tests = ndb.StringProperty(repeated=True)
  # Should be an entity.
  project = ndb.StringProperty()
  # The user that requested this try job, which may not be the same person
  # that owns the issue.
  requester = ndb.UserProperty(auto_current_user_add=True)
  category = ndb.StringProperty()

  # JSON dictionary of build properties.
  build_properties = ndb.TextProperty(default='{}')

  @property
  def status(self):
    """Returns a string equivalent so it can be used in CSS styles."""
    if self.result in (self.SUCCESS, self.WARNINGS):
      return 'success'
    if self.result == self.SKIPPED:
      return 'skipped'
    elif self.result == self.EXCEPTION:
      return 'exception'
    elif self.result in self.FAIL:
      return 'failure'
    elif self.result == self.TRYPENDING:
      return 'try-pending'
    else:
      return 'pending'

  @classmethod
  def result_priority(cls, result):
    """The higher the more important."""
    for index, possible_values in enumerate(cls.PRIORITIES):
      if result in possible_values:
        return index
    return None


class PatchSet(ndb.Model):
  """A set of patchset uploaded together.

  This is a descendant of an Issue and has Patches as descendants.
  """
  # name='issue' is needed for backward compatability with existing data.
  # Note: we could write a mapreduce to rewrite data from the issue field
  # to a new issue_key field, which would allow removal of name='issue',
  # but it would require that migration step on every Rietveld instance.
  issue_key = ndb.KeyProperty(name='issue', kind=Issue)  # == parent
  message = ndb.StringProperty()
  data = ndb.BlobProperty()
  url = ndb.StringProperty()
  created = ndb.DateTimeProperty(auto_now_add=True)
  modified = ndb.DateTimeProperty(auto_now=True)
  n_comments = ndb.IntegerProperty(default=0)
  # TODO(maruel): Deprecated, remove once the live instance has all its data
  # converted to TryJobResult instances.
  build_results = ndb.StringProperty(repeated=True)
  depends_on_patchset = ndb.StringProperty()
  dependent_patchsets = ndb.StringProperty(repeated=True)
  cq_status_url = ndb.StringProperty()

  @property
  def depends_on_tokens(self):
    tokens = None
    if self.depends_on_patchset:
      issue_id, patchset_id = self.depends_on_patchset.split(':')
      issue = Issue.get_by_id(int(issue_id))
      patchset = PatchSet.get_by_id(int(patchset_id), parent=issue.key)
      tokens = (issue, patchset)
    return tokens

  @property
  def dependent_tokens(self):
    tokens = []
    if self.dependent_patchsets:
      for dependent_patchset in self.dependent_patchsets:
        issue_id, patchset_id = dependent_patchset.split(':')
        issue = Issue.get_by_id(int(issue_id))
        patchset = PatchSet.get_by_id(int(patchset_id), parent=issue.key)
        tokens.append((issue, patchset))
    return tokens

  @property
  def num_patches(self):
    """Return the number of patches in this patchset."""
    return Patch.query(ancestor=self.key).count(
      settings.MAX_PATCHES_PER_PATCHSET)

  @property
  def patches(self):
    def reading_order(patch):
      """Sort patches by filename, except .h files before .c files."""
      base, ext = os.path.splitext(patch.filename)
      return (base, ext not in ('.h', '.hxx', '.hpp'), ext)

    patch_list = Patch.query(ancestor=self.key).fetch(
      settings.MAX_PATCHES_PER_PATCHSET,
      batch_size=settings.MAX_PATCHES_PER_PATCHSET)
    return sorted(patch_list, key=reading_order)

  def update_comment_count(self, n):
    """Increment the n_comments property by n."""
    self.n_comments = self.num_comments + n

  @property
  def num_comments(self):
    """The number of non-draft comments for this issue.

    This is almost an alias for self.n_comments, except that if
    n_comments is None, 0 is returned.
    """
    # For older patchsets n_comments is None.
    return self.n_comments or 0

  def calculate_deltas(self):
    patchset_id = self.key.id()
    patchsets = None
    q = Patch.query(Patch.delta_calculated == False, ancestor=self.key)
    for patch in q:
      if patchsets is None:
        # patchsets is retrieved on first iteration because patchsets
        # isn't needed outside the loop at all.
        patchsets = list(self.issue_key.get().patchsets)
      patch.delta = _calculate_delta(patch, patchset_id, patchsets)
      patch.delta_calculated = True
      patch.put()

  _try_job_results = None

  @property
  def try_job_results(self):
    """Lazy load all the TryJobResult objects associated to this PatchSet.

    Note the value is cached and doesn't expose a method to be refreshed.
    """
    if self._try_job_results is None:
      self._try_job_results = TryJobResult.query(ancestor=self.key).fetch(1000)

      # Append fake object for all build_results properties.
      # TODO(maruel): Deprecated. Delete this code as soon as the live
      # instance migrated to TryJobResult objects.
      SEPARATOR = '|'
      for build_result in self.build_results:
        (platform_id, status, details_url) = build_result.split(SEPARATOR, 2)
        if status == 'success':
          result = TryJobResult.SUCCESS
        elif status == 'failure':
          result = TryJobResult.FAILURE
        else:
          result = TryJobResult.STARTED
        self._try_job_results.append(
            TryJobResult(
              parent=self.key,
              url=details_url,
              result=result,
              builder=platform_id,
              timestamp=self.modified))

      def GetKey(job):
        """Gets the key used to order jobs in the results list.

        We want pending jobs to appear first in the list, so these jobs
        return datetime.datetime.max, as the sort is in reverse chronological
        order."""
        if job.result == TryJobResult.TRYPENDING:
          return datetime.datetime.max
        return job.timestamp

      self._try_job_results.sort(key=GetKey, reverse=True)
    return self._try_job_results


class Message(ndb.Model):
  """A copy of a message sent out in email.

  This is a descendant of an Issue.
  """
  # name='issue' is needed for backward compatability with existing data.
  issue_key = ndb.KeyProperty(name='issue', kind=Issue)  # == parent
  subject = ndb.StringProperty()
  sender = ndb.StringProperty()
  recipients = ndb.StringProperty(repeated=True)
  date = ndb.DateTimeProperty(auto_now_add=True)
  text = ndb.TextProperty()
  draft = ndb.BooleanProperty(default=False)
  in_reply_to_key = ndb.KeyProperty(name='in_reply_to', kind='Message')
  issue_was_closed = ndb.BooleanProperty(default=False)
  # If message came in through email, we might not count "lgtm"
  was_inbound_email = ndb.BooleanProperty(default=False)
  # Whether this Message was auto generated in response to an action the system
  # would like to log. Eg: Checking CQ checkbox or changing reviewers.
  auto_generated = ndb.BooleanProperty(default=False)
  # Patchset that the user was responding to.
  patchset_key = ndb.KeyProperty(PatchSet)

  _approval = None
  _disapproval = None

  LGTM_RE = re.compile(r'\blgtm\b')
  NOT_LGTM_RE = re.compile(r'\bnot lgtm\b')

  def find(self, regex, owner_allowed=False):
    """Returns True when the message has a string matching regex in it.

    - Must not be written by the issue owner.
    - Must contain regex in a line that doesn't start with '>'.
    - Must not be commit-bot.
    """
    issue = self.issue_key.get()
    if not owner_allowed and issue.owner.email() == self.sender:
      return False
    if self.sender == 'commit-bot@chromium.org':
      return False
    return any(
        True for line in self.text.lower().splitlines()
        if not line.strip().startswith('>') and regex.search(line))

  @property
  def approval(self):
    """Is True when the message represents an approval of the review."""
    if (self.was_inbound_email and
        not settings.RIETVELD_INCOMING_MAIL_RECOGNIZE_LGTM):
      return False
    if self._approval is None:
      self._approval = self.find(self.LGTM_RE) and not self.disapproval
    return self._approval

  @property
  def disapproval(self):
    """Is True when the message represents a disapproval of the review."""
    if self._disapproval is None:
      self._disapproval = self.find(self.NOT_LGTM_RE)
    return self._disapproval


class Content(ndb.Model):
  """The content of a text file.

  This is a descendant of a Patch.
  """

  # parent => Patch
  text = ndb.TextProperty()
  data = ndb.BlobProperty()
  # Checksum over text or data depending on the type of this content.
  checksum = ndb.TextProperty()
  is_uploaded = ndb.BooleanProperty(default=False)
  is_bad = ndb.BooleanProperty(default=False)
  file_too_large = ndb.BooleanProperty(default=False)

  @property
  def lines(self):
    """The text split into lines, retaining line endings."""
    if not self.text:
      return []
    return self.text.splitlines(True)


class Patch(ndb.Model):
  """A single patch, i.e. a set of changes to a single file.

  This is a descendant of a PatchSet.
  """

  patchset_key = ndb.KeyProperty(name='patchset', kind=PatchSet)  # == parent
  filename = ndb.StringProperty()
  status = ndb.StringProperty()  # 'A', 'A +', 'M', 'D' etc
  text = ndb.TextProperty()
  content_key = ndb.KeyProperty(name='content', kind=Content)
  patched_content_key = ndb.KeyProperty(name='patched_content', kind=Content)
  is_binary = ndb.BooleanProperty(default=False)
  # Ids of patchsets that have a different version of this file.
  delta = ndb.IntegerProperty(repeated=True)
  delta_calculated = ndb.BooleanProperty(default=False)

  _lines = None

  @property
  def lines(self):
    """The patch split into lines, retaining line endings.

    The value is cached.
    """
    if self._lines is not None:
      return self._lines

    # Note that self.text has already had newlines normalized on upload.
    # And, any ^L characters are explicitly not treated as breaks.
    bare_lines = self.text.split('\n')
    self._lines = [bare_line + '\n' for bare_line in bare_lines]
    return self._lines

  _property_changes = None

  @property
  def property_changes(self):
    """The property changes split into lines.

    The value is cached.
    """
    if self._property_changes != None:
      return self._property_changes
    self._property_changes = []
    match = re.search('^Property changes on.*\n'+'_'*67+'$', self.text,
                      re.MULTILINE)
    if match:
      self._property_changes = self.text[match.end():].splitlines()
    return self._property_changes

  _num_added = None

  @property
  def num_added(self):
    """The number of line additions in this patch.

    The value is cached.
    """
    if self._num_added is None:
      self._num_added = self.count_startswith('+') - 1
    return self._num_added

  _num_removed = None

  @property
  def num_removed(self):
    """The number of line removals in this patch.

    The value is cached.
    """
    if self._num_removed is None:
      self._num_removed = self.count_startswith('-') - 1
    return self._num_removed

  _num_chunks = None

  @property
  def num_chunks(self):
    """The number of 'chunks' in this patch.

    A chunk is a block of lines starting with '@@'.

    The value is cached.
    """
    if self._num_chunks is None:
      self._num_chunks = self.count_startswith('@@')
    return self._num_chunks

  _num_comments = None

  @property
  def num_comments(self):
    """The number of non-draft comments for this patch.

    The value is cached.
    """
    if self._num_comments is None:
      self._num_comments = Comment.query(
          Comment.draft == False, ancestor=self.key).count()
    return self._num_comments

  _num_my_comments = None

  def num_my_comments(self):
    """The number of non-draft comments for this patch by the logged in user.

    The value is cached.
    """
    if self._num_my_comments is None:
      account = Account.current_user_account
      if account is None:
        self._num_my_comments = 0
      else:
        query = Comment.query(
            Comment.draft == False, Comment.author == account.user,
            ancestor=self.key)
        self._num_my_comments = query.count()
    return self._num_my_comments

  _num_drafts = None

  @property
  def num_drafts(self):
    """The number of draft comments on this patch for the current user.

    The value is expensive to compute, so it is cached.
    """
    if self._num_drafts is None:
      account = Account.current_user_account
      if account is None:
        self._num_drafts = 0
      else:
        query = Comment.query(
            Comment.draft == True, Comment.author == account.user,
            ancestor=self.key)
        self._num_drafts = query.count()
    return self._num_drafts

  def count_startswith(self, prefix):
    """Returns the number of lines with the specified prefix."""
    return sum(1 for l in self.lines if l.startswith(prefix))

  def get_content(self):
    """Get self.content, or fetch it if necessary.

    This is the content of the file to which this patch is relative.

    Returns:
      a Content instance.

    Raises:
      FetchError: If there was a problem fetching it.
    """
    try:
      if self.content_key is not None:
        content = self.content_key.get()
        if content.is_bad:
          msg = 'Bad content. Try to upload again.'
          logging.warn('Patch.get_content: %s', msg)
          raise FetchError(msg)
        if content.file_too_large:
          msg = 'File too large.'
          logging.warn('Patch.get_content: %s', msg)
          raise FetchError(msg)
        if content.is_uploaded and content.text == None:
          msg = 'Upload of %s in progress.' % self.filename
          logging.warn('Patch.get_content: %s', msg)
          raise FetchError(msg)
        else:
          return content
    except db.Error:
      # This may happen when a Content entity was deleted behind our back.
      self.content_key = None

    content = self.fetch_base()
    self.content_key = content.key
    return content

  def get_patched_content(self):
    """Get this patch's patched_content, computing it if necessary.

    This is the content of the file after applying this patch.

    Returns:
      a Content instance.

    Raises:
      FetchError: If there was a problem fetching the old content.
    """
    try:
      if self.patched_content_key is not None:
        return self.patched_content_key.get()
    except db.Error:
      # This may happen when a Content entity was deleted behind our back.
      self.patched_content_key = None

    old_lines = self.get_content().text.splitlines(True)
    logging.info('Creating patched_content for %s', self.filename)
    chunks = patching.ParsePatchToChunks(self.lines, self.filename)
    new_lines = []
    for _, _, new in patching.PatchChunks(old_lines, chunks):
      new_lines.extend(new)
    text = ''.join(new_lines)
    patched_content = Content(text=text, parent=self.key)
    self.patched_content_key = patched_content.key
    return patched_content

  @property
  def no_base_file(self):
    """Returns True iff the base file is not available."""
    return self.content_key and self.content_key.get().file_too_large

  def fetch_base(self):
    """Fetch base file for the patch.

    Returns:
      A models.Content instance.

    Raises:
      FetchError: For any kind of problem fetching the content.
    """
    rev = patching.ParseRevision(self.lines)
    if rev is not None:
      if rev == 0:
        # rev=0 means it's a new file.
        return Content(text=u'', parent=self.key)

    # AppEngine can only fetch URLs that db.Link() thinks are OK,
    # so try converting to a db.Link() here.
    issue = self.patchset_key.get().issue_key.get()
    try:
      base = db.Link(issue.base)
    except db.BadValueError:
      msg = 'Invalid base URL for fetching: %s' % issue.base
      logging.warn(msg)
      raise FetchError(msg)

    url = utils.make_url(base, self.filename, rev)
    logging.info('Fetching %s', url)
    try:
      result = urlfetch.fetch(url, validate_certificate=True)
    except urlfetch.Error, err:
      msg = 'Error fetching %s: %s: %s' % (url, err.__class__.__name__, err)
      logging.warn('FetchBase: %s', msg)
      raise FetchError(msg)
    if result.status_code != 200:
      msg = 'Error fetching %s: HTTP status %s' % (url, result.status_code)
      logging.warn('FetchBase: %s', msg)
      raise FetchError(msg)
    return Content(text=utils.to_dbtext(utils.unify_linebreaks(result.content)),
                   parent=self.key)



class Comment(ndb.Model):
  """A Comment for a specific line of a specific file.

  This is a descendant of a Patch.
  """

  patch_key = ndb.KeyProperty(name='patch', kind=Patch)  # == parent
  message_id = ndb.StringProperty()  # == key_name
  author = auth_utils.AnyAuthUserProperty(auto_current_user_add=True)
  date = ndb.DateTimeProperty(auto_now=True)
  lineno = ndb.IntegerProperty()
  text = ndb.TextProperty()
  left = ndb.BooleanProperty()
  draft = ndb.BooleanProperty(required=True, default=True)

  buckets = None
  shorttext = None

  def complete(self):
    """Set the shorttext and buckets attributes."""
    # TODO(guido): Turn these into caching proprties instead.

    # The strategy for buckets is that we want groups of lines that
    # start with > to be quoted (and not displayed by
    # default). Whitespace-only lines are not considered either quoted
    # or not quoted. Same goes for lines that go like "On ... user
    # wrote:".
    cur_bucket = []
    quoted = None
    self.buckets = []

    def _Append():
      if cur_bucket:
        self.buckets.append(Bucket(text="\n".join(cur_bucket),
                                   quoted=bool(quoted)))

    lines = self.text.splitlines()
    for line in lines:
      if line.startswith("On ") and line.endswith(":"):
        pass
      elif line.startswith(">"):
        if quoted is False:
          _Append()
          cur_bucket = []
        quoted = True
      elif line.strip():
        if quoted is True:
          _Append()
          cur_bucket = []
        quoted = False
      cur_bucket.append(line)

    _Append()

    self.shorttext = self.text.lstrip()[:50].rstrip()
    # Grab the first 50 chars from the first non-quoted bucket
    for bucket in self.buckets:
      if not bucket.quoted:
        self.shorttext = bucket.text.lstrip()[:50].rstrip()
        break


class Bucket(ndb.Model):
  """A 'Bucket' of text.

  A comment may consist of multiple text buckets, some of which may be
  collapsed by default (when they represent quoted text).

  NOTE: This entity is never written to the database.  See Comment.complete().
  """
  # TODO(guido): Flesh this out.

  text = ndb.TextProperty()
  quoted = ndb.BooleanProperty()


### Accounts ###


class Account(ndb.Model):
  """Maps a user or email address to a user-selected nickname, and more.

  Nicknames do not have to be unique.

  The default nickname is generated from the email address by
  stripping the first '@' sign and everything after it.  The email
  should not be empty nor should it start with '@' (AssertionError
  error is raised if either of these happens).

  This also holds a list of ids of starred issues.  The expectation
  that you won't have more than a dozen or so starred issues (a few
  hundred in extreme cases) and the memory used up by a list of
  integers of that size is very modest, so this is an efficient
  solution.  (If someone found a use case for having thousands of
  starred issues we'd have to think of a different approach.)
  """

  user = auth_utils.AnyAuthUserProperty(auto_current_user_add=True,
                                        required=True)
  email = ndb.StringProperty(required=True)  # key == <email>
  nickname = ndb.StringProperty(required=True)
  default_context = ndb.IntegerProperty(default=settings.DEFAULT_CONTEXT,
                                        choices=CONTEXT_CHOICES)
  default_column_width = ndb.IntegerProperty(
      default=settings.DEFAULT_COLUMN_WIDTH)
  default_tab_spaces = ndb.IntegerProperty(default=settings.DEFAULT_TAB_SPACES)
  created = ndb.DateTimeProperty(auto_now_add=True)
  modified = ndb.DateTimeProperty(auto_now=True)
  stars = ndb.IntegerProperty(repeated=True)  # Issue ids of all starred issues
  fresh = ndb.BooleanProperty()
  deprecated_ui = ndb.BooleanProperty(default=True)
  notify_by_email = ndb.BooleanProperty(default=True)
  notify_by_chat = ndb.BooleanProperty(default=False)
  # Spammer; only blocks sending messages, not uploading issues.
  blocked = ndb.BooleanProperty(default=False)

  # Current user's Account.  Updated by middleware.AddUserToRequestMiddleware.
  current_user_account = None

  lower_email = ndb.ComputedProperty(lambda self: self.email.lower())
  lower_nickname = ndb.ComputedProperty(lambda self: self.nickname.lower())
  xsrf_secret = ndb.BlobProperty()

  # The user can opt-in to adding +foo to the end of their email username
  # where foo is one of owner, reviewer, cc.
  add_plus_role = ndb.BooleanProperty()

  # The user can opt-in to displaying generated messages by default.
  display_generated_msgs = ndb.BooleanProperty(default=False)

  # The user can opt-in to displaying experimental tryjob results
  # if available by default.
  display_exp_tryjob_results = ndb.BooleanProperty(default=False)

  # Users typically trigger notification emails that are sent from
  # the user's email address.  However, some legitimate users have
  # email addresses at domains that are often abused by spammers,
  # causing their notifications to be classified as spamm.  So,
  # such users can opt to send from reply@ instead.
  send_from_email_addr = ndb.BooleanProperty(default=True)

  @classmethod
  def get_id_for_email(cls, email):
    return '<%s>' % email

  @classmethod
  def get_account_for_user(cls, user, autocreate=True):
    """Get the Account for a user, creating a default one if desired."""
    email = user.email()
    assert email
    id_str = cls.get_id_for_email(email)
    # Since usually the account already exists, first try getting it
    # without the transaction implied by get_or_insert().
    account = cls.get_by_id(id_str)
    if account is not None:
      return account
    if not autocreate:
      return None
    nickname = cls.create_nickname_for_user(user)
    return cls.get_or_insert(
      id_str, user=user, email=email, nickname=nickname, fresh=True)

  @classmethod
  def create_nickname_for_user(cls, user):
    """Returns a unique nickname for a user."""
    name = nickname = user.email().split('@', 1)[0]
    next_char = chr(ord(nickname[0].lower())+1)
    # This uses eventual consistency and cannot be made strongly consistent.
    existing_nicks = [
      account.lower_nickname for account in cls.query(
          cls.lower_nickname >= nickname.lower(),
          cls.lower_nickname < next_char)]
    suffix = 0
    while nickname.lower() in existing_nicks:
      suffix += 1
      nickname = '%s%d' % (name, suffix)
    return nickname

  @classmethod
  def get_nickname_for_user(cls, user):
    """Get the nickname for a user."""
    return cls.get_account_for_user(user).nickname

  @classmethod
  def get_account_for_email(cls, email):
    """Get the Account for an email address, or return None."""
    assert email
    id_str = '<%s>' % email
    return cls.get_by_id(id_str)

  @classmethod
  def get_accounts_for_emails(cls, emails):
    """Get the Accounts for each of a list of email addresses."""
    keys = [ndb.Key(cls, '<%s>' % email) for email in emails]
    return ndb.get_multi(keys)

  @classmethod
  def get_multiple_accounts_by_email(cls, emails):
    """Get multiple accounts.  Returns a dict by email."""
    results = {}
    keys = []
    for email in emails:
      if cls.current_user_account and email == cls.current_user_account.email:
        results[email] = cls.current_user_account
      else:
        keys.append(ndb.Key(cls,'<%s>' % email))
    if keys:
      accounts = ndb.get_multi(keys)
      for account in accounts:
        if account is not None:
          results[account.email] = account
    return results

  @classmethod
  def get_nickname_for_email(cls, email, default=None):
    """Get the nickname for an email address, possibly a default.

    If default is None a generic nickname is computed from the email
    address.

    Args:
      email: email address.
      default: If given and no account is found, returned as the default value.
    Returns:
      Nickname for given email.
    """
    account = cls.get_account_for_email(email)
    if account is not None and account.nickname:
      return account.nickname
    if default is not None:
      return default
    return email.replace('@', '_')

  @classmethod
  def get_account_for_nickname(cls, nickname):
    """Get the list of Accounts that have this nickname."""
    assert nickname
    assert '@' not in nickname
    # This uses eventual consistency and cannot be made strongly consistent.
    return cls.query(cls.lower_nickname == nickname.lower()).get()

  @classmethod
  def get_email_for_nickname(cls, nickname):
    """Turn a nickname into an email address.

    If the nickname is not unique or does not exist, this returns None.
    """
    account = cls.get_account_for_nickname(nickname)
    if account is None:
      return None
    return account.email

  def user_has_selected_nickname(self):
    """Return True if the user picked the nickname.

    Normally this returns 'not self.fresh', but if that property is
    None, we assume that if the created and modified timestamp are
    within 2 seconds, the account is fresh (i.e. the user hasn't
    selected a nickname yet).  We then also update self.fresh, so it
    is used as a cache and may even be written back if we're lucky.
    """
    if self.fresh is None:
      delta = self.created - self.modified
      # Simulate delta = abs(delta)
      if delta.days < 0:
        delta = -delta
      self.fresh = (delta.days == 0 and delta.seconds < 2)
    return not self.fresh

  _drafts = None

  @property
  def drafts(self):
    """A list of issue ids that have drafts by this user.

    This is cached in memcache.
    """
    if self._drafts is None:
      if self._initialize_drafts():
        self._save_drafts()
    return self._drafts

  def update_drafts(self, issue, have_drafts=None):
    """Update the user's draft status for this issue.

    Args:
      issue: an Issue instance.
      have_drafts: optional bool forcing the draft status.  By default,
          issue.num_drafts is inspected (which may query the datastore).

    The Account is written to the datastore if necessary.
    """
    dirty = False
    if self._drafts is None:
      dirty = self._initialize_drafts()
    keyid = issue.key.id()
    if have_drafts is None:
      # Beware, this may do a query.
      have_drafts = bool(issue.get_num_drafts(self.user))
    if have_drafts:
      if keyid not in self._drafts:
        self._drafts.append(keyid)
        dirty = True
    else:
      if keyid in self._drafts:
        self._drafts.remove(keyid)
        dirty = True
    if dirty:
      self._save_drafts()

  def _initialize_drafts(self):
    """Initialize self._drafts from scratch.

    This mostly exists as a schema conversion utility.

    Returns:
      True if the user should call self._save_drafts(), False if not.
    """
    drafts = memcache.get('user_drafts:' + self.email)
    if drafts is not None:
      self._drafts = drafts
      ##logging.info('HIT: %s -> %s', self.email, self._drafts)
      return False
    # We're looking for the Issue key id.  The ancestry of comments goes:
    # Issue -> PatchSet -> Patch -> Comment.
    # This uses eventual consistency and cannot be made strongly consistent.
    draft_query = Comment.query(
        Comment.author == self.user, Comment.draft == True)
    issue_ids = set(comment.key.parent().parent().parent().id()
                    for comment in draft_query)
    self._drafts = list(issue_ids)
    ##logging.info('INITIALIZED: %s -> %s', self.email, self._drafts)
    return True

  def _save_drafts(self):
    """Save self._drafts to memcache."""
    ##logging.info('SAVING: %s -> %s', self.email, self._drafts)
    memcache.set('user_drafts:' + self.email, self._drafts, 3600)

  def get_xsrf_token(self, offset=0):
    """Return an XSRF token for the current user."""
    # This code assumes that
    # self.user.email() == auth_utils.get_current_user().email()
    current_user = auth_utils.get_current_user()
    if self.user.user_id() != current_user.user_id():
      # Mainly for Google Account plus conversion.
      logging.info('Updating user_id for %s from %s to %s' % (
        self.user.email(), self.user.user_id(), current_user.user_id()))
      self.user = current_user
      self.put()
    if not self.xsrf_secret:
      self.xsrf_secret = os.urandom(8)
      self.put()
    m = md5.new(self.xsrf_secret)
    email_str = self.lower_email
    if isinstance(email_str, unicode):
      email_str = email_str.encode('utf-8')
    m.update(self.lower_email)
    when = int(time.time()) // 3600 + offset
    m.update(str(when))
    return m.hexdigest()
