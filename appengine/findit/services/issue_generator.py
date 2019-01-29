# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utilities to generate content of bugs to be logged."""
import abc
import textwrap

from google.appengine.ext import ndb

from gae_libs.appengine_util import IsStaging
from model import entity_util
from model.flake.flake import Flake
from model.flake.flake_issue import FlakeIssue
from monorail_api import CustomizedField
from services import build_url
from services import git
from services import issue_constants
from services import monitoring
from services import swarming

# TODO(crbug.com/902408): Once underlying data models for Flake, FlakeIssue,
# MasterFlakeAnalysis, etc. are updated to associate with each other for bug
# deduplication on a 1-bug-per-culprit level, FlakyTestIssueGenerator,
# FlakeAnalysisIssueGenerator, and FlakeDetectionIssueGenerator should all be
# merged into a single bug-filing entry point capable of handling the various
# bug updates.

# The link to the flake culprit page to encapsulate all impacted analyses by
# a common culprit.
_CULPRIT_LINK_TEMPLATE = (
    'https://findit-for-me.appspot.com/waterfall/flake/flake-culprit?key={}')

# The base template for updating a bug with culprit findings.
_RESULT_WITH_CULPRIT_TEMPLATE = textwrap.dedent("""
Findit identified the culprit r{commit_position} as introducing flaky test(s)
summarized in {culprit_link}

Please revert the culprit or disable the test(s) asap. If you are the owner,
please fix!

If the culprit above is wrong, please file a bug using this link:
{wrong_result_link}

Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N).""")

# The link to include with bug updates about wrong findings for users to
# report.
_WRONG_CULPRIT_LINK_TEMPLATE = (
    'https://bugs.chromium.org/p/chromium/issues/entry?'
    'status=Unconfirmed&'
    'labels=Pri-1,Test-Findit-Wrong&'
    'components=Tools%3ETest%3EFindit%3EFlakiness&'
    'summary=%5BFindit%5D%20Flake%20Analyzer%20-%20Wrong%20culprit%20'
    'r{commit_position}&comment=Link%20to%20Culprit%3A%20{culprit_link}')

# The base template for completed analyses without findings. Currently not yet
# used as analyses without findings don't update bugs.
# TODO(crbug.com/902408): Still update bugs when there are no findings so
# sheriffs or developers can disable or delete tests at their discretion.
_UNKNOWN_CULPRIT_TEMPLATE = textwrap.dedent("""
Flaky test: {test_name}
Sample failed build due to flakiness: {build_link}
Test output log: {test_output_log_link}
Analysis: {analysis_link}

This flake is either longstanding, has low flakiness, or is not reproducible.

Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N).""")

# Flake detection bug templates.
_FLAKE_DETECTION_BUG_DESCRIPTION = textwrap.dedent("""
{test_name} is flaky.

Findit has detected {num_occurrences} flake occurrences of this test within the
past 24 hours. List of all flake occurrences can be found at:
{flake_url}.

Unless the culprit CL is found and reverted, please disable this test first
within 30 minutes then find an appropriate owner.
{previous_tracking_bug_text}
{footer}""")

# The base template for a detected flaky test before analysis.
_FLAKE_DETECTION_BUG_COMMENT = textwrap.dedent("""
{test_name} is flaky.

Findit has detected {num_occurrences} new flake occurrences of this test. List
of all flake occurrences can be found at:
{flake_url}.

{back_onto_sheriff_queue_message}
{previous_tracking_bug_text}
{footer}""")

_FLAKE_DETECTION_WRONG_RESULTS_BUG_LINK = (
    'https://bugs.chromium.org/p/chromium/issues/entry?'
    'status=Unconfirmed&labels=Pri-1,Test-Findit-Wrong&'
    'components=Tools%3ETest%3EFindit%3EFlakiness&'
    'summary=%5BFindit%5D%20Flake%20Detection%20-%20Wrong%20result%3A%20'
    '{summary}&comment=Link%20to%20flake%20details%3A%20{flake_link}')

_FLAKE_DETECTION_PREVIOUS_TRACKING_BUG = (
    '\nThis flaky test was previously tracked in bug {}.\n')

_FLAKE_DETECTION_FOOTER_TEMPLATE = textwrap.dedent(
    """If the result above is wrong, please file a bug using this link:
{wrong_results_bug_link}

Automatically posted by the findit-for-me app (https://goo.gl/Ot9f7N).""")

