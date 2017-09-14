# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
import itertools
import os
import sys

_ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__),
                                          os.path.pardir))
_FIRST_PARTY_DIR = os.path.join(_ROOT_DIR, 'first_party')
sys.path.insert(1, _FIRST_PARTY_DIR)

from local_libs import script_util

script_util.SetUpSystemPaths(_ROOT_DIR)

from app.common.model import triage_status
from scripts.delta_test import delta_test
from scripts import run_predator


SummaryStats = namedtuple(
    'SummaryStats',
    ['total_examples',
     'true_positives', 'true_negatives', 'false_positives', 'false_negatives',
     'untriaged', 'unsure'])


def RunModelOnTestSet(client_id, app_id, testset_path):  # pragma: no cover
  """Get pairs of (CrashAnalysis, list<Suspect>) for a set of test cases.

  Args:
    client_id (CrashClient enum value): The id of the client doing the analysis
      E.g. if the client is CrashClient.UMA_SAMPLING_PROFILER, get
      UMASamplingProfilerAnalysis entities and determine culprits using
      PredatorForUMASamplingProfiler.
    app_id (str): The id of the App Engine app to retrieve test cases from.
    testset_path (str): Path to the csv file storing the testset - i.e. a list
      of URLs of *Analysis entities. To generate a testset like this, use the
      update-testset.py script.
      # TODO(cweakliam): It would be better if we had triaged datasets saved in
      # the Datastore, and downloaded them from there instead.
  Returns:
    List of (crash, cls) pairs:
      crash (CrashAnalysis subclass): An entity representing one test case,
        usually triaged and labelled with the correct CL if there is one.
      cls (list of Suspect): The suspects produced by Predator.
  """
  crashes = delta_test.ReadCrashesFromCsvTestset(testset_path)
  culprits = run_predator.GetCulpritsOnRevision(crashes, 'HEAD', client_id,
                                                app_id)
  return [
    (crashes[crash_id], culprit.cls)
    for crash_id, culprit in culprits.iteritems()
  ]


def CommitUrlEquals(url1, url2):
  # Some URLs have '.git' in them, some don't
  url1_standardized = url1.replace('.git', '')
  url2_standardized = url2.replace('.git', '')
  return url1_standardized == url2_standardized


def IsTruePositive(correct_cl_url, suspects):
  """Determine if this Predator result is a true positive.

  Args:
    correct_cl_url (str): The URL of the correct CL for this example.
    suspects (list of Suspect): The suspects produced by Predator. Must be
      non-empty.

  An example is considered to be a true positive iff: the correct CL is among
  the suspects identified by Predator, and Predator assigned it a confidence
  value greater than or equal to that of any other suspect.
  """
  max_confidence = max(suspect.confidence for suspect in suspects)
  top_suspect_urls = [suspect.changelog.commit_url
                      for suspect in suspects
                      if suspect.confidence == max_confidence]
  return any(
      CommitUrlEquals(correct_cl_url, suspect_url)
      for suspect_url in top_suspect_urls)


def GradeModel(input_output_pairs):
  """Grade the model's performance on a set of examples.

  Args:
    input_output_pairs (iterable of (CrashAnalysis, list<Suspect>) pairs): A set
     of labelled examples, along with the result produced by Predator for each
     example.
  Returns:
    A SummaryStats object, detailing the result of grading the model (e.g.
      number of True Positives, False Positives etc.).
  """
  true_positives = 0
  true_negatives = 0
  false_positives = 0
  false_negatives = 0
  untriaged = 0
  unsure = 0
  total_examples = 0

  for crash, suspects in input_output_pairs:
    total_examples += 1

    if crash.suspected_cls_triage_status == triage_status.UNTRIAGED:
      untriaged += 1
      continue

    if crash.suspected_cls_triage_status == triage_status.TRIAGED_UNSURE:
      unsure += 1
      continue

    correct_cls = crash.culprit_cls

    if not correct_cls:
      if suspects:
        false_positives += 1
      else:
        true_negatives += 1
      continue

    if not suspects:
      false_negatives += 1
      continue

    # I'm assuming for now that there's only ever going to be one correct CL.
    assert len(correct_cls) == 1
    correct_cl_url = correct_cls[0]

    if IsTruePositive(correct_cl_url, suspects):
      true_positives += 1
    else:
      false_positives += 1

  return SummaryStats(
      total_examples=total_examples,
      true_positives=true_positives,
      true_negatives=true_negatives,
      false_positives=false_positives,
      false_negatives=false_negatives,
      untriaged=untriaged,
      unsure=unsure,
  )


def Percent(a, b):
  """Return the percentage of a wrt. b, or None if b == 0."""
  if b == 0:
    return None
  return (a / float(b)) * 100


# See https://en.wikipedia.org/wiki/Precision_and_recall for details on the
# following metrics.


def Precision(summary_stats):
  """The fraction of positive suggestions the model gives that are correct."""
  return Percent(summary_stats.true_positives,
                 summary_stats.true_positives + summary_stats.false_positives)


def Recall(summary_stats):
  """The fraction of positive examples that the model gets right."""
  return Percent(summary_stats.true_positives,
                 summary_stats.true_positives + summary_stats.false_negatives)


def Accuracy(summary_stats):
  """The fraction of all examples that the model gets right."""
  return Percent(
      summary_stats.true_positives + summary_stats.true_negatives,
      summary_stats.true_positives + summary_stats.true_negatives
      + summary_stats.false_positives + summary_stats.false_negatives)


