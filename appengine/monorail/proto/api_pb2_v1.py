# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Protocol buffers for Monorail API."""

from endpoints import ResourceContainer
from protorpc import messages
from protorpc import message_types

from proto import usergroup_pb2


########################## Helper Message ##########################


class ErrorMessage(messages.Message):
  """Request error."""
  code = messages.IntegerField(
      1, required=True, variant=messages.Variant.INT32)
  reason = messages.StringField(2, required=True)
  message = messages.StringField(3, required=True)


class Status(messages.Message):
  """Issue status."""
  status = messages.StringField(1, required=True)
  meansOpen = messages.BooleanField(2, required=True)
  description = messages.StringField(3)


class Label(messages.Message):
  """Issue label."""
  label = messages.StringField(1, required=True)
  description = messages.StringField(2)


class Prompt(messages.Message):
  """Default issue template values."""
  name = messages.StringField(1, required=True)
  title = messages.StringField(2)
  description = messages.StringField(3)
  titleMustBeEdited = messages.BooleanField(4)
  status = messages.StringField(5)
  labels = messages.StringField(6, repeated=True)
  membersOnly = messages.BooleanField(7)
  defaultToMember = messages.BooleanField(8)
  componentRequired = messages.BooleanField(9)


class Role(messages.Enum):
  """User role."""
  owner = 1
  member = 2
  contributor = 3


class IssueState(messages.Enum):
  """Issue state."""
  closed = 0
  open = 1


class CannedQuery(messages.Enum):
  """Canned query to search issues."""
  all = 0
  new = 1
  open = 2
  owned = 3
  reported = 4
  starred = 5
  to_verify = 6


class AtomPerson(messages.Message):
  """Atomic person."""
  name = messages.StringField(1, required=True)
  htmlLink = messages.StringField(2)
  kind = messages.StringField(3)
  last_visit_days_ago = messages.IntegerField(4)
  email_bouncing = messages.BooleanField(5)
  vacation_message = messages.StringField(6)


class Attachment(messages.Message):
  """Issue attachment."""
  attachmentId = messages.IntegerField(
      1, variant=messages.Variant.INT64, required=True)
  fileName = messages.StringField(2, required=True)
  fileSize = messages.IntegerField(
      3, required=True, variant=messages.Variant.INT32)
  mimetype = messages.StringField(4, required=True)
  isDeleted = messages.BooleanField(5)


class IssueRef(messages.Message):
  "Issue reference."
  issueId = messages.IntegerField(
      1, required=True, variant=messages.Variant.INT32)
  projectId = messages.StringField(2)
  kind = messages.StringField(3)


class FieldValueOperator(messages.Enum):
  """Operator of field values."""
  add = 1
  remove = 2
  clear = 3


class FieldValue(messages.Message):
  """Custom field values."""
  fieldName = messages.StringField(1, required=True)
  fieldValue = messages.StringField(2)
  derived = messages.BooleanField(3, default=False)
  operator = messages.EnumField(FieldValueOperator, 4, default='add')
  phaseName = messages.StringField(5)
  approvalName = messages.StringField(6)


class Update(messages.Message):
  """Issue update."""
  summary = messages.StringField(1)
  status = messages.StringField(2)
  owner = messages.StringField(3)
  labels = messages.StringField(4, repeated=True)
  cc = messages.StringField(5, repeated=True)
  blockedOn = messages.StringField(6, repeated=True)
  blocking = messages.StringField(7, repeated=True)
  mergedInto = messages.StringField(8)
  kind = messages.StringField(9)
  components = messages.StringField(10, repeated=True)
  moveToProject = messages.StringField(11)
  fieldValues = messages.MessageField(FieldValue, 12, repeated=True)
  is_description = messages.BooleanField(13)


class ApprovalUpdate(messages.Message):
  """Approval update."""
  approvers = messages.StringField(1, repeated=True)
  status = messages.StringField(2)
  kind = messages.StringField(3)
  # TODO(jojwang): monorail:4229, add fieldValues