############### Below are bug templates for flake groups. ###############
# Bug template for a group of detected flakes.
_FLAKE_DETECTION_GROUP_BUG_DESCRIPTION = textwrap.dedent("""
Tests in {canonical_step_name} is flaky.

Findit has detected {num_occurrences} flake occurrences of tests below within
the past 24 hours:

{flake_list}

Please try to find and revert the culprit if the culprit is obvious.
Otherwise please find an appropriate owner.
{previous_tracking_bug_text}
""")

# Template for the comment immediately after the bug is created.
_FLAKE_DETECTION_GROUP_BUG_LINK_COMMENT = textwrap.dedent("""
List of all flake occurrences can be found at:
{flakes_url}.

{footer}""")

_BACK_ONTO_SHERIFF_QUEUE_MESSAGE = (
    'Since these tests are still flaky, this issue has been moved back onto the'
    ' Sheriff Bug Queue if it hasn\'t already.')

_FLAKE_DETECTION_GROUP_BUG_COMMENT = textwrap.dedent("""
Findit has detected {num_occurrences} new flake occurrences of tests in this bug
within the past 24 hours.

List of all flake occurrences can be found at:
{flake_url}.

{back_onto_sheriff_queue_message}
{previous_tracking_bug_text}
{footer}""")


def _GenerateAnalysisLink(analysis):
  """Returns a link to Findit's result page of a MasterFlakeAnalysis."""
  return 'https://findit-for-me.appspot.com/waterfall/flake?key={}'.format(
      analysis.key.urlsafe())


def _GenerateCulpritLink(culprit_urlsafe_key):
  """Returns a link to a FlakeCulprit page."""
  return _CULPRIT_LINK_TEMPLATE.format(culprit_urlsafe_key)


def _GenerateWrongCulpritLink(culprit):
  """Returns the test with a link to file a bug agasinst a wrong result."""
  return _WRONG_CULPRIT_LINK_TEMPLATE.format(
      commit_position=culprit.commit_position,
      culprit_link=_GenerateCulpritLink(culprit.key.urlsafe()))


def _GenerateTestOutputLogLink(analysis):
  """Generates a link to the swarming task to be surfaced to the bug.

  Args:
    analysis (MasterFlakeAnalysis): The analysis whose data points and swarming
        tasks will be queried for surfacing to the bug.

  Returns:
    url (str): The url to the swarming task.
  """
  task_id = analysis.GetRepresentativeSwarmingTaskId()
  assert task_id, 'Representative task id unexpectedly not found!'

  return swarming.GetSwarmingTaskUrl(task_id)


def _GenerateMessageText(analysis):
  """Generates the text to create or update a bug with depending on results.

  Args:
    analysis (MasterFlakeAnalysis): The completed analysis with results to
      determine what to update the bug with.

  Returns:
    (str): The text to upodate the bug with.
  """
  # Culprit identified.
  if analysis.culprit_urlsafe_key:
    culprit = ndb.Key(urlsafe=analysis.culprit_urlsafe_key).get()
    assert culprit, 'Culprit is unexpectedly missing.'

    culprit_link = _GenerateCulpritLink(analysis.culprit_urlsafe_key)
    wrong_result_link = _GenerateWrongCulpritLink(culprit)

    return _RESULT_WITH_CULPRIT_TEMPLATE.format(
        commit_position=culprit.commit_position,
        culprit_link=culprit_link,
        wrong_result_link=wrong_result_link)

  # Culprit not identified.
  analysis_link = _GenerateAnalysisLink(analysis)

  build_link = build_url.CreateBuildUrl(analysis.original_master_name,
                                        analysis.original_builder_name,
                                        analysis.original_build_number)
  test_output_log_link = _GenerateTestOutputLogLink(analysis)
  return _UNKNOWN_CULPRIT_TEMPLATE.format(
      test_name=analysis.original_test_name,
      build_link=build_link,
      test_output_log_link=test_output_log_link,
      analysis_link=analysis_link)


