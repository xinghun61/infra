# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is govered by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Implementation of the filter rules helper functions."""

import logging
import re

from google.appengine.api import taskqueue

import settings
from framework import exceptions
from framework import framework_bizobj
from framework import framework_constants
from framework import urls
from framework import validate
from proto import ast_pb2
from proto import tracker_pb2
from search import query2ast
from search import searchpipeline
from services import user_svc
from tracker import component_helpers
from tracker import tracker_bizobj
from tracker import tracker_constants
from tracker import tracker_helpers


# Maximum number of filer rules that can be specified in a given
# project.  This helps us bound the amount of time needed to
# (re)compute derived fields.
MAX_RULES = 200

BLOCK = tracker_constants.RECOMPUTE_DERIVED_FIELDS_BLOCK_SIZE


# TODO(jrobbins): implement a more efficient way to update just those
# issues affected by a specific component change.
def RecomputeAllDerivedFields(cnxn, services, project, config):
  """Create work items to update all issues after filter rule changes.

  Args:
    cnxn: connection to SQL database.
    services: connections to backend services.
    project: Project PB for the project that was edited.
    config: ProjectIssueConfig PB for the project that was edited,
        including the edits made.
  """
  if not settings.recompute_derived_fields_in_worker:
    # Background tasks are not enabled, just do everything in the servlet.
    RecomputeAllDerivedFieldsNow(cnxn, services, project, config)
    return

  highest_id = services.issue.GetHighestLocalID(cnxn, project.project_id)
  if highest_id == 0:
    return  # No work to do.

  # Enqueue work items for blocks of issues to recompute.
  steps = range(1, highest_id + 1, BLOCK)
  steps.reverse()  # Update higher numbered issues sooner, old issues last.
  # Cycle through shard_ids just to load-balance among the replicas.  Each
  # block includes all issues in that local_id range, not just 1/10 of them.
  shard_id = 0
  for step in steps:
    params = {
      'project_id': project.project_id,
      'lower_bound': step,
      'upper_bound': min(step + BLOCK, highest_id + 1),
      'shard_id': shard_id,
      }
    logging.info('adding task with params %r', params)
    taskqueue.add(
      url=urls.RECOMPUTE_DERIVED_FIELDS_TASK + '.do', params=params)
    shard_id = (shard_id + 1) % settings.num_logical_shards


def RecomputeAllDerivedFieldsNow(
    cnxn, services, project, config, lower_bound=None, upper_bound=None):
  """Re-apply all filter rules to all issues in a project.

  Args:
    cnxn: connection to SQL database.
    services: connections to persistence layer.
    project: Project PB for the project that was changed.
    config: ProjectIssueConfig for that project.
    lower_bound: optional int lowest issue ID to consider, inclusive.
    upper_bound: optional int highest issue ID to consider, exclusive.

  SIDE-EFFECT: updates all issues in the project. Stores and re-indexes
  all those that were changed.
  """
  if lower_bound is not None and upper_bound is not None:
    issues = services.issue.GetIssuesByLocalIDs(
        cnxn, project.project_id, range(lower_bound, upper_bound),
        use_cache=False)
  else:
    issues = services.issue.GetAllIssuesInProject(
        cnxn, project.project_id, use_cache=False)

  rules = services.features.GetFilterRules(cnxn, project.project_id)
  predicate_asts = ParsePredicateASTs(rules, config, None)
  modified_issues = []
  for issue in issues:
    any_change, _traces = ApplyGivenRules(
        cnxn, services, issue, config, rules, predicate_asts)
    if any_change:
      modified_issues.append(issue)

  services.issue.UpdateIssues(cnxn, modified_issues, just_derived=True)

  # Doing the FTS indexing can be too slow, so queue up the issues
  # that need to be re-indexed by a cron-job later.
  services.issue.EnqueueIssuesForIndexing(
      cnxn, [issue.issue_id for issue in modified_issues])


def ParsePredicateASTs(rules, config, me_user_id):
  """Parse the given rules in QueryAST PBs."""
  predicates = [rule.predicate for rule in rules]
  if me_user_id:
    predicates = [
      searchpipeline.ReplaceKeywordsWithUserID(me_user_id, pred)[0]
      for pred in predicates]
  predicate_asts = [
      query2ast.ParseUserQuery(pred, '', query2ast.BUILTIN_ISSUE_FIELDS, config)
      for pred in predicates]
  return predicate_asts