class ProjectIssueConfig(messages.Message):
  """Issue configuration of project."""
  kind = messages.StringField(1)
  restrictToKnown = messages.BooleanField(2)
  defaultColumns = messages.StringField(3, repeated=True)
  defaultSorting = messages.StringField(4, repeated=True)
  statuses = messages.MessageField(Status, 5, repeated=True)
  labels = messages.MessageField(Label, 6, repeated=True)
  prompts = messages.MessageField(Prompt, 7, repeated=True)
  defaultPromptForMembers = messages.IntegerField(
      8, variant=messages.Variant.INT32)
  defaultPromptForNonMembers = messages.IntegerField(
      9, variant=messages.Variant.INT32)
  usersCanSetLabels = messages.BooleanField(10)


class Phase(messages.Message):
  """Issue phase details."""
  phaseName = messages.StringField(1)
  rank = messages.IntegerField(2)


class IssueCommentWrapper(messages.Message):
  """Issue comment details."""
  attachments = messages.MessageField(Attachment, 1, repeated=True)
  author = messages.MessageField(AtomPerson, 2)
  canDelete = messages.BooleanField(3)
  content = messages.StringField(4)
  deletedBy = messages.MessageField(AtomPerson, 5)
  id = messages.IntegerField(6, variant=messages.Variant.INT32)
  published = message_types.DateTimeField(7)
  updates = messages.MessageField(Update, 8)
  kind = messages.StringField(9)
  is_description = messages.BooleanField(10)


class ApprovalCommentWrapper(messages.Message):
  """Approval comment details."""
  attachments = messages.MessageField(Attachment, 1, repeated=True)
  author = messages.MessageField(AtomPerson, 2)
  canDelete = messages.BooleanField(3)
  content = messages.StringField(4)
  deletedBy = messages.MessageField(AtomPerson, 5)
  id = messages.IntegerField(6, variant=messages.Variant.INT32)
  published = message_types.DateTimeField(7)
  approvalUpdates = messages.MessageField(ApprovalUpdate, 8)
  kind = messages.StringField(9)
  is_description = messages.BooleanField(10)


class ApprovalStatus(messages.Enum):
  """Allowed Approval Statuses."""
  needsReview = 1
  nA = 2
  reviewRequested = 3
  reviewStarted = 4
  needInfo = 5
  approved = 6
  notApproved = 7
  notSet = 8


class Approval(messages.Message):
  """Approval Value details"""
  approvalName = messages.StringField(1)
  approvers = messages.MessageField(AtomPerson, 2, repeated=True)
  status = messages.EnumField(ApprovalStatus, 3)
  setter = messages.MessageField(AtomPerson, 4)
  setOn = message_types.DateTimeField(5)
  phaseName = messages.StringField(6)


class IssueWrapper(messages.Message):
  """Issue details."""
  author = messages.MessageField(AtomPerson, 1)
  blockedOn = messages.MessageField(IssueRef, 2, repeated=True)
  blocking = messages.MessageField(IssueRef, 3, repeated=True)
  canComment = messages.BooleanField(4)
  canEdit = messages.BooleanField(5)
  cc = messages.MessageField(AtomPerson, 6, repeated=True)
  closed = message_types.DateTimeField(7)
  description = messages.StringField(8)
  id = messages.IntegerField(9, variant=messages.Variant.INT32)
  kind = messages.StringField(10)
  labels = messages.StringField(11, repeated=True)
  owner = messages.MessageField(AtomPerson, 12)
  published = message_types.DateTimeField(13)
  starred = messages.BooleanField(14)
  stars = messages.IntegerField(15, variant=messages.Variant.INT32)
  state = messages.EnumField(IssueState, 16)
  status = messages.StringField(17, required=True)
  summary = messages.StringField(18, required=True)
  title = messages.StringField(19)
  updated = message_types.DateTimeField(20)
  components = messages.StringField(21, repeated=True)
  projectId = messages.StringField(22, required=True)
  mergedInto = messages.MessageField(IssueRef, 23)
  fieldValues = messages.MessageField(FieldValue, 24, repeated=True)
  owner_modified = message_types.DateTimeField(25)
  status_modified = message_types.DateTimeField(26)
  component_modified = message_types.DateTimeField(27)
  approvalValues = messages.MessageField(Approval, 28, repeated=True)
  phases = messages.MessageField(Phase, 29, repeated=True)


class ProjectWrapper(messages.Message):
  """Project details."""
  kind = messages.StringField(1)
  name = messages.StringField(2)
  externalId = messages.StringField(3, required=True)
  htmlLink = messages.StringField(4, required=True)
  summary = messages.StringField(5)
  description = messages.StringField(6)
  versionControlSystem = messages.StringField(7)
  repositoryUrls = messages.StringField(8, repeated=True)
  issuesConfig = messages.MessageField(ProjectIssueConfig, 9)
  role = messages.EnumField(Role, 10)
  members = messages.MessageField(AtomPerson, 11, repeated=True)


