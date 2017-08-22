# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import sys

_ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__),
                                          os.path.pardir))
_FIRST_PARTY_DIR = os.path.join(_ROOT_DIR, 'first_party')
sys.path.insert(1, _FIRST_PARTY_DIR)

from local_libs import script_util

script_util.SetUpSystemPaths(_ROOT_DIR)

from analysis.type_enums import CrashClient
from app.common.model import triage_status
from scripts.delta_test import delta_test
from scripts import run_predator
from scripts import setup


def RunModelOnTestSet(client_id, app_id, testset_path):  # pragma: no cover
  """Get pairs of (CrashAnalysis, Culprit) for a set of test cases.

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
  Yields:
    (crash, culprit)
    crash (CrashAnalysis subclass): An entity representing one test case,
      usually triaged and labelled with the correct CL if there is one.
    culprit (Culprit): The answer produced by Predator.
  """
  crashes = delta_test.ReadCrashesFromCsvTestset(testset_path)
  culprits = run_predator.GetCulpritsOnRevision(crashes, 'HEAD', client_id,
                                                app_id)
  for crash_id, culprit in culprits.iteritems():
    crash = crashes[crash_id]
    yield crash, culprit


def CommitUrlEquals(url1, url2):
  # Some URLs have '.git' in them, some don't
  url1_standardized = url1.replace('.git', '')
  url2_standardized = url2.replace('.git', '')
  return url1_standardized == url2_standardized


def IsTruePositive(correct_cl_url, suspects):  # pragma: no cover
  """Determine if this Predator result is a true positive.

  Args:
    correct_cl_url (str): The URL of the correct CL for this example.
    suspects (list of Suspect): The answers produced by Predator.

  An example is considered to be a true positive iff: the correct CL is among
  the suspects identified by Predator, and Predator assigned it a confidence
  value greater than or equal to that of any other suspect.
  """
  max_confidence = max(suspect.confidence for suspect in suspects)
  top_suspect_urls = [suspect.changelog.commit_url for suspect in
                      suspects if
                      suspect.confidence == max_confidence]
  return any(
      CommitUrlEquals(correct_cl_url, suspect_url)
      for suspect_url in top_suspect_urls)


def GradeModel(input_output_pairs):  # pragma: no cover
  """Grade the model's performance on a set of examples.

  Args:
    input_output_pairs (iterable of (CrashAnalysis, Culprit) pairs): A set of
      labelled examples, along with the result produced by Predator for each
      example.
  Prints:
    The number of test cases that are true positive, false positive, etc., and
    metrics like the model's precision, recall, and accuracy.
  """
  true_positives = 0
  false_positives = 0
  true_negatives = 0
  false_negatives = 0
  untriaged = 0
  unsure = 0
  total_examples = 0

  for crash, culprit in input_output_pairs:
    total_examples += 1

    if crash.suspected_cls_triage_status == triage_status.UNTRIAGED:
      if untriaged == 0:
        logging.warning("Testset file contains untriaged example(s). "
                        "These will be discarded for the analysis.")
      untriaged += 1
      continue

    if crash.suspected_cls_triage_status == triage_status.TRIAGED_UNSURE:
      if unsure == 0:
        logging.warning("Testset file contains example(s) triaged as 'unsure'. "
                        "These will be discarded for the analysis.")
      unsure += 1
      continue

    correct_cls = crash.culprit_cls
    suspects = culprit.cls

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

  def Percent(a, b):
    return (a / float(b)) * 100

  precision = Percent(true_positives, true_positives + false_positives)
  recall = Percent(true_positives, true_positives + false_negatives)
  accuracy = Percent(
      true_positives + true_negatives,
      true_positives + true_negatives + false_positives + false_negatives)

  print 'Total examples:', total_examples
  print 'True positives:', true_positives
  print 'False positives:', false_positives
  print 'True negatives:', true_negatives
  print 'False negatives', false_negatives

  if unsure or untriaged:
    print '--------'
  if unsure:
    print "%s unsure examples discarded" % unsure
  if untriaged:
    print "%s untriaged examples discarded" % untriaged

  print '--------'
  print 'Metrics:'
  print '  precision: %.2f%%' % precision
  print '  recall: %.2f%%' % recall
  print '  accuracy: %.2f%%' % accuracy