def _GetAutoAssignOwner(analysis):
  """Determines the best owner for the culprit of an analysis.

    Rules for determining an owner:
    1. None if no culprit.
    2. Return the culprit CL author if @chromium.org or @google.com
    3. TODO(crbug.com913032): Fallback to the reviewer(s) and check for
       @chromium.org or @google.com.

  Args:
    analysis (MasterFlakeAnalysis): The analysis for whose results are to be
      used to update the bug with.

  Returns:
    owner (str): The best-guess owner or None if not determined.
  """
  if not analysis.culprit_urlsafe_key:
    # No culprit, so no owner.
    return None

  culprit = entity_util.GetEntityFromUrlsafeKey(analysis.culprit_urlsafe_key)
  assert culprit, (
      'Culprit missing unexpectedly when trying to get owner for bug!')

  author = git.GetAuthor(culprit.revision)

  if not author:
    return None

  email = author.email
  if email.endswith('@chromium.org') or email.endswith('@google.com'):
    return email

  return None


def GenerateDuplicateComment(commit_position):
  return 'This flake has been identified as being introduced in r{}'.format(
      commit_position)


class BaseFlakeIssueGenerator(object):
  """Encapsulates details needed to create or update a Monorail issue."""
  __metaclass__ = abc.ABCMeta

  def __init__(self):
    """Initiates a BaseFlakeIssueGenerator object."""

    # Id of the previous issue that was tracking this flaky test.
    self._previous_tracking_bug_id = None

  @abc.abstractmethod
  def GetDescription(self):
    """Gets description for the issue to be created.

    Returns:
      A string representing the description.
    """
    return

  @abc.abstractmethod
  def GetComment(self):
    """Gets a comment to post an update to the issue.

    Returns:
      A string representing the comment.
    """
    return

  @abc.abstractmethod
  def ShouldRestoreChromiumSheriffLabel(self):
    """Returns True if the Sheriff label should be restored when updating bugs.

    This value should be set based on whether the results of the service are
    actionable. For example, for Flake Detection, once it detects new
    occurrences of a flaky test, it is immediately actionable that Sheriffs
    should disable the test ASAP. However, for Flake Analyzer, when the
    confidence is low, the analysis results mostly only serve as FYI
    information, so it would be too noisy to notify Sheriffs on every bug.

    Returns:
      A boolean indicates whether the Sheriff label should be restored.
    """
    return

  @abc.abstractmethod
  def GetLabels(self):
    """Gets labels for the issue to be created.

    Returns:
      A list of string representing the labels.
    """
    return

  def _GetCommonFlakyTestLabel(self):
    """Returns a list of comment labels used for flaky tests related issues.

    Args:
      A list of string representing the labels.
    """
    return [
        issue_constants.SHERIFF_CHROMIUM_LABEL, issue_constants.TYPE_BUG_LABEL,
        issue_constants.FLAKY_TEST_LABEL
    ]

  def GetAutoAssignOwner(self):
    """Gets the owner to assign the issue to.

      Can be None, in which case the owner field should not be affected.
    """
    return None

  def GetStatus(self):
    """Gets status for the issue to be created.

    Returns:
      A string representing the status, for example: Untriaged.
    """
    return 'Untriaged'

  @abc.abstractmethod
  def GetSummary(self):
    """Gets summary for the issue to be created.

    Returns:
      A string representing the summary.
    """
    return

  @abc.abstractmethod
  def GetFlakyTestCustomizedField(self):
    """Gets customized fields for the issue to be created.

    Returns:
      A CustomizedField field.
    """
    return

  def GetPriority(self):
    """Gets priority for the issue to be created.

    Defaults to P1 for all flaky tests related bugs.

    Returns:
      A string representing the priority of the issue. (e.g Pri-1, Pri-2)
    """
    return 'Pri-1'

  def GetMonorailProject(self):
    """Gets the name of the Monorail project the issue is for.

    Returns:
      A string representing the Monorail project.
    """
    return 'chromium'

  def GetPreviousTrackingBugId(self):
    """Gets the id of the previous issue that was tracking this flaky test.

    Returns:
      A string representing the Id of the issue.
    """
    return self._previous_tracking_bug_id

  def SetPreviousTrackingBugId(self, previous_tracking_bug_id):
    """Sets the id of the previous issue that was tracking this flaky test.

    Args:
      previous_tracking_bug_id: Id of the issue that was tracking this test.
    """
    self._previous_tracking_bug_id = previous_tracking_bug_id

  def OnIssueCreated(self):
    """Called when an issue was created successfully."""
    return

  def OnIssueUpdated(self):
    """Called when an issue was updated successfully."""
    return