def FbetaScore(summary_stats, beta=0.5):
  """A metric between 0 and 1 that balances Precision and Recall.

  Returns the metric you get if you consider Recall to be ``beta`` times as
  important as Precision.
  """
  tp = summary_stats.true_positives
  fp = summary_stats.false_positives
  fn = summary_stats.false_negatives

  return (
    ((1 + beta**2) * tp)
    / float((1 + beta**2) * tp + beta**2 * fn + fp))


def DetectionRate(summary_stats):
  """The fraction of all examples that Predator do give some results.

  All positive and true_negative results will be counted.
  """
  # A detected example means Predator provide some results for it, or
  # Predator find nothing if the example is supposed to have no result.
  all_detected_examples = (summary_stats.true_positives +
                           summary_stats.false_positives +
                           summary_stats.true_negatives)
  all_examples = (summary_stats.true_positives +
                  summary_stats.true_negatives +
                  summary_stats.false_positives +
                  summary_stats.false_negatives)

  return Percent(all_detected_examples, all_examples)


def PrintMetrics(input_output_pairs):  # pragma: no cover
  """Print a series of metrics to the user about the given examples."""
  result = GradeModel(input_output_pairs)

  print 'Total examples:', result.total_examples
  print 'True positives:', result.true_positives
  print 'False positives:', result.false_positives
  print 'True negatives:', result.true_negatives
  print 'False negatives', result.false_negatives

  if result.unsure or result.untriaged:
    print '--------'
  if result.unsure:
    print "%s unsure examples discarded" % result.unsure
  if result.untriaged:
    print "%s untriaged examples discarded" % result.untriaged

  print '--------'
  print 'Metrics:'
  print '  precision: %.2f%%' % Precision(result)
  print '  recall: %.2f%%' % Recall(result)
  print '  accuracy: %.2f%%' % Accuracy(result)
  print '  detection rate: %.2f%%' % DetectionRate(result)

  print '--------'
  print 'Maximum possible values of the metrics when using a confidence '
  print 'threshold:'
  precision_threshold, max_precision = MaximizeMetricWithThreshold(
      input_output_pairs, Precision)
  print ('  Max precision is %.2f%% with a confidence threshold of %f.'
         % (max_precision, precision_threshold))
  recall_threshold, max_recall = MaximizeMetricWithThreshold(
      input_output_pairs, Recall)
  print ('  Max recall is %.2f%% with a confidence threshold of %f.'
         % (max_recall, recall_threshold))
  accuracy_threshold, max_accuracy = MaximizeMetricWithThreshold(
      input_output_pairs, Accuracy)
  print ('  Max accuracy is %.2f%% with a confidence threshold of %f.'
         % (max_accuracy, accuracy_threshold))
  f_score_threshold, max_f_score = MaximizeMetricWithThreshold(
      input_output_pairs, FbetaScore)
  print ('  Max f-beta score is %.2f with a confidence threshold of %f.'
         % (max_f_score, f_score_threshold))
  detection_rate_threshold, max_detection_rate = MaximizeMetricWithThreshold(
      input_output_pairs, DetectionRate)
  print ('  Max detection rate is %.2f%% with a confidence threshold of %f.'
         % (max_detection_rate, detection_rate_threshold))


def MaximizeMetricWithThreshold(input_output_pairs, metric):
  """Find the confidence threshold that maximizes this metric on these examples.

  We may want to optimize for different metrics depending on the situation. For
  example, if we were sending email alerts to CL authors, we would want to
  maximize for precision, to ensure we aren't sending alerts unless we're sure
  the author's CL is responsible. However if we were just surfacing results on
  a dashboard in an on-demand way, we would want to maximize for something like
  accuracy or recall.

  Args:
    input_output_pairs (iterable of (CrashAnalysis, list<Suspect>) pairs): A set
      of labelled examples, along with the result produced by Predator for each
      example.
    metric (function: SummaryStats -> Number): The function to maximize.
  Returns:
    (threshold, value)
    threshold (float): The confidence threshold that maximizes the value of this
      metric on these examples.
    value: The value of the metric given this threshold.
  """
  confidences = [suspect.confidence
                 for _, suspects in input_output_pairs
                 for suspect in suspects]
  thresholds = itertools.chain([0], confidences)
  results = (
    (threshold, metric(GradeWithThreshold(input_output_pairs, threshold)))
    for threshold in thresholds
  )
  return max(results, key=lambda pair: pair[1])


def GradeWithThreshold(input_output_pairs, threshold):
  """The result of GradeModel when using a confidence threshold.

  Args:
    input_output_pairs (iterable of (CrashAnalysis, list<Suspect>) pairs): A set
      of labelled examples, along with the result produced by Predator for each
      example.
    threshold (float): The confidence threshold for considering a suspect. I.e.
      any suspect with confidence <= threshold will be discarded for the purpose
      of grading the model.
  Returns:
    A SummaryStats: The result of calling GradeModel on the given examples,
    after suspects have been filtered according to the threshold.
  """

  def FilterSuspectsBelowThreshold(suspects):
    return filter(
        lambda s: s.confidence > threshold, suspects)

  examples_with_filtered_suspects = (
    (crash, FilterSuspectsBelowThreshold(suspects))
    for crash, suspects in input_output_pairs)
  return GradeModel(examples_with_filtered_suspects)
