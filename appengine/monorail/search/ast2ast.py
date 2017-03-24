# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Convert a user's issue search AST into a simplified AST.

This phase of query processing simplifies the user's query by looking up
the int IDs of any labels, statuses, or components that are mentioned by
name in the original query.  The data needed for lookups is typically cached
in RAM in each backend job, so this will not put much load on the DB.  The
simplified ASTs are later converted into SQL which is simpler and has
fewer joins.

The simplified main query is better because:
  + It is clearly faster, especially in the most common case where config
    data is in RAM.
  + Since less RAM is used to process the main query on each shard, query
    execution time is more consistent with less variability under load.  Less
    variability is good because the user must wait for the slowest shard.
  + The config tables (LabelDef, StatusDef, etc.) exist only on the master, so
    they cannot be mentioned in a query that runs on a shard.
  + The query string itself is shorter when numeric IDs are substituted, which
    means that we can handle user queries with long lists of labels in a
    reasonable-sized query.
  + It bisects the complexity of the operation: it's easier to test and debug
    the lookup and simplification logic plus the main query logic this way
    than it would be to deal with an even more complex SQL main query.
"""

import logging
import re

from proto import ast_pb2
from proto import tracker_pb2
# TODO(jrobbins): if BUILTIN_ISSUE_FIELDS was passed through, I could
# remove this dep.
from search import query2ast
from services import user_svc
from tracker import tracker_bizobj


def PreprocessAST(
    cnxn, query_ast, project_ids, services, harmonized_config):
  """Preprocess the query by doing lookups so that the SQL query is simpler.

  Args:
    cnxn: connection to SQL database.
    query_ast: user query abstract syntax tree parsed by query2ast.py.
    project_ids: collection of int project IDs to use to look up status values
        and labels.
    services: Connections to persistence layer for users and configs.
    harmonized_config: harmonized config for all projects being searched.

  Returns:
    A new QueryAST PB with simplified conditions.  Specifically, string values
    for labels, statuses, and components are replaced with the int IDs of
    those items.  Also, is:open is distilled down to
    status_id != closed_status_ids.
  """
  new_conjs = []
  for conj in query_ast.conjunctions:
    new_conds = [
        _PreprocessCond(
            cnxn, cond, project_ids, services, harmonized_config)
        for cond in conj.conds]
    new_conjs.append(ast_pb2.Conjunction(conds=new_conds))

  return ast_pb2.QueryAST(conjunctions=new_conjs)


def _PreprocessIsOpenCond(
    cnxn, cond, project_ids, services, _harmonized_config):
  """Preprocess an is:open cond into status_id != closed_status_ids."""
  if project_ids:
    closed_status_ids = []
    for project_id in project_ids:
      closed_status_ids.extend(services.config.LookupClosedStatusIDs(
          cnxn, project_id))
  else:
    closed_status_ids = services.config.LookupClosedStatusIDsAnyProject(cnxn)

  # Invert the operator, because we're comparing against *closed* statuses.
  if cond.op == ast_pb2.QueryOp.EQ:
    op = ast_pb2.QueryOp.NE
  elif cond.op == ast_pb2.QueryOp.NE:
    op = ast_pb2.QueryOp.EQ
  else:
    raise MalformedQuery('Open condidtion got nonsensical op %r' % cond.op)

  return ast_pb2.Condition(
      op=op, field_defs=[query2ast.BUILTIN_ISSUE_FIELDS['status_id']],
      int_values=closed_status_ids)


def _PreprocessIsBlockedCond(
    _cnxn, cond, _project_ids, _services, _harmonized_config):
  """Preprocess an is:blocked cond into issues that are blocked."""
  if cond.op == ast_pb2.QueryOp.EQ:
    op = ast_pb2.QueryOp.IS_DEFINED
  elif cond.op == ast_pb2.QueryOp.NE:
    op = ast_pb2.QueryOp.IS_NOT_DEFINED
  else:
    raise MalformedQuery('Blocked condition got nonsensical op %r' % cond.op)

  return ast_pb2.Condition(
      op=op, field_defs=[query2ast.BUILTIN_ISSUE_FIELDS['blockedon_id']])


def _PreprocessIsSpamCond(
    _cnxn, cond, _project_ids, _services, _harmonized_config):
  """Preprocess an is:spam cond into is_spam == 1."""
  if cond.op == ast_pb2.QueryOp.EQ:
    int_values = [1]
  elif cond.op == ast_pb2.QueryOp.NE:
    int_values = [0]
  else:
    raise MalformedQuery('Spam condition got nonsensical op %r' % cond.op)

  return ast_pb2.Condition(
      op=ast_pb2.QueryOp.EQ,
      field_defs=[query2ast.BUILTIN_ISSUE_FIELDS['is_spam']],
      int_values=int_values)


def _PreprocessBlockedOnCond(
    cnxn, cond, project_ids, services, _harmonized_config):
  """Preprocess blockedon=xyz and has:blockedon conds.

  Preprocesses blockedon=xyz cond into blockedon_id:issue_ids.
  Preprocesses has:blockedon cond into issues that are blocked on other issues.
  """
  issue_ids = _GetIssueIDsFromLocalIdsCond(cnxn, cond, project_ids, services)
  return ast_pb2.Condition(
      op=_TextOpToIntOp(cond.op),
      field_defs=[query2ast.BUILTIN_ISSUE_FIELDS['blockedon_id']],
      int_values=issue_ids)


def _PreprocessBlockingCond(
    cnxn, cond, project_ids, services, _harmonized_config):
  """Preprocess blocking=xyz and has:blocking conds.

  Preprocesses blocking=xyz cond into blocking_id:issue_ids.
  Preprocesses has:blocking cond into issues that are blocking other issues.
  """
  issue_ids = _GetIssueIDsFromLocalIdsCond(cnxn, cond, project_ids, services)
  return ast_pb2.Condition(
      op=_TextOpToIntOp(cond.op),
      field_defs=[query2ast.BUILTIN_ISSUE_FIELDS['blocking_id']],
      int_values=issue_ids)


def _PreprocessMergedIntoCond(
    cnxn, cond, project_ids, services, _harmonized_config):
  """Preprocess mergedinto=xyz and has:mergedinto conds.

  Preprocesses mergedinto=xyz cond into mergedinto_id:issue_ids.
  Preprocesses has:mergedinto cond into has:mergedinto_id.
  """
  issue_ids = _GetIssueIDsFromLocalIdsCond(cnxn, cond, project_ids, services)
  return ast_pb2.Condition(
      op=_TextOpToIntOp(cond.op),
      field_defs=[query2ast.BUILTIN_ISSUE_FIELDS['mergedinto_id']],
      int_values=issue_ids)


def _GetIssueIDsFromLocalIdsCond(cnxn, cond, project_ids, services):
  """Returns global IDs from the local IDs provided in the cond."""
  # Get {project_name: project} for all projects in project_ids.
  ids_to_projects = services.project.GetProjects(cnxn, project_ids)
  ref_projects = {pb.project_name: pb for pb in ids_to_projects.itervalues()}
  # Populate default_project_name if there is only one project id provided.
  default_project_name = None
  if len(ref_projects) == 1:
    default_project_name = ref_projects.values()[0].project_name

  # Populate refs with (project_name, local_id) pairs.
  refs = []
  for val in cond.str_values:
    project_name, local_id = tracker_bizobj.ParseIssueRef(val)
    if not project_name:
      if not default_project_name:
        # TODO(rmistry): Support the below.
        raise MalformedQuery(
            'Searching for issues accross multiple/all projects without '
            'project prefixes is ambiguous and is currently not supported.')
      project_name = default_project_name
    refs.append((project_name, int(local_id)))

  issue_ids, _misses =  services.issue.ResolveIssueRefs(
      cnxn, ref_projects, default_project_name, refs)
  return issue_ids


def _PreprocessStatusCond(
    cnxn, cond, project_ids, services, _harmonized_config):
  """Preprocess a status=names cond into status_id=IDs."""
  if project_ids:
    status_ids = []
    for project_id in project_ids:
      status_ids.extend(services.config.LookupStatusIDs(
          cnxn, project_id, cond.str_values))
  else:
    status_ids = services.config.LookupStatusIDsAnyProject(
        cnxn, cond.str_values)

  return ast_pb2.Condition(
      op=_TextOpToIntOp(cond.op),
      field_defs=[query2ast.BUILTIN_ISSUE_FIELDS['status_id']],
      int_values=status_ids)


def _IsEqualityOp(op):
  """Return True for EQ and NE."""
  return op in (ast_pb2.QueryOp.EQ, ast_pb2.QueryOp.NE)


def _IsDefinedOp(op):
  """Return True for IS_DEFINED and IS_NOT_DEFINED."""
  return op in (ast_pb2.QueryOp.IS_DEFINED, ast_pb2.QueryOp.IS_NOT_DEFINED)


def _TextOpToIntOp(op):
  """If a query is optimized from string to ID matching, use an equality op."""
  if op == ast_pb2.QueryOp.TEXT_HAS or op == ast_pb2.QueryOp.KEY_HAS:
    return ast_pb2.QueryOp.EQ
  elif op == ast_pb2.QueryOp.NOT_TEXT_HAS:
    return ast_pb2.QueryOp.NE
  return op


def _MakePrefixRegex(cond):
  """Return a regex to match strings that start with cond values."""
  all_prefixes = '|'.join(map(re.escape, cond.str_values))
  return re.compile(r'(%s)-.+' % all_prefixes, re.I)


def _MakeKeyValueRegex(cond):
  """Return a regex to match the first token and remaining text separately."""
  keys, values = zip(*map(lambda x: x.split('-', 1), cond.str_values))
  if len(set(keys)) != 1:
    raise MalformedQuery(
        "KeyValue query with multiple different keys: %r" % cond.str_values)
  all_values = '|'.join(map(re.escape, values))
  return re.compile(r'%s-.*\b(%s)\b.*' % (keys[0], all_values), re.I)


def _MakeWordBoundaryRegex(cond):
  """Return a regex to match the cond values as whole words."""
  all_words = '|'.join(map(re.escape, cond.str_values))
  return re.compile(r'.*\b(%s)\b.*' % all_words, re.I)


def _PreprocessLabelCond(
    cnxn, cond, project_ids, services, _harmonized_config):
  """Preprocess a label=names cond into label_id=IDs."""
  if project_ids:
    label_ids = []
    for project_id in project_ids:
      if _IsEqualityOp(cond.op):
        label_ids.extend(services.config.LookupLabelIDs(
            cnxn, project_id, cond.str_values))
      elif _IsDefinedOp(cond.op):
        label_ids.extend(services.config.LookupIDsOfLabelsMatching(
            cnxn, project_id, _MakePrefixRegex(cond)))
      elif cond.op == ast_pb2.QueryOp.KEY_HAS:
        label_ids.extend(services.config.LookupIDsOfLabelsMatching(
            cnxn, project_id, _MakeKeyValueRegex(cond)))
      else:
        label_ids.extend(services.config.LookupIDsOfLabelsMatching(
            cnxn, project_id, _MakeWordBoundaryRegex(cond)))
  else:
    if _IsEqualityOp(cond.op):
      label_ids = services.config.LookupLabelIDsAnyProject(
          cnxn, cond.str_values)
    elif _IsDefinedOp(cond.op):
      label_ids = services.config.LookupIDsOfLabelsMatchingAnyProject(
          cnxn, _MakePrefixRegex(cond))
    elif cond.op == ast_pb2.QueryOp.KEY_HAS:
      label_ids = services.config.LookupIDsOfLabelsMatchingAnyProject(
          cnxn, _MakeKeyValueRegex(cond))
    else:
      label_ids = services.config.LookupIDsOfLabelsMatchingAnyProject(
          cnxn, _MakeWordBoundaryRegex(cond))

  return ast_pb2.Condition(
      op=_TextOpToIntOp(cond.op),
      field_defs=[query2ast.BUILTIN_ISSUE_FIELDS['label_id']],
      int_values=label_ids)


def _PreprocessComponentCond(
    cnxn, cond, project_ids, services, harmonized_config):
  """Preprocess a component= or component:name cond into component_id=IDs."""
  exact = _IsEqualityOp(cond.op)
  component_ids = []
  if project_ids:
    # We are searching within specific projects, so harmonized_config
    # holds the config data for all those projects.
    for comp_path in cond.str_values:
      component_ids.extend(tracker_bizobj.FindMatchingComponentIDs(
          comp_path, harmonized_config, exact=exact))
  else:
    # We are searching across the whole site, so we have no harmonized_config
    # to use.
    component_ids = services.config.FindMatchingComponentIDsAnyProject(
        cnxn, cond.str_values, exact=exact)

  return ast_pb2.Condition(
      op=_TextOpToIntOp(cond.op),
      field_defs=[query2ast.BUILTIN_ISSUE_FIELDS['component_id']],
      int_values=component_ids)


def _PreprocessExactUsers(cnxn, cond, user_service, id_fields):
  """Preprocess a foo=emails cond into foo_id=IDs, if exact user match.

  This preprocesing step converts string conditions to int ID conditions.
  E.g., [owner=email] to [owner_id=ID].  It only does it in cases
  where (a) the email was "me", so it was already converted to an string of
  digits in the search pipeline, or (b) it is "user@domain" which resolves to
  a known Monorail user.  It is also possible to search for, e.g.,
  [owner:substring], but such searches remain 'owner' field searches rather
  than 'owner_id', and they cannot be combined with the "me" keyword.

  Args:
    cnxn: connection to the DB.
    cond: original parsed query Condition PB.
    user_service: connection to user persistence layer.
    id_fields: list of the search fields to use if the conversion to IDs
        succeeds.

  Returns:
    A new Condition PB that checks the id_field.  Or, the original cond.
  """
  op = _TextOpToIntOp(cond.op)
  if _IsDefinedOp(op):
    # No need to look up any IDs if we are just testing for any defined value.
    return ast_pb2.Condition(op=op, field_defs=id_fields)

  # This preprocessing step is only for ops that compare whole values, not
  # substrings.
  if not _IsEqualityOp(op):
    logging.info('could not convert to IDs because op is %r', op)
    return cond

  user_ids = []
  for val in cond.str_values:
    try:
      user_ids.append(int(val))
    except ValueError:
      try:
        user_ids.append(user_service.LookupUserID(cnxn, val))
      except user_svc.NoSuchUserException:
        logging.info('could not convert user %r to int ID', val)
        return cond  # preprocessing failed, stick with the original cond.

  return ast_pb2.Condition(op=op, field_defs=id_fields, int_values=user_ids)


def _PreprocessOwnerCond(
    cnxn, cond, _project_ids, services, _harmonized_config):
  """Preprocess a owner=emails cond into owner_id=IDs, if exact user match."""
  return _PreprocessExactUsers(
      cnxn, cond, services.user, [query2ast.BUILTIN_ISSUE_FIELDS['owner_id']])


def _PreprocessCcCond(
    cnxn, cond, _project_ids, services, _harmonized_config):
  """Preprocess a cc=emails cond into cc_id=IDs, if exact user match."""
  return _PreprocessExactUsers(
      cnxn, cond, services.user, [query2ast.BUILTIN_ISSUE_FIELDS['cc_id']])


def _PreprocessReporterCond(
    cnxn, cond, _project_ids, services, _harmonized_config):
  """Preprocess a reporter=emails cond into reporter_id=IDs, if exact."""
  return _PreprocessExactUsers(
      cnxn, cond, services.user,
      [query2ast.BUILTIN_ISSUE_FIELDS['reporter_id']])


def _PreprocessStarredByCond(
    cnxn, cond, _project_ids, services, _harmonized_config):
  """Preprocess a starredby=emails cond into starredby_id=IDs, if exact."""
  return _PreprocessExactUsers(
      cnxn, cond, services.user,
      [query2ast.BUILTIN_ISSUE_FIELDS['starredby_id']])


def _PreprocessCommentByCond(
    cnxn, cond, _project_ids, services, _harmonized_config):
  """Preprocess a commentby=emails cond into commentby_id=IDs, if exact."""
  return _PreprocessExactUsers(
      cnxn, cond, services.user,
      [query2ast.BUILTIN_ISSUE_FIELDS['commentby_id']])


def _PreprocessCustomCond(cnxn, cond, services):
  """Preprocess a custom_user_field=emails cond into IDs, if exact matches."""
  # TODO(jrobbins): better support for ambiguous fields.
  # For now, if any field is USER_TYPE and the value being searched
  # for is the email address of an existing account, it will convert
  # to a user ID and we go with exact ID matching.  Otherwise, we
  # leave the cond as-is for ast2select to do string matching on.
  user_field_defs = [fd for fd in cond.field_defs
                     if fd.field_type == tracker_pb2.FieldTypes.USER_TYPE]
  if user_field_defs:
    return _PreprocessExactUsers(cnxn, cond, services.user, user_field_defs)
  else:
    return cond


_PREPROCESSORS = {
    'open': _PreprocessIsOpenCond,
    'blocked': _PreprocessIsBlockedCond,
    'spam': _PreprocessIsSpamCond,
    'blockedon': _PreprocessBlockedOnCond,
    'blocking': _PreprocessBlockingCond,
    'mergedinto': _PreprocessMergedIntoCond,
    'status': _PreprocessStatusCond,
    'label': _PreprocessLabelCond,
    'component': _PreprocessComponentCond,
    'owner': _PreprocessOwnerCond,
    'cc': _PreprocessCcCond,
    'reporter': _PreprocessReporterCond,
    'starredby': _PreprocessStarredByCond,
    'commentby': _PreprocessCommentByCond,
    }


def _PreprocessCond(
    cnxn, cond, project_ids, services, harmonized_config):
  """Preprocess query by looking up status, label and component IDs."""
  # All the fields in a cond share the same name because they are parsed
  # from a user query term, and the term syntax allows just one field name.
  field_name = cond.field_defs[0].field_name
  assert all(fd.field_name == field_name for fd in cond.field_defs)

  # Case 1: The user is searching custom fields.
  if any(fd.field_id for fd in cond.field_defs):
    # There can't be a mix of custom and built-in fields because built-in
    # field names are reserved and take priority over any conflicting ones.
    assert all(fd.field_id for fd in cond.field_defs)
    return _PreprocessCustomCond(cnxn, cond, services)

  # Case 2: The user is searching a built-in field.
  preproc = _PREPROCESSORS.get(field_name)
  if preproc:
    # We have a preprocessor for that built-in field.
    return preproc(cnxn, cond, project_ids, services, harmonized_config)
  else:
    # We don't have a preprocessor for it.
    return cond


class MalformedQuery(ValueError):
  pass