class FlakyTestIssueGenerator(BaseFlakeIssueGenerator):
  """Encapsulates details needed to create or update a Monorail issue."""
  __metaclass__ = abc.ABCMeta

  @abc.abstractmethod
  def GetStepName(self):
    """Gets the name of the step to create or update issue for.

    Returns:
      A String representing the step name.
    """
    return

  @abc.abstractmethod
  def GetTestName(self):
    """Gets a name that can be used to identify a flaky test.

    Returns:
      A string representing the test name.
    """
    return

  @abc.abstractmethod
  def GetTestLabelName(self):
    """Gets a label of the test that is used for display purpose.

    Returns:
      A label for the flaky test.
    """
    return

  def GetSummary(self):
    """Gets summary for the issue to be created.

    Returns:
      A string representing the summary.
    """
    return '%s is flaky' % self.GetTestLabelName()

  def GetFlakyTestCustomizedField(self):
    """Gets Flaky-Test customized fields for the issue to be created.

    Returns:
      A CustomizedField field whose value is the test name.
    """
    return CustomizedField(issue_constants.FLAKY_TEST_CUSTOMIZED_FIELD,
                           self.GetTestName())


class FlakeAnalysisIssueGenerator(FlakyTestIssueGenerator):
  """Encapsulates the details of issues filed by Flake Analyzer."""

  def __init__(self, analysis):
    super(FlakeAnalysisIssueGenerator, self).__init__()
    self._analysis = analysis

  def GetAutoAssignOwner(self):
    return _GetAutoAssignOwner(self._analysis)

  def GetStepName(self):
    return Flake.NormalizeStepName(
        step_name=self._analysis.step_name,
        master_name=self._analysis.master_name,
        builder_name=self._analysis.builder_name,
        build_number=self._analysis.build_number)

  def GetTestName(self):
    return Flake.NormalizeTestName(self._analysis.test_name,
                                   self._analysis.step_name)

  def GetTestLabelName(self):
    # Issues are filed with the test label name.
    return Flake.GetTestLabelName(self._analysis.test_name,
                                  self._analysis.step_name)

  def GetMonorailProject(self):
    # Currently, flake analysis only works on Chromium project.
    return 'chromium'

  def GetDescription(self):
    return _GenerateMessageText(self._analysis)

  def GetComment(self):
    return _GenerateMessageText(self._analysis)

  def ShouldRestoreChromiumSheriffLabel(self):
    # Analysis results are not always immediately actionable, so don't restore
    # Sheriff label to avoid being too noisy.
    return False

  def GetLabels(self):
    priority = self.GetPriority()
    flaky_test_labels = self._GetCommonFlakyTestLabel()
    flaky_test_labels.append(priority)
    flaky_test_labels.append(issue_constants.FINDIT_ANALYZED_LABEL_TEXT)
    return flaky_test_labels

  def OnIssueCreated(self):
    monitoring.OnIssueChange('created', 'flake')

  def OnIssueUpdated(self):
    monitoring.OnIssueChange('update', 'flake')