def ApplyFilterRules(cnxn, services, issue, config):
  """Apply the filter rules for this project to the given issue.

  Args:
    cnxn: database connection, used to look up user IDs.
    services: persistence layer for users, issues, and projects.
    issue: An Issue PB that has just been updated with new explicit values.
    config: The project's issue tracker config PB.

  Returns:
    A pair (any_changes, traces) where any_changes is true if any changes
    were made to the issue derived fields, and traces is a dictionary
    {(field_id, new_value): explanation_str} of traces that
    explain which rule generated each derived value.

  SIDE-EFFECT: update the derived_* fields of the Issue PB.
  """
  rules = services.features.GetFilterRules(cnxn, issue.project_id)
  predicate_asts = ParsePredicateASTs(rules, config, None)
  return ApplyGivenRules(cnxn, services, issue, config, rules, predicate_asts)


def ApplyGivenRules(cnxn, services, issue, config, rules, predicate_asts):
  """Apply the filter rules for this project to the given issue.

  Args:
    cnxn: database connection, used to look up user IDs.
    services: persistence layer for users, issues, and projects.
    issue: An Issue PB that has just been updated with new explicit values.
    config: The project's issue tracker config PB.
    rules: list of FilterRule PBs.

  Returns:
    A pair (any_changes, traces) where any_changes is true if any changes
    were made to the issue derived fields, and traces is a dictionary
    {(field_id, new_value): explanation_str} of traces that
    explain which rule generated each derived value.

  SIDE-EFFECT: update the derived_* fields of the Issue PB.
  """
  (derived_owner_id, derived_status, derived_cc_ids,
   derived_labels, derived_notify_addrs, traces,
   new_warnings, new_errors) = _ComputeDerivedFields(
       cnxn, services, issue, config, rules, predicate_asts)

  any_change = (derived_owner_id != issue.derived_owner_id or
                derived_status != issue.derived_status or
                derived_cc_ids != issue.derived_cc_ids or
                derived_labels != issue.derived_labels or
                derived_notify_addrs != issue.derived_notify_addrs)

  # Remember any derived values.
  issue.derived_owner_id = derived_owner_id
  issue.derived_status = derived_status
  issue.derived_cc_ids = derived_cc_ids
  issue.derived_labels = derived_labels
  issue.derived_notify_addrs = derived_notify_addrs
  issue.derived_warnings = new_warnings
  issue.derived_errors = new_errors

  return any_change, traces


