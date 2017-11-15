# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Classes and functions for persistence of issue tracker configuration.

This module provides functions to get, update, create, and (in some
cases) delete each type of business object.  It provides a logical
persistence layer on top of an SQL database.

Business objects are described in tracker_pb2.py and tracker_bizobj.py.
"""

import collections
import logging

from google.appengine.api import memcache

import settings
from framework import exceptions
from framework import sql
from proto import tracker_pb2
from services import caches
from services import project_svc
from tracker import tracker_bizobj
from tracker import tracker_constants


TEMPLATE_TABLE_NAME = 'Template'
TEMPLATE2LABEL_TABLE_NAME = 'Template2Label'
TEMPLATE2ADMIN_TABLE_NAME = 'Template2Admin'
TEMPLATE2COMPONENT_TABLE_NAME = 'Template2Component'
TEMPLATE2FIELDVALUE_TABLE_NAME = 'Template2FieldValue'
PROJECTISSUECONFIG_TABLE_NAME = 'ProjectIssueConfig'
LABELDEF_TABLE_NAME = 'LabelDef'
FIELDDEF_TABLE_NAME = 'FieldDef'
FIELDDEF2ADMIN_TABLE_NAME = 'FieldDef2Admin'
COMPONENTDEF_TABLE_NAME = 'ComponentDef'
COMPONENT2ADMIN_TABLE_NAME = 'Component2Admin'
COMPONENT2CC_TABLE_NAME = 'Component2Cc'
COMPONENT2LABEL_TABLE_NAME = 'Component2Label'
STATUSDEF_TABLE_NAME = 'StatusDef'

TEMPLATE_COLS = [
    'id', 'project_id', 'name', 'content', 'summary', 'summary_must_be_edited',
    'owner_id', 'status', 'members_only', 'owner_defaults_to_member',
    'component_required']
TEMPLATE2LABEL_COLS = ['template_id', 'label']
TEMPLATE2COMPONENT_COLS = ['template_id', 'component_id']
TEMPLATE2ADMIN_COLS = ['template_id', 'admin_id']
TEMPLATE2FIELDVALUE_COLS = [
    'template_id', 'field_id', 'int_value', 'str_value', 'date_value',
    'user_id']
PROJECTISSUECONFIG_COLS = [
    'project_id', 'statuses_offer_merge', 'exclusive_label_prefixes',
    'default_template_for_developers', 'default_template_for_users',
    'default_col_spec', 'default_sort_spec', 'default_x_attr',
    'default_y_attr', 'member_default_query', 'custom_issue_entry_url']
STATUSDEF_COLS = [
    'id', 'project_id', 'rank', 'status', 'means_open', 'docstring',
    'deprecated']
LABELDEF_COLS = [
    'id', 'project_id', 'rank', 'label', 'docstring', 'deprecated']
FIELDDEF_COLS = [
    'id', 'project_id', 'rank', 'field_name', 'field_type', 'applicable_type',
    'applicable_predicate', 'is_required', 'is_niche', 'is_multivalued',
    'min_value', 'max_value', 'regex', 'needs_member', 'needs_perm',
    'grants_perm', 'notify_on', 'date_action', 'docstring', 'is_deleted']
FIELDDEF2ADMIN_COLS = ['field_id', 'admin_id']
COMPONENTDEF_COLS = ['id', 'project_id', 'path', 'docstring', 'deprecated',
                     'created', 'creator_id', 'modified', 'modifier_id']
COMPONENT2ADMIN_COLS = ['component_id', 'admin_id']
COMPONENT2CC_COLS = ['component_id', 'cc_id']
COMPONENT2LABEL_COLS = ['component_id', 'label_id']

NOTIFY_ON_ENUM = ['never', 'any_comment']
DATE_ACTION_ENUM = ['no_action', 'ping_owner_only', 'ping_participants']

# Some projects have tons of label rows, so we retrieve them in shards
# to avoid huge DB results or exceeding the memcache size limit.
LABEL_ROW_SHARDS = 10


class LabelRowTwoLevelCache(caches.AbstractTwoLevelCache):
  """Class to manage RAM and memcache for label rows.

  Label rows exist for every label used in a project, even those labels
  that were added to issues in an ad hoc way without being defined in the
  config ahead of time.

  The set of all labels in a project can be very large, so we shard them
  into 10 parts so that each part can be cached in memcache with < 1MB.
  """

  def __init__(self, cache_manager, config_service):
    super(LabelRowTwoLevelCache, self).__init__(
        cache_manager, 'project', 'label_rows:', None)
    self.config_service = config_service

  def _MakeCache(self, cache_manager, kind, max_size=None):
    """Make the RAM cache and registier it with the cache_manager."""
    return caches.ShardedRamCache(
      cache_manager, kind, max_size=max_size, num_shards=LABEL_ROW_SHARDS)

  def _DeserializeLabelRows(self, label_def_rows):
    """Convert DB result rows into a dict {project_id: [row, ...]}."""
    result_dict = collections.defaultdict(list)
    for label_id, project_id, rank, label, docstr, deprecated in label_def_rows:
      shard_id = label_id % LABEL_ROW_SHARDS
      result_dict[(project_id, shard_id)].append(
          (label_id, project_id, rank, label, docstr, deprecated))

    return result_dict

  def FetchItems(self, cnxn, keys):
    """On RAM and memcache miss, hit the database."""
    # Make sure that every requested project is represented in the result
    label_rows_dict = {}
    for key in keys:
      label_rows_dict.setdefault(key, [])

    for project_id, shard_id in keys:
      shard_clause = [('id %% %s = %s', [LABEL_ROW_SHARDS, shard_id])]

      label_def_rows = self.config_service.labeldef_tbl.Select(
          cnxn, cols=LABELDEF_COLS, project_id=project_id,
          where=shard_clause)
      label_rows_dict.update(self._DeserializeLabelRows(label_def_rows))

    for rows_in_shard in label_rows_dict.values():
      rows_in_shard.sort(key=lambda row: (row[2], row[3]), reverse=True)

    return label_rows_dict

  def InvalidateKeys(self, cnxn, project_ids):
    """Drop the given keys from both RAM and memcache."""
    self.cache.InvalidateKeys(cnxn, project_ids)
    memcache.delete_multi(
        [self._KeyToStr((project_id, shard_id))
         for project_id in project_ids
         for shard_id in range(0, LABEL_ROW_SHARDS)], seconds=5,
        key_prefix=self.memcache_prefix)

  def InvalidateAllKeys(self, cnxn, project_ids):
    """Drop the given keys from memcache and invalidate all keys in RAM.

    Useful for avoiding inserting many rows into the Invalidate table when
    invalidating a large group of keys all at once. Only use when necessary.
    """
    self.cache.InvalidateAll(cnxn)
    memcache.delete_multi(
        [self._KeyToStr((project_id, shard_id))
         for project_id in project_ids
         for shard_id in range(0, LABEL_ROW_SHARDS)], seconds=5,
        key_prefix=self.memcache_prefix)

  def _KeyToStr(self, key):
    """Convert our tuple IDs to strings for use as memcache keys."""
    project_id, shard_id = key
    return '%d-%d' % (project_id, shard_id)

  def _StrToKey(self, key_str):
    """Convert memcache keys back to the tuples that we use as IDs."""
    project_id_str, shard_id_str = key_str.split('-')
    return int(project_id_str), int(shard_id_str)


class StatusRowTwoLevelCache(caches.AbstractTwoLevelCache):
  """Class to manage RAM and memcache for status rows."""

  def __init__(self, cache_manager, config_service):
    super(StatusRowTwoLevelCache, self).__init__(
        cache_manager, 'project', 'status_rows:', None)
    self.config_service = config_service

  def _DeserializeStatusRows(self, def_rows):
    """Convert status definition rows into {project_id: [row, ...]}."""
    result_dict = collections.defaultdict(list)
    for (status_id, project_id, rank, status,
         means_open, docstr, deprecated) in def_rows:
      result_dict[project_id].append(
          (status_id, project_id, rank, status, means_open, docstr, deprecated))

    return result_dict

  def FetchItems(self, cnxn, keys):
    """On cache miss, get status definition rows from the DB."""
    status_def_rows = self.config_service.statusdef_tbl.Select(
        cnxn, cols=STATUSDEF_COLS, project_id=keys,
        order_by=[('rank DESC', []), ('status DESC', [])])
    status_rows_dict = self._DeserializeStatusRows(status_def_rows)

    # Make sure that every requested project is represented in the result
    for project_id in keys:
      status_rows_dict.setdefault(project_id, [])

    return status_rows_dict


class FieldRowTwoLevelCache(caches.AbstractTwoLevelCache):
  """Class to manage RAM and memcache for field rows.

  Field rows exist for every field used in a project, since they cannot be
  created through ad-hoc means.
  """

  def __init__(self, cache_manager, config_service):
    super(FieldRowTwoLevelCache, self).__init__(
        cache_manager, 'project', 'field_rows:', None)
    self.config_service = config_service

  def _DeserializeFieldRows(self, field_def_rows):
    """Convert DB result rows into a dict {project_id: [row, ...]}."""
    result_dict = collections.defaultdict(list)
    # TODO(agable): Actually process the rest of the items.
    for (field_id, project_id, rank, field_name, _field_type, _applicable_type,
         _applicable_predicate, _is_required, _is_niche, _is_multivalued,
         _min_value, _max_value, _regex, _needs_member, _needs_perm,
         _grants_perm, _notify_on, _date_action, docstring,
         _is_deleted) in field_def_rows:
      result_dict[project_id].append(
          (field_id, project_id, rank, field_name, docstring))

    return result_dict

  def FetchItems(self, cnxn, keys):
    """On RAM and memcache miss, hit the database."""
    field_def_rows = self.config_service.fielddef_tbl.Select(
        cnxn, cols=FIELDDEF_COLS, project_id=keys,
        order_by=[('rank DESC', []), ('field_name DESC', [])])
    field_rows_dict = self._DeserializeFieldRows(field_def_rows)

    # Make sure that every requested project is represented in the result
    for project_id in keys:
      field_rows_dict.setdefault(project_id, [])

    return field_rows_dict


class ConfigTwoLevelCache(caches.AbstractTwoLevelCache):
  """Class to manage RAM and memcache for IssueProjectConfig PBs."""

  def __init__(self, cache_manager, config_service):
    super(ConfigTwoLevelCache, self).__init__(
        cache_manager, 'project', 'config:', tracker_pb2.ProjectIssueConfig)
    self.config_service = config_service

  def _UnpackProjectIssueConfig(self, config_row):
    """Partially construct a config object using info from a DB row."""
    (project_id, statuses_offer_merge, exclusive_label_prefixes,
     default_template_for_developers, default_template_for_users,
     default_col_spec, default_sort_spec, default_x_attr, default_y_attr,
     member_default_query, custom_issue_entry_url) = config_row
    config = tracker_pb2.ProjectIssueConfig()
    config.project_id = project_id
    config.statuses_offer_merge.extend(statuses_offer_merge.split())
    config.exclusive_label_prefixes.extend(exclusive_label_prefixes.split())
    config.default_template_for_developers = default_template_for_developers
    config.default_template_for_users = default_template_for_users
    config.default_col_spec = default_col_spec
    config.default_sort_spec = default_sort_spec
    config.default_x_attr = default_x_attr
    config.default_y_attr = default_y_attr
    config.member_default_query = member_default_query
    if custom_issue_entry_url is not None:
      config.custom_issue_entry_url = custom_issue_entry_url

    return config

  def _UnpackTemplate(self, template_row):
    """Partially construct a template object using info from a DB row."""
    (template_id, project_id, name, content, summary,
     summary_must_be_edited, owner_id, status,
     members_only, owner_defaults_to_member, component_required) = template_row
    template = tracker_pb2.TemplateDef()
    template.template_id = template_id
    template.name = name
    template.content = content
    template.summary = summary
    template.summary_must_be_edited = bool(
        summary_must_be_edited)
    template.owner_id = owner_id or 0
    template.status = status
    template.members_only = bool(members_only)
    template.owner_defaults_to_member = bool(owner_defaults_to_member)
    template.component_required = bool(component_required)

    return template, project_id

  def _UnpackFieldDef(self, fielddef_row):
    """Partially construct a FieldDef object using info from a DB row."""
    (field_id, project_id, _rank, field_name, field_type,
     applic_type, applic_pred, is_required, is_niche, is_multivalued,
     min_value, max_value, regex, needs_member, needs_perm,
     grants_perm, notify_on_str, date_action_str, docstring,
     is_deleted) = fielddef_row
    if notify_on_str == 'any_comment':
      notify_on = tracker_pb2.NotifyTriggers.ANY_COMMENT
    else:
      notify_on = tracker_pb2.NotifyTriggers.NEVER
    try:
      date_action = DATE_ACTION_ENUM.index(date_action_str)
    except ValueError:
      date_action = DATE_ACTION_ENUM.index('no_action')

    return tracker_bizobj.MakeFieldDef(
        field_id, project_id, field_name,
        tracker_pb2.FieldTypes(field_type.upper()), applic_type, applic_pred,
        is_required, is_niche, is_multivalued, min_value, max_value, regex,
        needs_member, needs_perm, grants_perm, notify_on, date_action,
        docstring, is_deleted)

  def _UnpackComponentDef(
      self, cd_row, component2admin_rows, component2cc_rows,
      component2label_rows):
    """Partially construct a FieldDef object using info from a DB row."""
    (component_id, project_id, path, docstring, deprecated, created,
     creator_id, modified, modifier_id) = cd_row
    cd = tracker_bizobj.MakeComponentDef(
        component_id, project_id, path, docstring, deprecated,
        [admin_id for comp_id, admin_id in component2admin_rows
         if comp_id == component_id],
        [cc_id for comp_id, cc_id in component2cc_rows
         if comp_id == component_id],
        created, creator_id, 
        modified=modified, modifier_id=modifier_id,
        label_ids=[label_id for comp_id, label_id in component2label_rows
                   if comp_id == component_id])

    return cd

  def _DeserializeIssueConfigs(
      self, config_rows, template_rows, template2label_rows,
      template2component_rows, template2admin_rows, template2fieldvalue_rows,
      statusdef_rows, labeldef_rows, fielddef_rows, fielddef2admin_rows,
      componentdef_rows, component2admin_rows, component2cc_rows,
      component2label_rows):
    """Convert the given row tuples into a dict of ProjectIssueConfig PBs."""
    result_dict = {}
    template_dict = {}
    fielddef_dict = {}

    for config_row in config_rows:
      config = self._UnpackProjectIssueConfig(config_row)
      result_dict[config.project_id] = config

    for template_row in template_rows:
      template, project_id = self._UnpackTemplate(template_row)
      if project_id in result_dict:
        result_dict[project_id].templates.append(template)
        template_dict[template.template_id] = template

    for template2label_row in template2label_rows:
      template_id, label = template2label_row
      template = template_dict.get(template_id)
      if template:
        template.labels.append(label)

    for template2component_row in template2component_rows:
      template_id, component_id = template2component_row
      template = template_dict.get(template_id)
      if template:
        template.component_ids.append(component_id)

    for template2admin_row in template2admin_rows:
      template_id, admin_id = template2admin_row
      template = template_dict.get(template_id)
      if template:
        template.admin_ids.append(admin_id)

    for fv_row in template2fieldvalue_rows:
      (template_id, field_id, int_value, str_value, user_id,
       date_value, url_value) = fv_row
      fv = tracker_bizobj.MakeFieldValue(
          field_id, int_value, str_value, user_id, date_value, url_value, False)
      template = template_dict.get(template_id)
      if template:
        template.field_values.append(fv)

    for statusdef_row in statusdef_rows:
      (_, project_id, _rank, status,
       means_open, docstring, deprecated) = statusdef_row
      if project_id in result_dict:
        wks = tracker_pb2.StatusDef(
            status=status, means_open=bool(means_open),
            status_docstring=docstring or '', deprecated=bool(deprecated))
        result_dict[project_id].well_known_statuses.append(wks)

    for labeldef_row in labeldef_rows:
      _, project_id, _rank, label, docstring, deprecated = labeldef_row
      if project_id in result_dict:
        wkl = tracker_pb2.LabelDef(
            label=label, label_docstring=docstring or '',
            deprecated=bool(deprecated))
        result_dict[project_id].well_known_labels.append(wkl)

    for fd_row in fielddef_rows:
      fd = self._UnpackFieldDef(fd_row)
      result_dict[fd.project_id].field_defs.append(fd)
      fielddef_dict[fd.field_id] = fd

    for fd2admin_row in fielddef2admin_rows:
      field_id, admin_id = fd2admin_row
      fd = fielddef_dict.get(field_id)
      if fd:
        fd.admin_ids.append(admin_id)

    for cd_row in componentdef_rows:
      cd = self._UnpackComponentDef(
          cd_row, component2admin_rows, component2cc_rows, component2label_rows)
      result_dict[cd.project_id].component_defs.append(cd)

    return result_dict

  def _FetchConfigs(self, cnxn, project_ids):
    """On RAM and memcache miss, hit the database."""
    config_rows = self.config_service.projectissueconfig_tbl.Select(
        cnxn, cols=PROJECTISSUECONFIG_COLS, project_id=project_ids)
    template_rows = self.config_service.template_tbl.Select(
        cnxn, cols=TEMPLATE_COLS, project_id=project_ids,
        order_by=[('name', [])])
    template_ids = [row[0] for row in template_rows]
    template2label_rows = self.config_service.template2label_tbl.Select(
        cnxn, cols=TEMPLATE2LABEL_COLS, template_id=template_ids)
    template2component_rows = self.config_service.template2component_tbl.Select(
        cnxn, cols=TEMPLATE2COMPONENT_COLS, template_id=template_ids)
    template2admin_rows = self.config_service.template2admin_tbl.Select(
        cnxn, cols=TEMPLATE2ADMIN_COLS, template_id=template_ids)
    template2fv_rows = self.config_service.template2fieldvalue_tbl.Select(
        cnxn, cols=TEMPLATE2FIELDVALUE_COLS, template_id=template_ids)
    logging.info('t2fv is %r', template2fv_rows)
    statusdef_rows = self.config_service.statusdef_tbl.Select(
        cnxn, cols=STATUSDEF_COLS, project_id=project_ids,
        where=[('rank IS NOT NULL', [])], order_by=[('rank', [])])
    labeldef_rows = self.config_service.labeldef_tbl.Select(
        cnxn, cols=LABELDEF_COLS, project_id=project_ids,
        where=[('rank IS NOT NULL', [])], order_by=[('rank', [])])
    # TODO(jrobbins): For now, sort by field name, but someday allow admins
    # to adjust the rank to group and order field definitions logically.
    fielddef_rows = self.config_service.fielddef_tbl.Select(
        cnxn, cols=FIELDDEF_COLS, project_id=project_ids,
        order_by=[('field_name', [])])
    field_ids = [row[0] for row in fielddef_rows]
    fielddef2admin_rows = self.config_service.fielddef2admin_tbl.Select(
        cnxn, cols=FIELDDEF2ADMIN_COLS, field_id=field_ids)
    componentdef_rows = self.config_service.componentdef_tbl.Select(
        cnxn, cols=COMPONENTDEF_COLS, project_id=project_ids,
        order_by=[('LOWER(path)', [])])
    component_ids = [cd_row[0] for cd_row in componentdef_rows]
    component2admin_rows = self.config_service.component2admin_tbl.Select(
        cnxn, cols=COMPONENT2ADMIN_COLS, component_id=component_ids)
    component2cc_rows = self.config_service.component2cc_tbl.Select(
        cnxn, cols=COMPONENT2CC_COLS, component_id=component_ids)
    component2label_rows = self.config_service.component2label_tbl.Select(
        cnxn, cols=COMPONENT2LABEL_COLS, component_id=component_ids)

    retrieved_dict = self._DeserializeIssueConfigs(
        config_rows, template_rows, template2label_rows,
        template2component_rows, template2admin_rows,
        template2fv_rows, statusdef_rows, labeldef_rows,
        fielddef_rows, fielddef2admin_rows, componentdef_rows,
        component2admin_rows, component2cc_rows, component2label_rows)
    return retrieved_dict

  def FetchItems(self, cnxn, keys):
    """On RAM and memcache miss, hit the database."""
    retrieved_dict = self._FetchConfigs(cnxn, keys)

    # Any projects which don't have stored configs should use a default
    # config instead.
    for project_id in keys:
      if project_id not in retrieved_dict:
        config = tracker_bizobj.MakeDefaultProjectIssueConfig(project_id)
        retrieved_dict[project_id] = config

    return retrieved_dict


class ConfigService(object):
  """The persistence layer for Monorail's issue tracker configuration data."""

  def __init__(self, cache_manager):
    """Initialize this object so that it is ready to use.

    Args:
      cache_manager: manages local caches with distributed invalidation.
    """
    self.template_tbl = sql.SQLTableManager(TEMPLATE_TABLE_NAME)
    self.template2label_tbl = sql.SQLTableManager(TEMPLATE2LABEL_TABLE_NAME)
    self.template2component_tbl = sql.SQLTableManager(
        TEMPLATE2COMPONENT_TABLE_NAME)
    self.template2admin_tbl = sql.SQLTableManager(TEMPLATE2ADMIN_TABLE_NAME)
    self.template2fieldvalue_tbl = sql.SQLTableManager(
        TEMPLATE2FIELDVALUE_TABLE_NAME)
    self.projectissueconfig_tbl = sql.SQLTableManager(
        PROJECTISSUECONFIG_TABLE_NAME)
    self.statusdef_tbl = sql.SQLTableManager(STATUSDEF_TABLE_NAME)
    self.labeldef_tbl = sql.SQLTableManager(LABELDEF_TABLE_NAME)
    self.fielddef_tbl = sql.SQLTableManager(FIELDDEF_TABLE_NAME)
    self.fielddef2admin_tbl = sql.SQLTableManager(FIELDDEF2ADMIN_TABLE_NAME)
    self.componentdef_tbl = sql.SQLTableManager(COMPONENTDEF_TABLE_NAME)
    self.component2admin_tbl = sql.SQLTableManager(COMPONENT2ADMIN_TABLE_NAME)
    self.component2cc_tbl = sql.SQLTableManager(COMPONENT2CC_TABLE_NAME)
    self.component2label_tbl = sql.SQLTableManager(COMPONENT2LABEL_TABLE_NAME)

    self.config_2lc = ConfigTwoLevelCache(cache_manager, self)
    self.label_row_2lc = LabelRowTwoLevelCache(cache_manager, self)
    self.label_cache = caches.RamCache(cache_manager, 'project')
    self.status_row_2lc = StatusRowTwoLevelCache(cache_manager, self)
    self.status_cache = caches.RamCache(cache_manager, 'project')
    self.field_row_2lc = FieldRowTwoLevelCache(cache_manager, self)
    self.field_cache = caches.RamCache(cache_manager, 'project')

  ### Label lookups

  def GetLabelDefRows(self, cnxn, project_id, use_cache=True):
    """Get SQL result rows for all labels used in the specified project."""
    result = []
    for shard_id in range(0, LABEL_ROW_SHARDS):
      key = (project_id, shard_id)
      pids_to_label_rows_shard, _misses = self.label_row_2lc.GetAll(
        cnxn, [key], use_cache=use_cache)
      result.extend(pids_to_label_rows_shard[key])
    # Sort in python to reduce DB load and integrate results from shards.
    # row[2] is rank, row[3] is label name.
    result.sort(key=lambda row: (row[2], row[3]), reverse=True)
    return result

  def GetLabelDefRowsAnyProject(self, cnxn, where=None):
    """Get all LabelDef rows for the whole site. Used in whole-site search."""
    # TODO(jrobbins): maybe add caching for these too.
    label_def_rows = self.labeldef_tbl.Select(
        cnxn, cols=LABELDEF_COLS, where=where,
        order_by=[('rank DESC', []), ('label DESC', [])])
    return label_def_rows

  def _DeserializeLabels(self, def_rows):
    """Convert label defs into bi-directional mappings of names and IDs."""
    label_id_to_name = {
        label_id: label for
        label_id, _pid, _rank, label, _doc, _deprecated
        in def_rows}
    label_name_to_id = {
        label.lower(): label_id
        for label_id, label in label_id_to_name.iteritems()}

    return label_id_to_name, label_name_to_id

  def _EnsureLabelCacheEntry(self, cnxn, project_id, use_cache=True):
    """Make sure that self.label_cache has an entry for project_id."""
    if not use_cache or not self.label_cache.HasItem(project_id):
      def_rows = self.GetLabelDefRows(cnxn, project_id, use_cache=use_cache)
      self.label_cache.CacheItem(project_id, self._DeserializeLabels(def_rows))

  def LookupLabel(self, cnxn, project_id, label_id):
    """Lookup a label string given the label_id.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project where the label is defined or used.
      label_id: int label ID.

    Returns:
      Label name string for the given label_id, or None.
    """
    self._EnsureLabelCacheEntry(cnxn, project_id)
    label_id_to_name, _label_name_to_id = self.label_cache.GetItem(
        project_id)
    if label_id in label_id_to_name:
      return label_id_to_name[label_id]

    logging.info('Label %r not found. Getting fresh from DB.', label_id)
    self._EnsureLabelCacheEntry(cnxn, project_id, use_cache=False)
    label_id_to_name, _label_name_to_id = self.label_cache.GetItem(
        project_id)
    return label_id_to_name.get(label_id)

  def LookupLabelID(self, cnxn, project_id, label, autocreate=True):
    """Look up a label ID, optionally interning it.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project where the statuses are defined.
      label: label string.
      autocreate: if not already in the DB, store it and generate a new ID.

    Returns:
      The label ID for the given label string.
    """
    self._EnsureLabelCacheEntry(cnxn, project_id)
    _label_id_to_name, label_name_to_id = self.label_cache.GetItem(
        project_id)
    if label.lower() in label_name_to_id:
      return label_name_to_id[label.lower()]

    # Double check that the label does not already exist in the DB.
    rows = self.labeldef_tbl.Select(
        cnxn, cols=['id'], project_id=project_id,
        where=[('LOWER(label) = %s', [label.lower()])],
        limit=1)
    logging.info('Double checking for %r gave %r', label, rows)
    if rows:
      self.label_row_2lc.cache.LocalInvalidate(project_id)
      self.label_cache.LocalInvalidate(project_id)
      return rows[0][0]

    if autocreate:
      logging.info('No label %r is known in project %d, so intern it.',
                   label, project_id)
      label_id = self.labeldef_tbl.InsertRow(
          cnxn, project_id=project_id, label=label)
      self.label_row_2lc.InvalidateKeys(cnxn, [project_id])
      self.label_cache.Invalidate(cnxn, project_id)
      return label_id

    return None  # It was not found and we don't want to create it.

  def LookupLabelIDs(self, cnxn, project_id, labels, autocreate=False):
    """Look up several label IDs.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project where the statuses are defined.
      labels: list of label strings.
      autocreate: if not already in the DB, store it and generate a new ID.

    Returns:
      Returns a list of int label IDs for the given label strings.
    """
    result = []
    for lab in labels:
      label_id = self.LookupLabelID(
          cnxn, project_id, lab, autocreate=autocreate)
      if label_id is not None:
        result.append(label_id)

    return result

  def LookupIDsOfLabelsMatching(self, cnxn, project_id, regex):
    """Look up the IDs of all labels in a project that match the regex.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project where the statuses are defined.
      regex: regular expression object to match against the label strings.

    Returns:
      List of label IDs for labels that match the regex.
    """
    self._EnsureLabelCacheEntry(cnxn, project_id)
    label_id_to_name, _label_name_to_id = self.label_cache.GetItem(
        project_id)
    result = [label_id for label_id, label in label_id_to_name.iteritems()
              if regex.match(label)]

    return result

  def LookupLabelIDsAnyProject(self, cnxn, label):
    """Return the IDs of labels with the given name in any project.

    Args:
      cnxn: connection to SQL database.
      label: string label to look up.  Case sensitive.

    Returns:
      A list of int label IDs of all labels matching the given string.
    """
    # TODO(jrobbins): maybe add caching for these too.
    label_id_rows = self.labeldef_tbl.Select(
        cnxn, cols=['id'], label=label)
    label_ids = [row[0] for row in label_id_rows]
    return label_ids

  def LookupIDsOfLabelsMatchingAnyProject(self, cnxn, regex):
    """Return the IDs of matching labels in any project."""
    label_rows = self.labeldef_tbl.Select(
        cnxn, cols=['id', 'label'])
    matching_ids = [
        label_id for label_id, label in label_rows if regex.match(label)]
    return matching_ids

  ### Status lookups

  def GetStatusDefRows(self, cnxn, project_id):
    """Return a list of status definition rows for the specified project."""
    pids_to_status_rows, misses = self.status_row_2lc.GetAll(
        cnxn, [project_id])
    assert not misses
    return pids_to_status_rows[project_id]

  def GetStatusDefRowsAnyProject(self, cnxn):
    """Return all status definition rows on the whole site."""
    # TODO(jrobbins): maybe add caching for these too.
    status_def_rows = self.statusdef_tbl.Select(
        cnxn, cols=STATUSDEF_COLS,
        order_by=[('rank DESC', []), ('status DESC', [])])
    return status_def_rows

  def _DeserializeStatuses(self, def_rows):
    """Convert status defs into bi-directional mappings of names and IDs."""
    status_id_to_name = {
        status_id: status
        for (status_id, _pid, _rank, status, _means_open,
             _doc, _deprecated) in def_rows}
    status_name_to_id = {
        status.lower(): status_id
        for status_id, status in status_id_to_name.iteritems()}
    closed_status_ids = [
        status_id
        for (status_id, _pid, _rank, _status, means_open,
             _doc, _deprecated) in def_rows
        if means_open == 0]  # Only 0 means closed. NULL/None means open.

    return status_id_to_name, status_name_to_id, closed_status_ids

  def _EnsureStatusCacheEntry(self, cnxn, project_id):
    """Make sure that self.status_cache has an entry for project_id."""
    if not self.status_cache.HasItem(project_id):
      def_rows = self.GetStatusDefRows(cnxn, project_id)
      self.status_cache.CacheItem(
          project_id, self._DeserializeStatuses(def_rows))

  def LookupStatus(self, cnxn, project_id, status_id):
    """Look up a status string for the given status ID.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project where the statuses are defined.
      status_id: int ID of the status value.

    Returns:
      A status string, or None.
    """
    if status_id == 0:
      return ''

    self._EnsureStatusCacheEntry(cnxn, project_id)
    (status_id_to_name, _status_name_to_id,
     _closed_status_ids) = self.status_cache.GetItem(project_id)

    return status_id_to_name.get(status_id)

  def LookupStatusID(self, cnxn, project_id, status, autocreate=True):
    """Look up a status ID for the given status string.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project where the statuses are defined.
      status: status string.
      autocreate: if not already in the DB, store it and generate a new ID.

    Returns:
      The status ID for the given status string, or None.
    """
    if not status:
      return None

    self._EnsureStatusCacheEntry(cnxn, project_id)
    (_status_id_to_name, status_name_to_id,
     _closed_status_ids) = self.status_cache.GetItem(project_id)
    if status.lower() in status_name_to_id:
      return status_name_to_id[status.lower()]

    if autocreate:
      logging.info('No status %r is known in project %d, so intern it.',
                   status, project_id)
      status_id = self.statusdef_tbl.InsertRow(
          cnxn, project_id=project_id, status=status)
      self.status_row_2lc.InvalidateKeys(cnxn, [project_id])
      self.status_cache.Invalidate(cnxn, project_id)
      return status_id

    return None  # It was not found and we don't want to create it.

  def LookupStatusIDs(self, cnxn, project_id, statuses):
    """Look up several status IDs for the given status strings.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project where the statuses are defined.
      statuses: list of status strings.

    Returns:
      A list of int status IDs.
    """
    result = []
    for stat in statuses:
      status_id = self.LookupStatusID(cnxn, project_id, stat, autocreate=False)
      if status_id:
        result.append(status_id)

    return result

  def LookupClosedStatusIDs(self, cnxn, project_id):
    """Return the IDs of closed statuses defined in the given project."""
    self._EnsureStatusCacheEntry(cnxn, project_id)
    (_status_id_to_name, _status_name_to_id,
     closed_status_ids) = self.status_cache.GetItem(project_id)

    return closed_status_ids

  def LookupClosedStatusIDsAnyProject(self, cnxn):
    """Return the IDs of closed statuses defined in any project."""
    status_id_rows = self.statusdef_tbl.Select(
        cnxn, cols=['id'], means_open=False)
    status_ids = [row[0] for row in status_id_rows]
    return status_ids

  def LookupStatusIDsAnyProject(self, cnxn, status):
    """Return the IDs of statues with the given name in any project."""
    status_id_rows = self.statusdef_tbl.Select(
        cnxn, cols=['id'], status=status)
    status_ids = [row[0] for row in status_id_rows]
    return status_ids

  # TODO(jrobbins): regex matching for status values.

  ### Issue tracker configuration objects

  def GetProjectConfigs(self, cnxn, project_ids, use_cache=True):
    """Get several project issue config objects."""
    config_dict, missed_ids = self.config_2lc.GetAll(
        cnxn, project_ids, use_cache=use_cache)
    if missed_ids:
      raise exceptions.NoSuchProjectException()
    return config_dict

  def GetProjectConfig(self, cnxn, project_id, use_cache=True):
    """Load a ProjectIssueConfig for the specified project from the database.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the current project.
      use_cache: if False, always hit the database.

    Returns:
      A ProjectIssueConfig describing how the issue tracker in the specified
      project is configured.  Projects only have a stored ProjectIssueConfig if
      a project owner has edited the configuration.  Other projects use a
      default configuration.
    """
    config_dict = self.GetProjectConfigs(
        cnxn, [project_id], use_cache=use_cache)
    return config_dict[project_id]

  def TemplatesWithComponent(self, cnxn, component_id, config):
    """Returns all templates with the specified component.

    Args:
      cnxn: connection to SQL database.
      component_id: int component id.
      config: ProjectIssueConfig instance.
    """
    template2component_rows = self.template2component_tbl.Select(
        cnxn, cols=['template_id'], component_id=component_id)
    template_ids = [r[0] for r in template2component_rows]
    return [t for t in config.templates if t.template_id in template_ids]

  def StoreConfig(self, cnxn, config):
    """Update an issue config in the database.

    Args:
      cnxn: connection to SQL database.
      config: ProjectIssueConfig PB to update.
    """
    # TODO(jrobbins): Convert default template index values into foreign
    # key references.  Updating an entire config might require (1) adding
    # new templates, (2) updating the config with new foreign key values,
    # and finally (3) deleting only the specific templates that should be
    # deleted.
    self.projectissueconfig_tbl.InsertRow(
        cnxn, replace=True,
        project_id=config.project_id,
        statuses_offer_merge=' '.join(config.statuses_offer_merge),
        exclusive_label_prefixes=' '.join(config.exclusive_label_prefixes),
        default_template_for_developers=config.default_template_for_developers,
        default_template_for_users=config.default_template_for_users,
        default_col_spec=config.default_col_spec,
        default_sort_spec=config.default_sort_spec,
        default_x_attr=config.default_x_attr,
        default_y_attr=config.default_y_attr,
        member_default_query=config.member_default_query,
        custom_issue_entry_url=config.custom_issue_entry_url,
        commit=False)

    self._UpdateTemplates(cnxn, config)
    self._UpdateWellKnownLabels(cnxn, config)
    self._UpdateWellKnownStatuses(cnxn, config)
    cnxn.Commit()

  def _UpdateTemplates(self, cnxn, config):
    """Update the templates part of a project's issue configuration.

    Args:
      cnxn: connection to SQL database.
      config: ProjectIssueConfig PB to update in the DB.
    """
    # Delete dependent rows of existing templates.  It is all rewritten below.
    template_id_rows = self.template_tbl.Select(
      cnxn, cols=['id'], project_id=config.project_id)
    template_ids = [row[0] for row in template_id_rows]
    self.template2label_tbl.Delete(
      cnxn, template_id=template_ids, commit=False)
    self.template2component_tbl.Delete(
      cnxn, template_id=template_ids, commit=False)
    self.template2admin_tbl.Delete(
      cnxn, template_id=template_ids, commit=False)
    self.template2fieldvalue_tbl.Delete(
      cnxn, template_id=template_ids, commit=False)
    self.template_tbl.Delete(
      cnxn, project_id=config.project_id, commit=False)

    # Now, update existing ones and add new ones.
    template_rows = []
    for template in config.templates:
      row = (template.template_id,
             config.project_id,
             template.name,
             template.content,
             template.summary,
             template.summary_must_be_edited,
             template.owner_id or None,
             template.status,
             template.members_only,
             template.owner_defaults_to_member,
             template.component_required)
      template_rows.append(row)

    # Maybe first insert ones that have a template_id and then insert new ones
    # separately.
    generated_ids = self.template_tbl.InsertRows(
        cnxn, TEMPLATE_COLS, template_rows, replace=True, commit=False,
        return_generated_ids=True)
    logging.info('generated_ids is %r', generated_ids)
    for template in config.templates:
      if not template.template_id:
        # Get IDs from the back of the list because the original template IDs
        # have already been added to template_rows.
        template.template_id = generated_ids.pop()

    template2label_rows = []
    template2component_rows = []
    template2admin_rows = []
    template2fieldvalue_rows = []
    for template in config.templates:
      for label in template.labels:
        if label:
          template2label_rows.append((template.template_id, label))
      for component_id in template.component_ids:
        template2component_rows.append((template.template_id, component_id))
      for admin_id in template.admin_ids:
        template2admin_rows.append((template.template_id, admin_id))
      for fv in template.field_values:
        template2fieldvalue_rows.append(
            (template.template_id, fv.field_id, fv.int_value, fv.str_value,
             fv.user_id or None, fv.date_value))

    self.template2label_tbl.InsertRows(
        cnxn, TEMPLATE2LABEL_COLS, template2label_rows, ignore=True,
        commit=False)
    self.template2component_tbl.InsertRows(
        cnxn, TEMPLATE2COMPONENT_COLS, template2component_rows, commit=False)
    self.template2admin_tbl.InsertRows(
        cnxn, TEMPLATE2ADMIN_COLS, template2admin_rows, commit=False)
    self.template2fieldvalue_tbl.InsertRows(
        cnxn, TEMPLATE2FIELDVALUE_COLS, template2fieldvalue_rows, commit=False)

  def _UpdateWellKnownLabels(self, cnxn, config):
    """Update the labels part of a project's issue configuration.

    Args:
      cnxn: connection to SQL database.
      config: ProjectIssueConfig PB to update in the DB.
    """
    update_labeldef_rows = []
    new_labeldef_rows = []
    for rank, wkl in enumerate(config.well_known_labels):
      # We must specify label ID when replacing, otherwise a new ID is made.
      label_id = self.LookupLabelID(
          cnxn, config.project_id, wkl.label, autocreate=False)
      if label_id:
        row = (label_id, config.project_id, rank, wkl.label,
               wkl.label_docstring, wkl.deprecated)
        update_labeldef_rows.append(row)
      else:
        row = (
            config.project_id, rank, wkl.label, wkl.label_docstring,
            wkl.deprecated)
        new_labeldef_rows.append(row)

    self.labeldef_tbl.Update(
        cnxn, {'rank': None}, project_id=config.project_id, commit=False)
    self.labeldef_tbl.InsertRows(
        cnxn, LABELDEF_COLS, update_labeldef_rows, replace=True, commit=False)
    self.labeldef_tbl.InsertRows(
        cnxn, LABELDEF_COLS[1:], new_labeldef_rows, commit=False)
    self.label_row_2lc.InvalidateKeys(cnxn, [config.project_id])
    self.label_cache.Invalidate(cnxn, config.project_id)

  def _UpdateWellKnownStatuses(self, cnxn, config):
    """Update the status part of a project's issue configuration.

    Args:
      cnxn: connection to SQL database.
      config: ProjectIssueConfig PB to update in the DB.
    """
    update_statusdef_rows = []
    new_statusdef_rows = []
    for rank, wks in enumerate(config.well_known_statuses):
      # We must specify label ID when replacing, otherwise a new ID is made.
      status_id = self.LookupStatusID(cnxn, config.project_id, wks.status,
                                      autocreate=False)
      if status_id is not None:
        row = (status_id, config.project_id, rank, wks.status,
               bool(wks.means_open), wks.status_docstring, wks.deprecated)
        update_statusdef_rows.append(row)
      else:
        row = (config.project_id, rank, wks.status,
               bool(wks.means_open), wks.status_docstring, wks.deprecated)
        new_statusdef_rows.append(row)

    self.statusdef_tbl.Update(
        cnxn, {'rank': None}, project_id=config.project_id, commit=False)
    self.statusdef_tbl.InsertRows(
        cnxn, STATUSDEF_COLS, update_statusdef_rows, replace=True,
        commit=False)
    self.statusdef_tbl.InsertRows(
        cnxn, STATUSDEF_COLS[1:], new_statusdef_rows, commit=False)
    self.status_row_2lc.InvalidateKeys(cnxn, [config.project_id])
    self.status_cache.Invalidate(cnxn, config.project_id)

  def UpdateConfig(
      self, cnxn, project, well_known_statuses=None,
      statuses_offer_merge=None, well_known_labels=None,
      excl_label_prefixes=None, templates=None,
      default_template_for_developers=None, default_template_for_users=None,
      list_prefs=None, restrict_to_known=None):
    """Update project's issue tracker configuration with the given info.

    Args:
      cnxn: connection to SQL database.
      project: the project in which to update the issue tracker config.
      well_known_statuses: [(status_name, docstring, means_open, deprecated),..]
      statuses_offer_merge: list of status values that trigger UI to merge.
      well_known_labels: [(label_name, docstring, deprecated),...]
      excl_label_prefixes: list of prefix strings.  Each issue should
          have only one label with each of these prefixed.
      templates: List of PBs for issue templates.
      default_template_for_developers: int ID of template to use for devs.
      default_template_for_users: int ID of template to use for non-members.
      list_prefs: defaults for columns and sorting.
      restrict_to_known: optional bool to allow project owners
          to limit issue status and label values to only the well-known ones.

    Returns:
      The updated ProjectIssueConfig PB.
    """
    project_id = project.project_id
    project_config = self.GetProjectConfig(cnxn, project_id, use_cache=False)

    if well_known_statuses is not None:
      tracker_bizobj.SetConfigStatuses(project_config, well_known_statuses)

    if statuses_offer_merge is not None:
      project_config.statuses_offer_merge = statuses_offer_merge

    if well_known_labels is not None:
      tracker_bizobj.SetConfigLabels(project_config, well_known_labels)

    if excl_label_prefixes is not None:
      project_config.exclusive_label_prefixes = excl_label_prefixes

    if templates is not None:
      project_config.templates = templates

    if default_template_for_developers is not None:
      project_config.default_template_for_developers = (
          default_template_for_developers)
    if default_template_for_users is not None:
      project_config.default_template_for_users = default_template_for_users

    if list_prefs:
      (default_col_spec, default_sort_spec, default_x_attr, default_y_attr,
       member_default_query) = list_prefs
      project_config.default_col_spec = default_col_spec
      project_config.default_col_spec = default_col_spec
      project_config.default_sort_spec = default_sort_spec
      project_config.default_x_attr = default_x_attr
      project_config.default_y_attr = default_y_attr
      project_config.member_default_query = member_default_query

    if restrict_to_known is not None:
      project_config.restrict_to_known = restrict_to_known

    self.StoreConfig(cnxn, project_config)
    self.config_2lc.InvalidateKeys(cnxn, [project_id])
    self.InvalidateMemcacheForEntireProject(project_id)
    # Invalidate all issue caches in all frontends to clear out
    # sorting.art_values_cache which now has wrong sort orders.
    cache_manager = self.config_2lc.cache.cache_manager
    cache_manager.StoreInvalidateAll(cnxn, 'issue')

    return project_config

  def ExpungeConfig(self, cnxn, project_id):
    """Completely delete the specified project config from the database."""
    logging.info('expunging the config for %r', project_id)
    template_id_rows = self.template_tbl.Select(
        cnxn, cols=['id'], project_id=project_id)
    template_ids = [row[0] for row in template_id_rows]
    self.template2label_tbl.Delete(cnxn, template_id=template_ids)
    self.template2component_tbl.Delete(cnxn, template_id=template_ids)
    self.template_tbl.Delete(cnxn, project_id=project_id)
    self.statusdef_tbl.Delete(cnxn, project_id=project_id)
    self.labeldef_tbl.Delete(cnxn, project_id=project_id)
    self.projectissueconfig_tbl.Delete(cnxn, project_id=project_id)

    self.config_2lc.InvalidateKeys(cnxn, [project_id])

  ### Custom field definitions

  def CreateFieldDef(
      self, cnxn, project_id, field_name, field_type_str, applic_type,
      applic_pred, is_required, is_niche, is_multivalued,
      min_value, max_value, regex, needs_member, needs_perm,
      grants_perm, notify_on, date_action_str, docstring, admin_ids):
    """Create a new field definition with the given info.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the current project.
      field_name: name of the new custom field.
      field_type_str: string identifying the type of the custom field.
      applic_type: string specifying issue type the field is applicable to.
      applic_pred: string condition to test if the field is applicable.
      is_required: True if the field should be required on issues.
      is_niche: True if the field is not initially offered for editing, so users
          must click to reveal such special-purpose or experimental fields.
      is_multivalued: True if the field can occur multiple times on one issue.
      min_value: optional validation for int_type fields.
      max_value: optional validation for int_type fields.
      regex: optional validation for str_type fields.
      needs_member: optional validation for user_type fields.
      needs_perm: optional validation for user_type fields.
      grants_perm: optional string for perm to grant any user named in field.
      notify_on: int enum of when to notify users named in field.
      date_action_str: string saying who to notify when a date arrives.
      docstring: string describing this field.
      admin_ids: list of additional user IDs who can edit this field def.

    Returns:
      Integer field_id of the new field definition.
    """
    assert not (is_required and is_niche), (
        'A field cannot be both requrired and niche')
    assert date_action_str in DATE_ACTION_ENUM
    field_id = self.fielddef_tbl.InsertRow(
        cnxn, project_id=project_id,
        field_name=field_name, field_type=field_type_str,
        applicable_type=applic_type, applicable_predicate=applic_pred,
        is_required=is_required, is_niche=is_niche,
        is_multivalued=is_multivalued,
        min_value=min_value, max_value=max_value, regex=regex,
        needs_member=needs_member, needs_perm=needs_perm,
        grants_perm=grants_perm, notify_on=NOTIFY_ON_ENUM[notify_on],
        date_action=date_action_str, docstring=docstring, commit=False)
    self.fielddef2admin_tbl.InsertRows(
        cnxn, FIELDDEF2ADMIN_COLS,
        [(field_id, admin_id) for admin_id in admin_ids],
        commit=False)
    cnxn.Commit()
    self.config_2lc.InvalidateKeys(cnxn, [project_id])
    self.InvalidateMemcacheForEntireProject(project_id)
    return field_id

  def _DeserializeFields(self, def_rows):
    """Convert field defs into bi-directional mappings of names and IDs."""
    field_id_to_name = {
        field_id: field
        for field_id, _pid, _rank, field, _doc in def_rows}
    field_name_to_id = {
        field.lower(): field_id
        for field_id, field in field_id_to_name.iteritems()}

    return field_id_to_name, field_name_to_id

  def GetFieldDefRows(self, cnxn, project_id):
    """Get SQL result rows for all fields used in the specified project."""
    pids_to_field_rows, misses = self.field_row_2lc.GetAll(cnxn, [project_id])
    assert not misses
    return pids_to_field_rows[project_id]

  def _EnsureFieldCacheEntry(self, cnxn, project_id):
    """Make sure that self.field_cache has an entry for project_id."""
    if not self.field_cache.HasItem(project_id):
      def_rows = self.GetFieldDefRows(cnxn, project_id)
      self.field_cache.CacheItem(
          project_id, self._DeserializeFields(def_rows))

  def LookupField(self, cnxn, project_id, field_id):
    """Lookup a field string given the field_id.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project where the label is defined or used.
      field_id: int field ID.

    Returns:
      Field name string for the given field_id, or None.
    """
    self._EnsureFieldCacheEntry(cnxn, project_id)
    field_id_to_name, _field_name_to_id = self.field_cache.GetItem(
        project_id)
    return field_id_to_name.get(field_id)

  def LookupFieldID(self, cnxn, project_id, field):
    """Look up a field ID.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the project where the fields are defined.
      field: field string.

    Returns:
      The field ID for the given field string.
    """
    self._EnsureFieldCacheEntry(cnxn, project_id)
    _field_id_to_name, field_name_to_id = self.field_cache.GetItem(
        project_id)
    return field_name_to_id.get(field.lower())

  def SoftDeleteFieldDef(self, cnxn, project_id, field_id):
    """Mark the specified field as deleted, it will be reaped later."""
    self.fielddef_tbl.Update(cnxn, {'is_deleted': True}, id=field_id)
    self.config_2lc.InvalidateKeys(cnxn, [project_id])
    self.InvalidateMemcacheForEntireProject(project_id)

  # TODO(jrobbins): GC deleted field defs after field values are gone.

  def UpdateFieldDef(
      self, cnxn, project_id, field_id, field_name=None,
      applicable_type=None, applicable_predicate=None, is_required=None,
      is_niche=None, is_multivalued=None, min_value=None, max_value=None,
      regex=None, needs_member=None, needs_perm=None, grants_perm=None,
      notify_on=None, date_action=None, docstring=None, admin_ids=None):
    """Update the specified field definition."""
    new_values = {}
    if field_name is not None:
      new_values['field_name'] = field_name
    if applicable_type is not None:
      new_values['applicable_type'] = applicable_type
    if applicable_predicate is not None:
      new_values['applicable_predicate'] = applicable_predicate
    if is_required is not None:
      new_values['is_required'] = bool(is_required)
    if is_niche is not None:
      new_values['is_niche'] = bool(is_niche)
    if is_multivalued is not None:
      new_values['is_multivalued'] = bool(is_multivalued)
    if min_value is not None:
      new_values['min_value'] = min_value
    if max_value is not None:
      new_values['max_value'] = max_value
    if regex is not None:
      new_values['regex'] = regex
    if needs_member is not None:
      new_values['needs_member'] = needs_member
    if needs_perm is not None:
      new_values['needs_perm'] = needs_perm
    if grants_perm is not None:
      new_values['grants_perm'] = grants_perm
    if notify_on is not None:
      new_values['notify_on'] = NOTIFY_ON_ENUM[notify_on]
    if date_action is not None:
      assert date_action in DATE_ACTION_ENUM
      new_values['date_action'] = date_action
    if docstring is not None:
      new_values['docstring'] = docstring

    self.fielddef_tbl.Update(cnxn, new_values, id=field_id, commit=False)
    self.fielddef2admin_tbl.Delete(cnxn, field_id=field_id, commit=False)
    self.fielddef2admin_tbl.InsertRows(
        cnxn, FIELDDEF2ADMIN_COLS,
        [(field_id, admin_id) for admin_id in admin_ids],
        commit=False)
    cnxn.Commit()
    self.config_2lc.InvalidateKeys(cnxn, [project_id])
    self.InvalidateMemcacheForEntireProject(project_id)

  ### Component definitions

  def FindMatchingComponentIDsAnyProject(self, cnxn, path_list, exact=True):
    """Look up component IDs across projects.

    Args:
      cnxn: connection to SQL database.
      path_list: list of component path prefixes.
      exact: set to False to include all components which have one of the
          given paths as their ancestor, instead of exact matches.

    Returns:
      A list of component IDs of component's whose paths match path_list.
    """
    or_terms = []
    args = []
    for path in path_list:
      or_terms.append('path = %s')
      args.append(path)

    if not exact:
      for path in path_list:
        or_terms.append('path LIKE %s')
        args.append(path + '>%')

    cond_str = '(' + ' OR '.join(or_terms) + ')'
    rows = self.componentdef_tbl.Select(
        cnxn, cols=['id'], where=[(cond_str, args)])
    return [row[0] for row in rows]

  def CreateComponentDef(
      self, cnxn, project_id, path, docstring, deprecated, admin_ids, cc_ids,
      created, creator_id, label_ids):
    """Create a new component definition with the given info.

    Args:
      cnxn: connection to SQL database.
      project_id: int ID of the current project.
      path: string pathname of the new component.
      docstring: string describing this field.
      deprecated: whether or not this should be autocompleted
      admin_ids: list of int IDs of users who can administer.
      cc_ids: list of int IDs of users to notify when an issue in
          this component is updated.
      created: timestamp this component was created at.
      creator_id: int ID of user who created this component.
      label_ids: list of int IDs of labels to add when an issue is
          in this component.

    Returns:
      Integer component_id of the new component definition.
    """
    component_id = self.componentdef_tbl.InsertRow(
        cnxn, project_id=project_id, path=path, docstring=docstring,
        deprecated=deprecated, created=created, creator_id=creator_id,
        commit=False)
    self.component2admin_tbl.InsertRows(
        cnxn, COMPONENT2ADMIN_COLS,
        [(component_id, admin_id) for admin_id in admin_ids],
        commit=False)
    self.component2cc_tbl.InsertRows(
        cnxn, COMPONENT2CC_COLS,
        [(component_id, cc_id) for cc_id in cc_ids],
        commit=False)
    self.component2label_tbl.InsertRows(
        cnxn, COMPONENT2LABEL_COLS,
        [(component_id, label_id) for label_id in label_ids],
        commit=False)
    cnxn.Commit()
    self.config_2lc.InvalidateKeys(cnxn, [project_id])
    self.InvalidateMemcacheForEntireProject(project_id)
    return component_id

  def UpdateComponentDef(
      self, cnxn, project_id, component_id, path=None, docstring=None,
      deprecated=None, admin_ids=None, cc_ids=None, created=None,
      creator_id=None, modified=None, modifier_id=None,
      label_ids=None):
    """Update the specified component definition."""
    new_values = {}
    if path is not None:
      assert path
      new_values['path'] = path
    if docstring is not None:
      new_values['docstring'] = docstring
    if deprecated is not None:
      new_values['deprecated'] = deprecated
    if created is not None:
      new_values['created'] = created
    if creator_id is not None:
      new_values['creator_id'] = creator_id
    if modified is not None:
      new_values['modified'] = modified
    if modifier_id is not None:
      new_values['modifier_id'] = modifier_id

    if admin_ids is not None:
      self.component2admin_tbl.Delete(
          cnxn, component_id=component_id, commit=False)
      self.component2admin_tbl.InsertRows(
          cnxn, COMPONENT2ADMIN_COLS,
          [(component_id, admin_id) for admin_id in admin_ids],
          commit=False)

    if cc_ids is not None:
      self.component2cc_tbl.Delete(
          cnxn, component_id=component_id, commit=False)
      self.component2cc_tbl.InsertRows(
          cnxn, COMPONENT2CC_COLS,
          [(component_id, cc_id) for cc_id in cc_ids],
          commit=False)

    if label_ids is not None:
      self.component2label_tbl.Delete(
          cnxn, component_id=component_id, commit=False)
      self.component2label_tbl.InsertRows(
          cnxn, COMPONENT2LABEL_COLS,
          [(component_id, label_id) for label_id in label_ids],
          commit=False)

    self.componentdef_tbl.Update(
        cnxn, new_values, id=component_id, commit=False)
    cnxn.Commit()
    self.config_2lc.InvalidateKeys(cnxn, [project_id])
    self.InvalidateMemcacheForEntireProject(project_id)

  def DeleteComponentDef(self, cnxn, project_id, component_id):
    """Delete the specified component definition."""
    self.component2cc_tbl.Delete(
        cnxn, component_id=component_id, commit=False)
    self.component2admin_tbl.Delete(
        cnxn, component_id=component_id, commit=False)
    self.component2label_tbl.Delete(
        cnxn, component_id=component_id, commit=False)
    self.componentdef_tbl.Delete(cnxn, id=component_id, commit=False)
    cnxn.Commit()
    self.config_2lc.InvalidateKeys(cnxn, [project_id])
    self.InvalidateMemcacheForEntireProject(project_id)

  ### Memcache management

  def InvalidateMemcache(self, issues, key_prefix=''):
    """Delete the memcache entries for issues and their project-shard pairs."""
    memcache.delete_multi(
        [str(issue.issue_id) for issue in issues], key_prefix='issue:',
        seconds=5)
    project_shards = set(
        (issue.project_id, issue.issue_id % settings.num_logical_shards)
        for issue in issues)
    self._InvalidateMemcacheShards(project_shards, key_prefix=key_prefix)

  def _InvalidateMemcacheShards(self, project_shards, key_prefix=''):
    """Delete the memcache entries for the given project-shard pairs.

    Deleting these rows does not delete the actual cached search results
    but it does mean that they will be considered stale and thus not used.

    Args:
      project_shards: list of (pid, sid) pairs.
      key_prefix: string to pass as memcache key prefix.
    """
    cache_entries = ['%d;%d' % ps for ps in project_shards]
    # Whenever any project is invalidated, also invalidate the 'all'
    # entry that is used in site-wide searches.
    shard_id_set = {sid for _pid, sid in project_shards}
    cache_entries.extend(('all;%d' % sid) for sid in shard_id_set)

    memcache.delete_multi(cache_entries, key_prefix=key_prefix)

  def InvalidateMemcacheForEntireProject(self, project_id):
    """Delete the memcache entries for all searches in a project."""
    project_shards = set((project_id, shard_id)
                         for shard_id in range(settings.num_logical_shards))
    self._InvalidateMemcacheShards(project_shards)
    memcache.delete_multi([str(project_id)], key_prefix='config:')
    memcache.delete_multi([str(project_id)], key_prefix='label_rows:')
    memcache.delete_multi([str(project_id)], key_prefix='status_rows:')
    memcache.delete_multi([str(project_id)], key_prefix='field_rows:')


class Error(Exception):
  """Base class for errors from this module."""
  pass


class NoSuchComponentException(Error):
  """No component with the specified name exists."""
  pass


class InvalidComponentNameException(Error):
  """The component name is invalid."""
  pass
