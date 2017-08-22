# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import os
import sys

_ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__),
                                          os.path.pardir))
_FIRST_PARTY_DIR = os.path.join(_ROOT_DIR, 'first_party')
sys.path.insert(1, _FIRST_PARTY_DIR)

from local_libs import script_util

script_util.SetUpSystemPaths(_ROOT_DIR)

from analysis.type_enums import CrashClient
from local_libs import remote_api
from scripts import grade_model
from scripts import setup


if __name__ == '__main__':
  argparser = argparse.ArgumentParser(
      description=('Evaluate the current version of Predator on a local csv '
                   'testset. The testset must have been manually labelled. '
                   'Computes number of true positives, false positives etc., '
                   'as well as metrics like precision and recall.'))

  argparser.add_argument(
      'testset', help='The path to the csv testset to run the model on.')

  argparser.add_argument(
      '--client',
      '-c',
      default=setup.DEFAULT_CLIENT,
      help=('The name of the client to run. '
            'Possible values are: %s, %s, %s, %s.' %
            (CrashClient.CRACAS, CrashClient.FRACAS, CrashClient.CLUSTERFUZZ,
             CrashClient.UMA_SAMPLING_PROFILER)))

  argparser.add_argument(
      '--app',
      '-a',
      default=setup.DEFAULT_APP_ID,
      help=('App id of the App engine app that query needs to access. '
            'Defaults to %s. \nNOTE, only appspot app ids are supported, '
            'the app_id of googleplex app will have access issues '
            'due to internal proxy. ') % setup.DEFAULT_APP_ID)

  args = argparser.parse_args()
  remote_api.EnableRemoteApi(args.app)
  examples = grade_model.RunModelOnTestSet(args.client, args.app, args.testset)
  grade_model.GradeModel(examples)