def _ComputeDerivedFields(cnxn, services, issue, config, rules, predicate_asts):
  """Compute derived field values for an issue based on filter rules.

  Args:
    cnxn: database connection, used to look up user IDs.
    services: persistence layer for users, issues, and projects.
    issue: the issue to examine.
    config: ProjectIssueConfig for the project containing the issue.
    rules: list of FilterRule PBs.
    predicate_asts: QueryAST PB for each rule.

  Returns:
    A 8-tuple of derived values for owner_id, status, cc_ids, labels,
    notify_addrs, traces, warnings, and errors.  These values are the result
    of applying all rules in order.  Filter rules only produce derived values
    that do not conflict with the explicit field values of the issue.
  """
  excl_prefixes = [
      prefix.lower() for prefix in config.exclusive_label_prefixes]
  # Examine the explicit labels and Cc's on the issue.
  lower_labels = [lab.lower() for lab in issue.labels]
  label_set = set(lower_labels)
  cc_set = set(issue.cc_ids)
  excl_prefixes_used = set()
  for lab in lower_labels:
    prefix = lab.split('-')[0]
    if prefix in excl_prefixes:
      excl_prefixes_used.add(prefix)
  prefix_values_added = {}

  # Start with the assumption that rules don't change anything, then
  # accumulate changes.
  derived_owner_id = framework_constants.NO_USER_SPECIFIED
  derived_status = ''
  derived_cc_ids = []
  derived_labels = []
  derived_notify_addrs = []
  traces = {}  # {(field_id, new_value): explanation_str}
  new_warnings = []
  new_errors = []

  def AddLabelConsideringExclusivePrefixes(label):
    lab_lower = label.lower()
    if lab_lower in label_set:
      return False  # We already have that label.
    prefix = lab_lower.split('-')[0]
    if '-' in lab_lower and prefix in excl_prefixes:
      if prefix in excl_prefixes_used:
        return False  # Issue already has that prefix.
      # Replace any earlied-added label that had the same exclusive prefix.
      if prefix in prefix_values_added:
        label_set.remove(prefix_values_added[prefix].lower())
        derived_labels.remove(prefix_values_added[prefix])
      prefix_values_added[prefix] = label

    derived_labels.append(label)
    label_set.add(lab_lower)
    return True

  # Apply component labels and auto-cc's before doing the rules.
  components = tracker_bizobj.GetIssueComponentsAndAncestors(issue, config)
  for cd in components:
    for cc_id in cd.cc_ids:
      if cc_id not in cc_set:
        derived_cc_ids.append(cc_id)
        cc_set.add(cc_id)
        traces[(tracker_pb2.FieldID.CC, cc_id)] = (
            'Added by component %s' % cd.path)

    for label_id in cd.label_ids:
      lab = services.config.LookupLabel(cnxn, config.project_id, label_id)
      if AddLabelConsideringExclusivePrefixes(lab):
        traces[(tracker_pb2.FieldID.LABELS, lab)] = (
            'Added by component %s' % cd.path)

  # Apply each rule in order. Later rules see the results of earlier rules.
  # Later rules can overwrite or add to results of earlier rules.
  # TODO(jrobbins): also pass in in-progress values for owner and CCs so
  # that early rules that set those can affect later rules that check them.
  for rule, predicate_ast in zip(rules, predicate_asts):
    (rule_owner_id, rule_status, rule_add_cc_ids,
     rule_add_labels, rule_add_notify, rule_add_warning,
     rule_add_error) = _ApplyRule(
         cnxn, services, rule, predicate_ast, issue, label_set, config)

    # logging.info(
    #    'rule "%s" gave %r, %r, %r, %r, %r',
    #     rule.predicate, rule_owner_id, rule_status, rule_add_cc_ids,
    #     rule_add_labels, rule_add_notify)

    if rule_owner_id and not issue.owner_id:
      derived_owner_id = rule_owner_id
      traces[(tracker_pb2.FieldID.OWNER, rule_owner_id)] = (
        'Added by rule: IF %s THEN SET DEFAULT OWNER' % rule.predicate)

    if rule_status and not issue.status:
      derived_status = rule_status
      traces[(tracker_pb2.FieldID.STATUS, rule_status)] = (
        'Added by rule: IF %s THEN SET DEFAULT STATUS' % rule.predicate)

    for cc_id in rule_add_cc_ids:
      if cc_id not in cc_set:
        derived_cc_ids.append(cc_id)
        cc_set.add(cc_id)
        traces[(tracker_pb2.FieldID.CC, cc_id)] = (
          'Added by rule: IF %s THEN ADD CC' % rule.predicate)

    for lab in rule_add_labels:
      if AddLabelConsideringExclusivePrefixes(lab):
        traces[(tracker_pb2.FieldID.LABELS, lab)] = (
            'Added by rule: IF %s THEN ADD LABEL' % rule.predicate)

    for addr in rule_add_notify:
      if addr not in derived_notify_addrs:
        derived_notify_addrs.append(addr)
        # Note: No trace because also-notify addresses are not shown in the UI.

    if rule_add_warning:
      new_warnings.append(rule_add_warning)
      traces[(tracker_pb2.FieldID.WARNING, rule_add_warning)] = (
        'Added by rule: IF %s THEN ADD WARNING' % rule.predicate)

    if rule_add_error:
      new_errors.append(rule_add_error)
      traces[(tracker_pb2.FieldID.ERROR, rule_add_error)] = (
        'Added by rule: IF %s THEN ADD ERROR' % rule.predicate)

  return (derived_owner_id, derived_status, derived_cc_ids, derived_labels,
          derived_notify_addrs, traces, new_warnings, new_errors)