class FlakeDetectionIssueGenerator(FlakyTestIssueGenerator):
  """Encapsulates the details of issues filed by Flake Detection."""

  def __init__(self, flake, num_occurrences):
    super(FlakeDetectionIssueGenerator, self).__init__()
    self._flake = flake
    self._num_occurrences = num_occurrences

  def GetStepName(self):
    return self._flake.canonical_step_name

  def GetTestName(self):
    return self._flake.normalized_test_name

  def GetTestLabelName(self):
    return self._flake.test_label_name

  def GetMonorailProject(self):
    return FlakeIssue.GetMonorailProjectFromLuciProject(
        self._flake.luci_project)

  def GetDescription(self):
    previous_tracking_bug_id = self.GetPreviousTrackingBugId()
    previous_tracking_bug_text = _FLAKE_DETECTION_PREVIOUS_TRACKING_BUG.format(
        previous_tracking_bug_id) if previous_tracking_bug_id else ''
    description = _FLAKE_DETECTION_BUG_DESCRIPTION.format(
        test_name=self._flake.test_label_name,
        num_occurrences=self._num_occurrences,
        flake_url=self._GetLinkForFlake(),
        previous_tracking_bug_text=previous_tracking_bug_text,
        footer=self._GetFooter())

    return description

  def GetComment(self):
    previous_tracking_bug_id = self.GetPreviousTrackingBugId()
    previous_tracking_bug_text = _FLAKE_DETECTION_PREVIOUS_TRACKING_BUG.format(
        previous_tracking_bug_id) if previous_tracking_bug_id else ''

    comment = _FLAKE_DETECTION_BUG_COMMENT.format(
        test_name=self._flake.test_label_name,
        num_occurrences=self._num_occurrences,
        flake_url=self._GetLinkForFlake(),
        back_onto_sheriff_queue_message=_BACK_ONTO_SHERIFF_QUEUE_MESSAGE,
        previous_tracking_bug_text=previous_tracking_bug_text,
        footer=self._GetFooter())

    return comment

  def ShouldRestoreChromiumSheriffLabel(self):
    # Flake Detection always requires Chromium Sheriff's attentions to disable
    # flaky tests when new occurrences are detected.
    return True

  def GetLabels(self):
    flaky_test_labels = self._GetCommonFlakyTestLabel()
    flaky_test_labels.append(issue_constants.FLAKE_DETECTION_LABEL_TEXT)
    return flaky_test_labels

  def OnIssueCreated(self):
    monitoring.OnFlakeDetectionCreateOrUpdateIssues('create')

  def OnIssueUpdated(self):
    monitoring.OnFlakeDetectionCreateOrUpdateIssues('updated')

  def _GetLinkForFlake(self):
    """Given a flake, gets a link to the flake on flake detection UI.

    Returns:
      A link to the flake on flake detection UI.
    """
    url_template = (
        'https://findit-for-me%s.appspot.com/flake/occurrences?key=%s')
    suffix = '-staging' if IsStaging() else ''
    return url_template % (suffix, self._flake.key.urlsafe())

  def _GetFooter(self):
    """Gets the footer for the bug description of comment.

    Returns:
      A string representing footer.
    """
    wrong_results_bug_link = _FLAKE_DETECTION_WRONG_RESULTS_BUG_LINK.format(
        summary=self._flake.normalized_test_name,
        flake_link=self._GetLinkForFlake())
    return _FLAKE_DETECTION_FOOTER_TEMPLATE.format(
        wrong_results_bug_link=wrong_results_bug_link)