class UserGroupSettingsWrapper(messages.Message):
  """User group settings."""
  groupName = messages.StringField(1, required=True)
  who_can_view_members = messages.EnumField(
      usergroup_pb2.MemberVisibility, 2,
      default=usergroup_pb2.MemberVisibility.MEMBERS)
  ext_group_type = messages.EnumField(usergroup_pb2.GroupType, 3)
  last_sync_time = messages.IntegerField(
      4, default=0, variant=messages.Variant.INT32)


class GroupCitizens(messages.Message):
  """Group members and owners."""
  groupOwners = messages.StringField(1, repeated=True)
  groupMembers = messages.StringField(2, repeated=True)


########################## Comments Message ##########################

# pylint: disable=pointless-string-statement

"""Request to delete/undelete an issue's comments."""
ISSUES_COMMENTS_DELETE_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    message_types.VoidMessage,
    projectId=messages.StringField(1, required=True),
    issueId=messages.IntegerField(
        2, required=True, variant=messages.Variant.INT32),
    commentId=messages.IntegerField(
        3, required=True, variant=messages.Variant.INT32)
)


class IssuesCommentsDeleteResponse(messages.Message):
  """Response message of request to delete/undelete an issue's comments."""
  error = messages.MessageField(ErrorMessage, 1)


"""Request to insert an issue's comments."""
ISSUES_COMMENTS_INSERT_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    IssueCommentWrapper,
    projectId=messages.StringField(1, required=True),
    issueId=messages.IntegerField(
        2, required=True, variant=messages.Variant.INT32),
    sendEmail=messages.BooleanField(3)
)


class IssuesCommentsInsertResponse(messages.Message):
  """Response message of request to insert an issue's comments."""
  error = messages.MessageField(ErrorMessage, 1)
  id = messages.IntegerField(2, variant=messages.Variant.INT32)
  kind = messages.StringField(3)
  author = messages.MessageField(AtomPerson, 4)
  content = messages.StringField(5)
  published = message_types.DateTimeField(6)
  updates = messages.MessageField(Update, 7)
  canDelete = messages.BooleanField(8)


"""Request to list an issue's comments."""
ISSUES_COMMENTS_LIST_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    message_types.VoidMessage,
    projectId=messages.StringField(1, required=True),
    issueId=messages.IntegerField(
        2, required=True, variant=messages.Variant.INT32),
    maxResults=messages.IntegerField(
        3, default=100, variant=messages.Variant.INT32),
    startIndex=messages.IntegerField(
        4, default=0, variant=messages.Variant.INT32)
)


class IssuesCommentsListResponse(messages.Message):
  """Response message of request to list an issue's comments."""
  error = messages.MessageField(ErrorMessage, 1)
  items = messages.MessageField(IssueCommentWrapper, 2, repeated=True)
  totalResults = messages.IntegerField(3, variant=messages.Variant.INT32)
  kind = messages.StringField(4)

########################## ApprovalComments Message ################

"""Request to insert an issue approval's comments."""
APPROVALS_COMMENTS_INSERT_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    ApprovalCommentWrapper,
    projectId=messages.StringField(1, required=True),
    issueId=messages.IntegerField(
        2, required=True, variant=messages.Variant.INT32),
    approvalName=messages.StringField(3, required=True),
    sendEmail=messages.BooleanField(4)
)


class ApprovalsCommentsInsertResponse(messages.Message):
  """Response message of request to insert an isuse's comments."""
  error = messages.MessageField(ErrorMessage, 1)
  id = messages.IntegerField(2, variant=messages.Variant.INT32)
  kind = messages.StringField(3)
  author = messages.MessageField(AtomPerson, 4)
  content = messages.StringField(5)
  published = message_types.DateTimeField(6)
  approvalUpdates = messages.MessageField(ApprovalUpdate, 7)
  canDelete = messages.BooleanField(8)
  approvalName = messages.StringField(9)

########################## Users Message ##########################

"""Request to get a user."""
USERS_GET_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    message_types.VoidMessage,
    userId=messages.StringField(1, required=True),
    ownerProjectsOnly=messages.BooleanField(2, default=False)
)