def EvalPredicate(
    cnxn, services, predicate_ast, issue, label_set, config, owner_id, cc_ids,
    status):
  """Return True if the given issue satisfies the given predicate.

  Args:
    cnxn: Connection to SQL database.
    services: persistence layer for users and issues.
    predicate_ast: QueryAST for rule or saved query string.
    issue: Issue PB of the issue to evaluate.
    label_set: set of lower-cased labels on the issue.
    config: ProjectIssueConfig for the project that contains the issue.
    owner_id: int user ID of the issue owner.
    cc_ids: list of int user IDs of the users Cc'd on the issue.
    status: string status value of the issue.

  Returns:
    True if the issue satisfies the predicate.

  Note: filter rule evaluation passes in only the explicit owner_id,
  cc_ids, and status whereas subscription evaluation passes in the
  combination of explicit values and derived values.
  """
  # TODO(jrobbins): Call ast2ast to simplify the predicate and do
  # most lookups.  Refactor to allow that to be done once.
  project = services.project.GetProject(cnxn, config.project_id)
  for conj in predicate_ast.conjunctions:
    if all(_ApplyCond(cnxn, services, project, cond, issue, label_set, config,
                      owner_id, cc_ids, status)
            for cond in conj.conds):
      return True

  # All OR-clauses were evaluated, but none of them was matched.
  return False


def _ApplyRule(
    cnxn, services, rule_pb, predicate_ast, issue, label_set, config):
  """Test if the given rule should fire and return its result.

  Args:
    cnxn: database connection, used to look up user IDs.
    services: persistence layer for users and issues.
    rule_pb: FilterRule PB instance with a predicate and various actions.
    predicate_ast: QueryAST for the rule predicate.
    issue: The Issue PB to be considered.
    label_set: set of lowercased labels from an issue's explicit
      label_list plus and labels that have accumlated from previous rules.
    config: ProjectIssueConfig for the project containing the issue.

  Returns:
    A 6-tuple of the results from this rule: derived owner id, status,
    cc_ids to add, labels to add, notify addresses to add, and a warning
    string.  Currently only one will be set and the others will all be
    None or an empty list.
  """
  if EvalPredicate(
      cnxn, services, predicate_ast, issue, label_set, config,
      issue.owner_id, issue.cc_ids, issue.status):
    logging.info('rule adds: %r', rule_pb.add_labels)
    return (rule_pb.default_owner_id, rule_pb.default_status,
            rule_pb.add_cc_ids, rule_pb.add_labels,
            rule_pb.add_notify_addrs, rule_pb.warning, rule_pb.error)
  else:
    return None, None, [], [], [], None, None


def _ApplyCond(
    cnxn, services, project, term, issue, label_set, config, owner_id, cc_ids,
    status):
  """Return True if the given issue satisfied the given predicate term."""
  op = term.op
  vals = term.str_values or term.int_values
  # Since rules are per-project, there'll be exactly 1 field
  fd = term.field_defs[0]
  field = fd.field_name

  if field == 'label':
    return _Compare(op, vals, label_set)
  if field == 'component':
    return _CompareComponents(config, op, vals, issue.component_ids)
  if field == 'any_field':
    return _Compare(op, vals, label_set) or _Compare(op, vals, [issue.summary])
  if field == 'attachments':
    return _Compare(op, term.int_values, [issue.attachment_count])
  if field == 'blocked':
    return _Compare(op, vals, issue.blocked_on_iids)
  if field == 'blockedon':
    return _CompareIssueRefs(
        cnxn, services, project, op, term.str_values, issue.blocked_on_iids)
  if field == 'blocking':
    return _CompareIssueRefs(
        cnxn, services, project, op, term.str_values, issue.blocking_iids)
  if field == 'cc':
    return _CompareUsers(cnxn, services.user, op, vals, cc_ids)
  if field == 'closed':
    return (issue.closed_timestamp and
            _Compare(op, vals, [issue.closed_timestamp]))
  if field == 'id':
    return _Compare(op, vals, [issue.local_id])
  if field == 'mergedinto':
    return _CompareIssueRefs(
        cnxn, services, project, op, term.str_values, [issue.merged_into or 0])
  if field == 'modified':
    return (issue.modified_timestamp and
            _Compare(op, vals, [issue.modified_timestamp]))
  if field == 'open':
    # TODO(jrobbins): this just checks the explicit status, not the result
    # of any previous rules.
    return tracker_helpers.MeansOpenInProject(status, config)
  if field == 'opened':
    return (issue.opened_timestamp and
            _Compare(op, vals, [issue.opened_timestamp]))
  if field == 'owner':
    return _CompareUsers(cnxn, services.user, op, vals, [owner_id])
  if field == 'reporter':
    return _CompareUsers(cnxn, services.user, op, vals, [issue.reporter_id])
  if field == 'stars':
    return _Compare(op, term.int_values, [issue.star_count])
  if field == 'status':
    return _Compare(op, vals, [status.lower()])
  if field == 'summary':
    return _Compare(op, vals, [issue.summary])

  # Since rules are per-project, it makes no sense to support field project.
  # We would need to load comments to support fields comment, commentby,
  # description, attachment.
  # Supporting starredby is probably not worth the complexity.

  logging.info('Rule with unsupported field %r was False', field)
  return False