class FlakeDetectionGroupIssueGenerator(BaseFlakeIssueGenerator):
  """Encapsulates the details of issues filed by Flake Detection for a flake
    group.

  This issue_generator can be used for 2 cases:
    1. A group of new flakes are detected, and we want to create a bug for this
      group. In this case, by our heuristic rules, all flakes are in the same
      binary name and test suite, and all happen in the same builds (meaning
      they have the same occurrence_count).
    2. A group of old flakes are still happening so we want to update their bug.
      In this case, all our heuristic rules may not apply since other flakes may
      be merged together to one bug automatically or manually.
  """

  def __init__(self,
               flakes,
               num_occurrences,
               canonical_step_name=None,
               flake_issue=None,
               flakes_with_same_occurrences=True):
    """
    Args:
      flakes (list): a list of Flake entities in the same group for one bug.
      num_occurrences (int): Number of occurrence for each flake.
        1. If create a bug for a group, by heuristic rule the occurrence should
          be the same for all flakes.
        2. If updating a bug, numbers might be different, in that case we will
          use the smallest number(but still qualified to update the bug) of
          occurrences within the group.
      canonical_step_name (str): The flakes in a group should be in the same
        step name.
      flake_issue (FlakeIssue): The FlakeIssue entity for the shared bug of the
        group.
      flakes_with_same_occurrences (bool): Flag for if flakes in the group have
        the same occurrences count. Bug comment should be adjusted based on the
        value of this flag.
    """
    super(FlakeDetectionGroupIssueGenerator, self).__init__()
    self._flakes = flakes
    self._num_occurrences = num_occurrences
    self._canonical_step_name = canonical_step_name
    self._flake_issue = flake_issue
    self._flakes_with_same_occurrences = flakes_with_same_occurrences

  def _GenerateFlakeList(self):
    return '\n'.join([flake.test_label_name for flake in self._flakes])

  def _GetNumOccurrences(self):
    """Returns processed num occurrences.

    If self._flakes_with_same_occurrences, we can simply use the
      self._num_occurrences; otherwise self._num_occurrences should be the
      smallest count within the group.
    """
    return (self._num_occurrences if self._flakes_with_same_occurrences else
            '%d+' % self._num_occurrences)

  def _GetLinkForFlakes(self):
    """Given a FlakeIssue, gets a link to all the flake linked to the bug on
      flake detection UI.
    """
    assert self._flake_issue, (
        'FlakeIssue required to generate a comment on a group bug.')
    url_template = (
        'https://findit-for-me%s.appspot.com/ranked-flakes?bug_id=%d')
    if self._flake_issue.monorail_project != 'chromium':
      url_template = '{}&monorail_project={}'.format(
          url_template, self._flake_issue.monorail_project)
    suffix = '-staging' if IsStaging() else ''
    return url_template % (suffix, self._flake_issue.issue_id)

  def _GetIssueSummaryForWrongResultLink(self):
    if self._canonical_step_name:
      return 'Tests in {}'.format(self._canonical_step_name)
    return self._flake_issue.issue_id if self._flake_issue else None

  def _GetFooter(self):
    """Gets the footer for the bug description of comment.

    Returns:
      A string representing footer.
    """
    wrong_results_bug_link = _FLAKE_DETECTION_WRONG_RESULTS_BUG_LINK.format(
        summary=self._GetIssueSummaryForWrongResultLink(),
        flake_link=self._GetLinkForFlakes())
    return _FLAKE_DETECTION_FOOTER_TEMPLATE.format(
        wrong_results_bug_link=wrong_results_bug_link)

  def GetMonorailProject(self):
    return FlakeIssue.GetMonorailProjectFromLuciProject(
        self._flakes[0].luci_project)

  def GetSummary(self):
    return 'Flakes are found in {canonical_step_name}.'.format(
        canonical_step_name=self._canonical_step_name)

  def GetDescription(self):
    previous_tracking_bug_id = self.GetPreviousTrackingBugId()
    previous_tracking_bug_text = _FLAKE_DETECTION_PREVIOUS_TRACKING_BUG.format(
        previous_tracking_bug_id) if previous_tracking_bug_id else ''
    return _FLAKE_DETECTION_GROUP_BUG_DESCRIPTION.format(
        canonical_step_name=self._canonical_step_name,
        num_occurrences=self._GetNumOccurrences(),
        flake_list=self._GenerateFlakeList(),
        previous_tracking_bug_text=previous_tracking_bug_text)

  def GetFirstCommentWhenBugJustCreated(self):
    """Generates the first comment we'll post to the newly created bug.

    In order to provide a url to grouped flakes, an issue id is needed to query
    for Flakes with FlakeIssues with that same id which is unavailable at bug
    creation time.
    """
    return _FLAKE_DETECTION_GROUP_BUG_LINK_COMMENT.format(
        flakes_url=self._GetLinkForFlakes(), footer=self._GetFooter())

  def GetComment(self):
    previous_tracking_bug_id = self.GetPreviousTrackingBugId()
    previous_tracking_bug_text = _FLAKE_DETECTION_PREVIOUS_TRACKING_BUG.format(
        previous_tracking_bug_id) if previous_tracking_bug_id else ''

    return _FLAKE_DETECTION_GROUP_BUG_COMMENT.format(
        num_occurrences=self._GetNumOccurrences(),
        flake_url=self._GetLinkForFlakes(),
        back_onto_sheriff_queue_message=_BACK_ONTO_SHERIFF_QUEUE_MESSAGE,
        previous_tracking_bug_text=previous_tracking_bug_text,
        footer=self._GetFooter())

  def GetFlakyTestCustomizedField(self):
    return None

  def SetFlakeIssue(self, flake_issue):
    """Sets flake_issue for the group when the bug has been created."""
    self._flake_issue = flake_issue

  def ShouldRestoreChromiumSheriffLabel(self):
    # Flake Detection always requires Chromium Sheriff's attentions to disable
    # flaky tests when new occurrences are detected.
    return True

  def GetLabels(self):
    flaky_test_labels = self._GetCommonFlakyTestLabel()
    flaky_test_labels.append(issue_constants.FLAKE_DETECTION_LABEL_TEXT)
    return flaky_test_labels

  def OnIssueCreated(self):
    monitoring.OnFlakeDetectionCreateOrUpdateIssues('create')

  def OnIssueUpdated(self):
    monitoring.OnFlakeDetectionCreateOrUpdateIssues('updated')