class UsersGetResponse(messages.Message):
  """Response message of request to get a user."""
  error = messages.MessageField(ErrorMessage, 1)
  id = messages.StringField(2)
  kind = messages.StringField(3)
  projects = messages.MessageField(ProjectWrapper, 4, repeated=True)


########################## Issues Message ##########################

"""Request to get an issue."""
ISSUES_GET_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    message_types.VoidMessage,
    projectId=messages.StringField(1, required=True),
    issueId=messages.IntegerField(
        2, required=True, variant=messages.Variant.INT32)
)


"""Request to insert an issue."""
ISSUES_INSERT_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    IssueWrapper,
    projectId=messages.StringField(1, required=True),
    sendEmail=messages.BooleanField(2, default=True)
)


class IssuesGetInsertResponse(messages.Message):
  """Response message of request to get/insert an issue."""
  error = messages.MessageField(ErrorMessage, 1)
  kind = messages.StringField(2)
  id = messages.IntegerField(3, variant=messages.Variant.INT32)
  title = messages.StringField(4)
  summary = messages.StringField(5)
  stars = messages.IntegerField(6, variant=messages.Variant.INT32)
  starred = messages.BooleanField(7)
  status = messages.StringField(8)
  state = messages.EnumField(IssueState, 9)
  labels = messages.StringField(10, repeated=True)
  author = messages.MessageField(AtomPerson, 11)
  owner = messages.MessageField(AtomPerson, 12)
  cc = messages.MessageField(AtomPerson, 13, repeated=True)
  updated = message_types.DateTimeField(14)
  published = message_types.DateTimeField(15)
  closed = message_types.DateTimeField(16)
  blockedOn = messages.MessageField(IssueRef, 17, repeated=True)
  blocking = messages.MessageField(IssueRef, 18, repeated=True)
  projectId = messages.StringField(19)
  canComment = messages.BooleanField(20)
  canEdit = messages.BooleanField(21)
  components = messages.StringField(22, repeated=True)
  mergedInto = messages.MessageField(IssueRef, 23)
  fieldValues = messages.MessageField(FieldValue, 24, repeated=True)
  owner_modified = message_types.DateTimeField(25)
  status_modified = message_types.DateTimeField(26)
  component_modified = message_types.DateTimeField(27)
  approvalValues = messages.MessageField(Approval, 28, repeated=True)
  phases = messages.MessageField(Phase, 29, repeated=True)


"""Request to list issues."""
ISSUES_LIST_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    message_types.VoidMessage,
    projectId=messages.StringField(1, required=True),
    additionalProject=messages.StringField(2, repeated=True),
    can=messages.EnumField(CannedQuery, 3, default='all'),
    label=messages.StringField(4),
    maxResults=messages.IntegerField(
        5, default=100, variant=messages.Variant.INT32),
    owner=messages.StringField(6),
    publishedMax=messages.IntegerField(7, variant=messages.Variant.INT64),
    publishedMin=messages.IntegerField(8, variant=messages.Variant.INT64),
    q=messages.StringField(9),
    sort=messages.StringField(10),
    startIndex=messages.IntegerField(
        11, default=0, variant=messages.Variant.INT32),
    status=messages.StringField(12),
    updatedMax=messages.IntegerField(13, variant=messages.Variant.INT64),
    updatedMin=messages.IntegerField(14, variant=messages.Variant.INT64)
)


class IssuesListResponse(messages.Message):
  """Response message of request to list issues."""
  error = messages.MessageField(ErrorMessage, 1)
  items = messages.MessageField(IssueWrapper, 2, repeated=True)
  totalResults = messages.IntegerField(3, variant=messages.Variant.INT32)
  kind = messages.StringField(4)


"""Request to list group settings."""
GROUPS_SETTINGS_LIST_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    message_types.VoidMessage,
    importedGroupsOnly=messages.BooleanField(1, default=False)
)


class GroupsSettingsListResponse(messages.Message):
  """Response message of request to list group settings."""
  error = messages.MessageField(ErrorMessage, 1)
  groupSettings = messages.MessageField(
      UserGroupSettingsWrapper, 2, repeated=True)