def _CheckTrivialCases(op, issue_values):
  """Check has:x and -has:x terms and no values.  Otherwise, return None."""
  # We can do these operators without looking up anything or even knowing
  # which field is being checked.
  issue_values_exist = bool(
      issue_values and issue_values != [''] and issue_values != [0])
  if op == ast_pb2.QueryOp.IS_DEFINED:
    return issue_values_exist
  elif op == ast_pb2.QueryOp.IS_NOT_DEFINED:
    return not issue_values_exist
  elif not issue_values_exist:
    # No other operator can match empty values.
    return op in (ast_pb2.QueryOp.NE, ast_pb2.QueryOp.NOT_TEXT_HAS)

  return None  # Caller should continue processing the term.

def _CompareComponents(config, op, rule_values, issue_values):
  """Compare the components specified in the rule vs those in the issue."""
  trivial_result = _CheckTrivialCases(op, issue_values)
  if trivial_result is not None:
    return trivial_result

  exact = op in (ast_pb2.QueryOp.EQ, ast_pb2.QueryOp.NE)
  rule_component_ids = set()
  for path in rule_values:
    rule_component_ids.update(tracker_bizobj.FindMatchingComponentIDs(
        path, config, exact=exact))

  if op == ast_pb2.QueryOp.TEXT_HAS or op == ast_pb2.QueryOp.EQ:
    return any(rv in issue_values for rv in rule_component_ids)
  elif op == ast_pb2.QueryOp.NOT_TEXT_HAS or op == ast_pb2.QueryOp.NE:
    return all(rv not in issue_values for rv in rule_component_ids)

  return False


def _CompareIssueRefs(
  cnxn, services, project, op, rule_str_values, issue_values):
  """Compare the issues specified in the rule vs referenced in the issue."""
  trivial_result = _CheckTrivialCases(op, issue_values)
  if trivial_result is not None:
    return trivial_result

  rule_refs = []
  for str_val in rule_str_values:
    ref = tracker_bizobj.ParseIssueRef(str_val)
    if ref:
      rule_refs.append(ref)
  rule_ref_project_names = set(
      pn for pn, local_id in rule_refs if pn)
  rule_ref_projects_dict = services.project.GetProjectsByName(
      cnxn, rule_ref_project_names)
  rule_ref_projects_dict[project.project_name] = project
  rule_iids, _misses = services.issue.ResolveIssueRefs(
      cnxn, rule_ref_projects_dict, project.project_name, rule_refs)

  if op == ast_pb2.QueryOp.TEXT_HAS:
    op = ast_pb2.QueryOp.EQ
  if op == ast_pb2.QueryOp.NOT_TEXT_HAS:
    op = ast_pb2.QueryOp.NE

  return _Compare(op, rule_iids, issue_values)


def _CompareUsers(cnxn, user_service, op, rule_values, issue_values):
  """Compare the user(s) specified in the rule and the issue."""
  # Note that all occurances of "me" in rule_values should have already
  # been resolved to str(user_id) of the subscribing user.
  # TODO(jrobbins): Project filter rules should not be allowed to have "me".

  trivial_result = _CheckTrivialCases(op, issue_values)
  if trivial_result is not None:
    return trivial_result

  try:
    return _CompareUserIDs(op, rule_values, issue_values)
  except ValueError:
    return _CompareEmails(cnxn, user_service, op, rule_values, issue_values)