"""Request to create a group."""
GROUPS_CREATE_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    message_types.VoidMessage,
    groupName = messages.StringField(1, required=True),
    who_can_view_members = messages.EnumField(
        usergroup_pb2.MemberVisibility, 2,
        default=usergroup_pb2.MemberVisibility.MEMBERS, required=True),
    ext_group_type = messages.EnumField(usergroup_pb2.GroupType, 3)
)


class GroupsCreateResponse(messages.Message):
  """Response message of request to create a group."""
  error = messages.MessageField(ErrorMessage, 1)
  groupID = messages.IntegerField(
      2, variant=messages.Variant.INT32)


"""Request to get a group."""
GROUPS_GET_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    message_types.VoidMessage,
    groupName = messages.StringField(1, required=True)
)


class GroupsGetResponse(messages.Message):
  """Response message of request to create a group."""
  error = messages.MessageField(ErrorMessage, 1)
  groupID = messages.IntegerField(
      2, variant=messages.Variant.INT32)
  groupSettings = messages.MessageField(
      UserGroupSettingsWrapper, 3)
  groupOwners = messages.StringField(4, repeated=True)
  groupMembers = messages.StringField(5, repeated=True)


"""Request to update a group."""
GROUPS_UPDATE_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    GroupCitizens,
    groupName = messages.StringField(1, required=True),
    who_can_view_members = messages.EnumField(
        usergroup_pb2.MemberVisibility, 2),
    ext_group_type = messages.EnumField(usergroup_pb2.GroupType, 3),
    last_sync_time = messages.IntegerField(
        4, default=0, variant=messages.Variant.INT32),
    friend_projects = messages.StringField(5, repeated=True),
)


class GroupsUpdateResponse(messages.Message):
  """Response message of request to update a group."""
  error = messages.MessageField(ErrorMessage, 1)


########################## Component Message ##########################

class Component(messages.Message):
  """Component PB."""
  componentId = messages.IntegerField(
      1, required=True, variant=messages.Variant.INT32)
  projectName = messages.StringField(2, required=True)
  componentPath = messages.StringField(3, required=True)
  description = messages.StringField(4)
  admin = messages.StringField(5, repeated=True)
  cc = messages.StringField(6, repeated=True)
  deprecated = messages.BooleanField(7, default=False)
  created = message_types.DateTimeField(8)
  creator = messages.StringField(9)
  modified = message_types.DateTimeField(10)
  modifier = messages.StringField(11)


"""Request to get components of a project."""
COMPONENTS_LIST_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    message_types.VoidMessage,
    projectId=messages.StringField(1, required=True),
)


class ComponentsListResponse(messages.Message):
  """Response to list components."""
  components = messages.MessageField(
      Component, 1, repeated=True)


class ComponentCreateRequestBody(messages.Message):
  """Request body to create a component."""
  parentPath = messages.StringField(1)
  description = messages.StringField(2)
  admin = messages.StringField(3, repeated=True)
  cc = messages.StringField(4, repeated=True)
  deprecated = messages.BooleanField(5, default=False)


"""Request to create component of a project."""
COMPONENTS_CREATE_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    ComponentCreateRequestBody,
    projectId=messages.StringField(1, required=True),
    componentName=messages.StringField(2, required=True),
)


"""Request to delete a component."""
COMPONENTS_DELETE_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    message_types.VoidMessage,
    projectId=messages.StringField(1, required=True),
    componentPath=messages.StringField(2, required=True),
)


class ComponentUpdateFieldID(messages.Enum):
  """Possible fields that can be updated in a component."""
  LEAF_NAME = 1
  DESCRIPTION = 2
  ADMIN = 3
  CC = 4
  DEPRECATED = 5


class ComponentUpdate(messages.Message):
  """Component update."""
  # 'field' allows a field to be cleared
  field = messages.EnumField(ComponentUpdateFieldID, 1, required=True)
  leafName = messages.StringField(2)
  description = messages.StringField(3)
  admin = messages.StringField(4, repeated=True)
  cc = messages.StringField(5, repeated=True)
  deprecated = messages.BooleanField(6)


class ComponentUpdateRequestBody(messages.Message):
  """Request body to update a component."""
  updates = messages.MessageField(ComponentUpdate, 1, repeated=True)


"""Request to update a component."""
COMPONENTS_UPDATE_REQUEST_RESOURCE_CONTAINER = ResourceContainer(
    ComponentUpdateRequestBody,
    projectId=messages.StringField(1, required=True),
    componentPath=messages.StringField(2, required=True),
)