def _CompareUserIDs(op, rule_values, issue_values):
  """Compare users according to specified user ID integer strings."""
  rule_user_ids = [int(uid_str) for uid_str in rule_values]

  if op == ast_pb2.QueryOp.TEXT_HAS or op == ast_pb2.QueryOp.EQ:
    return any(rv in issue_values for rv in rule_user_ids)
  elif op == ast_pb2.QueryOp.NOT_TEXT_HAS or op == ast_pb2.QueryOp.NE:
    return all(rv not in issue_values for rv in rule_user_ids)

  logging.info('unexpected numeric user operator %r %r %r',
               op, rule_values, issue_values)
  return False


def _CompareEmails(cnxn, user_service, op, rule_values, issue_values):
  """Compare users based on email addresses."""
  issue_emails = user_service.LookupUserEmails(cnxn, issue_values).values()

  if op == ast_pb2.QueryOp.TEXT_HAS:
    return any(_HasText(rv, issue_emails) for rv in rule_values)
  elif op == ast_pb2.QueryOp.NOT_TEXT_HAS:
    return all(not _HasText(rv, issue_emails) for rv in rule_values)
  elif op == ast_pb2.QueryOp.EQ:
    return any(rv in issue_emails for rv in rule_values)
  elif op == ast_pb2.QueryOp.NE:
    return all(rv not in issue_emails for rv in rule_values)

  logging.info('unexpected user operator %r %r %r',
               op, rule_values, issue_values)
  return False


def _Compare(op, rule_values, issue_values):
  """Compare the values specified in the rule and the issue."""
  trivial_result = _CheckTrivialCases(op, issue_values)
  if trivial_result is not None:
    return trivial_result

  if (op in [ast_pb2.QueryOp.TEXT_HAS, ast_pb2.QueryOp.NOT_TEXT_HAS] and
      issue_values and not isinstance(min(issue_values), basestring)):
    return False  # Empty or numeric fields cannot match substrings
  elif op == ast_pb2.QueryOp.TEXT_HAS:
    return any(_HasText(rv, issue_values) for rv in rule_values)
  elif op == ast_pb2.QueryOp.NOT_TEXT_HAS:
    return all(not _HasText(rv, issue_values) for rv in rule_values)

  val_type = type(min(issue_values))
  if val_type == int or val_type == long:
    try:
      rule_values = [int(rv) for rv in rule_values]
    except ValueError:
      logging.info('rule value conversion to int failed: %r', rule_values)
      return False

  if op == ast_pb2.QueryOp.EQ:
    return any(rv in issue_values for rv in rule_values)
  elif op == ast_pb2.QueryOp.NE:
    return all(rv not in issue_values for rv in rule_values)

  if val_type != int and val_type != long:
    return False  # Inequalities only work on numeric fields

  if op == ast_pb2.QueryOp.GT:
    return min(issue_values) > min(rule_values)
  elif op == ast_pb2.QueryOp.GE:
    return min(issue_values) >= min(rule_values)
  elif op == ast_pb2.QueryOp.LT:
    return max(issue_values) < max(rule_values)
  elif op == ast_pb2.QueryOp.LE:
    return max(issue_values) <= max(rule_values)

  logging.info('unexpected operator %r %r %r', op, rule_values, issue_values)
  return False


def _HasText(rule_text, issue_values):
  """Return True if the issue contains the rule text, case insensitive."""
  rule_lower = rule_text.lower()
  for iv in issue_values:
    if iv is not None and rule_lower in iv.lower():
      return True

  return False


def MakeRule(
    predicate, default_status=None, default_owner_id=None, add_cc_ids=None,
    add_labels=None, add_notify=None, warning=None, error=None):
  """Make a FilterRule PB with the supplied information.

  Args:
    predicate: string query that will trigger the rule if satisfied.
    default_status: optional default status to set if rule fires.
    default_owner_id: optional default owner_id to set if rule fires.
    add_cc_ids: optional cc ids to set if rule fires.
    add_labels: optional label strings to set if rule fires.
    add_notify: optional notify email addresses to set if rule fires.
    warning: optional string for a software development process warning.
    error: optional string for a software development process error.

  Returns:
    A new FilterRule PB.
  """
  rule_pb = tracker_pb2.FilterRule()
  rule_pb.predicate = predicate

  if add_labels:
    rule_pb.add_labels = add_labels
  if default_status:
    rule_pb.default_status = default_status
  if default_owner_id:
    rule_pb.default_owner_id = default_owner_id
  if add_cc_ids:
    rule_pb.add_cc_ids = add_cc_ids
  if add_notify:
    rule_pb.add_notify_addrs = add_notify
  if warning:
    rule_pb.warning = warning
  if error:
    rule_pb.error = error

  return rule_pb


def ParseRules(cnxn, post_data, user_service, errors, prefix=''):
  """Parse rules from the user and return a list of FilterRule PBs.

  Args:
    cnxn: connection to database.
    post_data: dictionary of html form data.
    user_service: connection to user backend services.
    errors: EZTErrors message used to display field validation errors.
    prefix: optional string prefix used to differentiate the form fields
      for existing rules from the form fields for new rules.

  Returns:
    A list of FilterRule PBs
  """
  rules = []

  # The best we can do for now is show all validation errors at the bottom of
  # the filter rules section, not directly on the rule that had the error :(.
  error_list = []

  for i in xrange(1, MAX_RULES + 1):
    if ('%spredicate%s' % (prefix, i)) not in post_data:
      continue  # skip any entries that are blank or have no predicate.
    predicate = post_data['%spredicate%s' % (prefix, i)].strip()
    action_type = post_data.get('%saction_type%s' % (prefix, i),
                                'add_labels').strip()
    action_value = post_data.get('%saction_value%s' % (prefix, i),
                                 '').strip()
    if predicate:
      # Note: action_value may be '', meaning no-op.
      rules.append(_ParseOneRule(
          cnxn, predicate, action_type, action_value, user_service, i,
          error_list))

  if error_list:
    errors.rules = error_list

  return rules


def _ParseOneRule(
    cnxn, predicate, action_type, action_value, user_service,
    rule_num, error_list):
  """Parse one FilterRule based on the action type."""

  if action_type == 'default_status':
    status = framework_bizobj.CanonicalizeLabel(action_value)
    rule = MakeRule(predicate, default_status=status)

  elif action_type == 'default_owner':
    if action_value:
      try:
        user_id = user_service.LookupUserID(cnxn, action_value)
      except user_svc.NoSuchUserException:
        user_id = framework_constants.NO_USER_SPECIFIED
        error_list.append(
            'Rule %d: No such user: %s' % (rule_num, action_value))
    else:
      user_id = framework_constants.NO_USER_SPECIFIED
    rule = MakeRule(predicate, default_owner_id=user_id)

  elif action_type == 'add_ccs':
    cc_ids = []
    for email in re.split('[,;\s]+', action_value):
      if not email.strip():
        continue
      try:
        user_id = user_service.LookupUserID(
            cnxn, email.strip(), autocreate=True)
        cc_ids.append(user_id)
      except user_svc.NoSuchUserException:
        error_list.append(
            'Rule %d: No such user: %s' % (rule_num, email.strip()))

    rule = MakeRule(predicate, add_cc_ids=cc_ids)

  elif action_type == 'add_labels':
    add_labels = framework_constants.IDENTIFIER_RE.findall(action_value)
    rule = MakeRule(predicate, add_labels=add_labels)

  elif action_type == 'also_notify':
    add_notify = []
    for addr in re.split('[,;\s]+', action_value):
      if validate.IsValidEmail(addr.strip()):
        add_notify.append(addr.strip())
      else:
        error_list.append(
            'Rule %d: Invalid email address: %s' % (rule_num, addr.strip()))

    rule = MakeRule(predicate, add_notify=add_notify)

  elif action_type == 'warning':
    rule = MakeRule(predicate, warning=action_value)

  elif action_type == 'error':
    rule = MakeRule(predicate, error=action_value)

  else:
    logging.info('unexpected action type, probably tampering:%r', action_type)
    raise exceptions.InputException()

  return rule
