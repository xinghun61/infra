# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from handlers.flake.detection import flake_detection_utils
from libs import analysis_status
from libs import time_util
from model.flake.analysis.flake_culprit import FlakeCulprit
from model.flake.analysis.master_flake_analysis import MasterFlakeAnalysis
from model.flake.detection.flake_occurrence import FlakeOccurrence
from model.flake.flake import Flake
from model.flake.flake import TestLocation
from model.flake.flake_issue import FlakeIssue
from model.flake.flake_type import FlakeType
from waterfall.test.wf_testcase import WaterfallTestCase


class FlakeDetectionUtilsTest(WaterfallTestCase):

  @mock.patch.object(time_util, 'GetUTCNow', return_value=datetime(2018, 1, 3))
  @mock.patch.object(
      time_util, 'GetDateDaysBeforeNow', return_value=datetime(2017, 12, 27))
  def testGetFlakeInformation(self, *_):
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=900)
    flake_issue.last_updated_time_by_flake_detection = datetime(2018, 1, 1)
    flake_issue.last_updated_time_in_monorail = datetime(2018, 1, 2)
    flake_issue.status = 'Started'
    flake_issue.put()

    luci_project = 'chromium'
    step_ui_name = 'step'
    test_name = 'test'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name'
    test_label_name = 'test_label'
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name,
    )

    flake.component = 'Mock>Component'
    flake.test_location = TestLocation()
    flake.test_location.file_path = '../../some/test/path/a.cc'
    flake.test_location.line_number = 42
    flake.flake_issue_key = flake_issue.key
    flake.flake_score_last_week = 10
    flake.put()

    build_id = 123
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    legacy_build_number = 999
    time_happened = datetime(2018, 1, 1)
    gerrit_cl_id = 98765
    occurrence = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_FALSE_REJECTION,
        build_id=build_id,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=time_happened,
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence.time_detected = datetime(2018, 1, 1)
    occurrence.put()

    occurrence2 = FlakeOccurrence.Create(
        flake_type=FlakeType.RETRY_WITH_PATCH,
        build_id=124,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder='luci builder 2',
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=datetime(2018, 1, 2, 3),
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence2.time_detected = datetime(2018, 1, 2, 3)
    occurrence2.put()

    occurrence3 = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_FALSE_REJECTION,
        build_id=125,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder='luci builder 2',
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=datetime(2018, 1, 2, 2),
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence3.time_detected = datetime(2018, 1, 2, 2)
    occurrence3.put()

    occurrence4 = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_HIDDEN_FLAKE,
        build_id=126,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder='luci builder 2',
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=datetime(2018, 1, 2, 2),
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence4.time_detected = datetime(2018, 1, 2, 2)
    occurrence4.put()

    occurrence5 = FlakeOccurrence.Create(
        flake_type=FlakeType.CI_FAILED_STEP,
        build_id=127,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder='luci builder 2',
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=datetime(2018, 1, 2, 2),
        gerrit_cl_id=-1,
        parent_flake_key=flake.key)
    occurrence5.time_detected = datetime(2018, 1, 2, 2)
    occurrence5.put()

    occurrence6 = FlakeOccurrence.Create(
        flake_type=FlakeType.CI_FAILED_STEP,
        build_id=128,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder='luci builder 2',
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=datetime(2017, 1, 2, 2),
        gerrit_cl_id=-1,
        parent_flake_key=flake.key)
    occurrence6.time_detected = datetime(2017, 1, 2, 2)
    occurrence6.put()

    culprit1 = FlakeCulprit.Create('chromium', 'rev1', 123456, 'culprit_url')
    culprit1.put()

    analysis = MasterFlakeAnalysis.Create(legacy_master_name, luci_builder,
                                          legacy_build_number, step_ui_name,
                                          test_name)
    analysis.bug_id = 900
    analysis.culprit_urlsafe_key = culprit1.key.urlsafe()
    analysis.confidence_in_culprit = 0.98
    analysis.put()

    culprit2 = FlakeCulprit.Create('chromium', 'rev2', 123457, 'culprit_url')
    culprit2.put()
    analysis_1 = MasterFlakeAnalysis.Create(legacy_master_name, luci_builder,
                                            legacy_build_number - 1,
                                            step_ui_name, test_name)
    analysis_1.bug_id = 900
    analysis_1.culprit_urlsafe_key = culprit2.key.urlsafe()
    analysis_1.put()

    expected_flake_dict = {
        'luci_project':
            'chromium',
        'normalized_step_name':
            'normalized_step_name',
        'normalized_test_name':
            'normalized_test_name',
        'test_label_name':
            'test_label',
        'flake_issue_key':
            flake_issue.key,
        'last_occurred_time':
            None,
        'last_test_location_based_tag_update_time':
            None,
        'false_rejection_count_last_week':
            0,
        'impacted_cl_count_last_week':
            0,
        'archived':
            False,
        'flake_counts_last_week': [
            {
                'flake_type': 'cq false rejection',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
            {
                'flake_type': 'cq step level retry',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
            {
                'flake_type': 'cq hidden flake',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
            {
                'flake_type': 'ci failed step',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
        ],
        'flake_score_last_week':
            10,
        'flake_issue': {
            'flake_culprit_key':
                None,
            'monorail_project':
                'chromium',
            'issue_id':
                900,
            'last_updated_time_by_flake_detection':
                datetime(2018, 1, 1),
            'issue_link': ('https://monorail-prod.appspot.com/p/chromium/'
                           'issues/detail?id=900'),
            'merge_destination_key':
                None,
            'last_updated_time_in_monorail':
                '1 day, 00:00:00',
            'last_updated_time_with_analysis_results':
                None,
            'create_time_in_monorail':
                None,
            'labels': [],
            'status':
                'Started',
        },
        'component':
            'Mock>Component',
        'test_location': {
            'file_path': '../../some/test/path/a.cc',
            'line_number': 42,
        },
        'tags': [],
        'culprits': [{
            'revision': 'rev1',
            'commit_position': culprit1.commit_position,
            'culprit_key': culprit1.key.urlsafe()
        }],
        'sample_analysis':
            None,
        'occurrences': [{
            'group_by_field':
                'luci builder 2',
            'occurrences': [
                {
                    'flake_type': 'cq step level retry',
                    'build_id': '124',
                    'step_ui_name': step_ui_name,
                    'test_name': test_name,
                    'tags': [],
                    'build_configuration': {
                        'luci_project': 'chromium',
                        'luci_bucket': 'try',
                        'luci_builder': 'luci builder 2',
                        'legacy_master_name': 'buildbot master',
                        'legacy_build_number': 999
                    },
                    'time_happened': '2018-01-02 03:00:00 UTC',
                    'time_detected': '2018-01-02 03:00:00 UTC',
                    'gerrit_cl_id': gerrit_cl_id
                },
                {
                    'flake_type': 'cq false rejection',
                    'build_id': '125',
                    'step_ui_name': step_ui_name,
                    'test_name': test_name,
                    'tags': [],
                    'build_configuration': {
                        'luci_project': 'chromium',
                        'luci_bucket': 'try',
                        'luci_builder': 'luci builder 2',
                        'legacy_master_name': 'buildbot master',
                        'legacy_build_number': 999
                    },
                    'time_happened': '2018-01-02 02:00:00 UTC',
                    'time_detected': '2018-01-02 02:00:00 UTC',
                    'gerrit_cl_id': gerrit_cl_id
                },
                {
                    'flake_type': 'ci failed step',
                    'build_id': '127',
                    'step_ui_name': step_ui_name,
                    'test_name': test_name,
                    'tags': [],
                    'build_configuration': {
                        'luci_project': 'chromium',
                        'luci_bucket': 'try',
                        'luci_builder': 'luci builder 2',
                        'legacy_master_name': 'buildbot master',
                        'legacy_build_number': 999
                    },
                    'time_happened': '2018-01-02 02:00:00 UTC',
                    'time_detected': '2018-01-02 02:00:00 UTC',
                    'gerrit_cl_id': -1,
                },
                {
                    'flake_type': 'cq hidden flake',
                    'build_id': '126',
                    'step_ui_name': step_ui_name,
                    'test_name': test_name,
                    'tags': [],
                    'build_configuration': {
                        'luci_project': 'chromium',
                        'luci_bucket': 'try',
                        'luci_builder': 'luci builder 2',
                        'legacy_master_name': 'buildbot master',
                        'legacy_build_number': 999
                    },
                    'time_happened': '2018-01-02 02:00:00 UTC',
                    'time_detected': '2018-01-02 02:00:00 UTC',
                    'gerrit_cl_id': gerrit_cl_id,
                },
            ]
        },
                        {
                            'group_by_field':
                                'luci builder',
                            'occurrences': [{
                                'flake_type': 'cq false rejection',
                                'build_id': '123',
                                'step_ui_name': step_ui_name,
                                'test_name': test_name,
                                'tags': [],
                                'build_configuration': {
                                    'luci_project': 'chromium',
                                    'luci_bucket': 'try',
                                    'luci_builder': 'luci builder',
                                    'legacy_master_name': 'buildbot master',
                                    'legacy_build_number': 999
                                },
                                'time_happened': '2018-01-01 00:00:00 UTC',
                                'time_detected': '2018-01-01 00:00:00 UTC',
                                'gerrit_cl_id': gerrit_cl_id
                            }]
                        }],
    }
    self.assertEqual(expected_flake_dict,
                     flake_detection_utils.GetFlakeInformation(flake, 6))

  @mock.patch.object(time_util, 'GetUTCNow', return_value=datetime(2019, 1, 3))
  @mock.patch.object(
      time_util, 'GetDateDaysBeforeNow', return_value=datetime(2018, 12, 27))
  def testGetFlakeInformationOldFlakes(self, *_):
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=900)
    flake_issue.last_updated_time_by_flake_detection = datetime(2018, 1, 1)
    flake_issue.last_updated_time_in_monorail = datetime(2018, 1, 2)
    flake_issue.status = 'Started'
    flake_issue.put()

    luci_project = 'chromium'
    step_ui_name = 'step'
    test_name = 'test'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name'
    test_label_name = 'test_label'
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name,
    )

    flake.component = 'Mock>Component'
    flake.test_location = TestLocation()
    flake.test_location.file_path = '../../some/test/path/a.cc'
    flake.test_location.line_number = 42
    flake.flake_issue_key = flake_issue.key
    flake.archived = True
    flake.put()

    build_id = 123
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    legacy_build_number = 999
    time_happened = datetime(2018, 1, 1)
    gerrit_cl_id = 98765
    occurrence = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_FALSE_REJECTION,
        build_id=build_id,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=time_happened,
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence.time_detected = datetime(2018, 1, 1)
    occurrence.put()

    occurrence2 = FlakeOccurrence.Create(
        flake_type=FlakeType.RETRY_WITH_PATCH,
        build_id=124,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder='luci builder 2',
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=datetime(2018, 1, 2, 3),
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence2.time_detected = datetime(2018, 1, 2, 3)
    occurrence2.put()

    occurrence3 = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_FALSE_REJECTION,
        build_id=125,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder='luci builder 2',
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=datetime(2018, 1, 2, 2),
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence3.time_detected = datetime(2018, 1, 2, 2)
    occurrence3.put()

    occurrence4 = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_HIDDEN_FLAKE,
        build_id=126,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder='luci builder 2',
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=datetime(2018, 1, 2, 4),
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence4.time_detected = datetime(2018, 1, 2, 4)
    occurrence4.put()

    occurrence5 = FlakeOccurrence.Create(
        flake_type=FlakeType.CI_FAILED_STEP,
        build_id=127,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder='luci builder 2',
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=datetime(2018, 1, 2, 5),
        gerrit_cl_id=-1,
        parent_flake_key=flake.key)
    occurrence5.time_detected = datetime(2018, 1, 2, 5)
    occurrence5.put()

    culprit1 = FlakeCulprit.Create('chromium', 'rev1', 123456, 'culprit_url')
    culprit1.put()

    analysis = MasterFlakeAnalysis.Create(legacy_master_name, luci_builder,
                                          legacy_build_number, step_ui_name,
                                          test_name)
    analysis.bug_id = 900
    analysis.culprit_urlsafe_key = culprit1.key.urlsafe()
    analysis.confidence_in_culprit = 0.98
    analysis.put()

    culprit2 = FlakeCulprit.Create('chromium', 'rev2', 123457, 'culprit_url')
    culprit2.put()
    analysis_1 = MasterFlakeAnalysis.Create(legacy_master_name, luci_builder,
                                            legacy_build_number - 1,
                                            step_ui_name, test_name)
    analysis_1.bug_id = 900
    analysis_1.culprit_urlsafe_key = culprit2.key.urlsafe()
    analysis_1.put()

    expected_flake_dict = {
        'luci_project':
            'chromium',
        'normalized_step_name':
            'normalized_step_name',
        'normalized_test_name':
            'normalized_test_name',
        'test_label_name':
            'test_label',
        'flake_issue_key':
            flake_issue.key,
        'last_occurred_time':
            None,
        'last_test_location_based_tag_update_time':
            None,
        'false_rejection_count_last_week':
            0,
        'impacted_cl_count_last_week':
            0,
        'archived':
            True,
        'flake_counts_last_week': [
            {
                'flake_type': 'cq false rejection',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
            {
                'flake_type': 'cq step level retry',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
            {
                'flake_type': 'cq hidden flake',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
            {
                'flake_type': 'ci failed step',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
        ],
        'flake_score_last_week':
            0,
        'flake_issue': {
            'flake_culprit_key':
                None,
            'monorail_project':
                'chromium',
            'issue_id':
                900,
            'last_updated_time_by_flake_detection':
                datetime(2018, 1, 1),
            'issue_link': ('https://monorail-prod.appspot.com/p/chromium/'
                           'issues/detail?id=900'),
            'merge_destination_key':
                None,
            'last_updated_time_in_monorail':
                '366 days, 00:00:00',
            'last_updated_time_with_analysis_results':
                None,
            'create_time_in_monorail':
                None,
            'labels': [],
            'status':
                'Started',
        },
        'component':
            'Mock>Component',
        'test_location': {
            'file_path': '../../some/test/path/a.cc',
            'line_number': 42,
        },
        'tags': [],
        'culprits': [{
            'revision': 'rev1',
            'commit_position': culprit1.commit_position,
            'culprit_key': culprit1.key.urlsafe()
        }],
        'sample_analysis':
            None,
        'occurrences': [{
            'group_by_field':
                'luci builder 2',
            'occurrences': [
                {
                    'flake_type': 'ci failed step',
                    'build_id': '127',
                    'step_ui_name': step_ui_name,
                    'test_name': test_name,
                    'tags': [],
                    'build_configuration': {
                        'luci_project': 'chromium',
                        'luci_bucket': 'try',
                        'luci_builder': 'luci builder 2',
                        'legacy_master_name': 'buildbot master',
                        'legacy_build_number': 999
                    },
                    'time_happened': '2018-01-02 05:00:00 UTC',
                    'time_detected': '2018-01-02 05:00:00 UTC',
                    'gerrit_cl_id': -1,
                },
                {
                    'flake_type': 'cq hidden flake',
                    'build_id': '126',
                    'step_ui_name': step_ui_name,
                    'test_name': test_name,
                    'tags': [],
                    'build_configuration': {
                        'luci_project': 'chromium',
                        'luci_bucket': 'try',
                        'luci_builder': 'luci builder 2',
                        'legacy_master_name': 'buildbot master',
                        'legacy_build_number': 999
                    },
                    'time_happened': '2018-01-02 04:00:00 UTC',
                    'time_detected': '2018-01-02 04:00:00 UTC',
                    'gerrit_cl_id': gerrit_cl_id,
                },
                {
                    'flake_type': 'cq step level retry',
                    'build_id': '124',
                    'step_ui_name': step_ui_name,
                    'test_name': test_name,
                    'tags': [],
                    'build_configuration': {
                        'luci_project': 'chromium',
                        'luci_bucket': 'try',
                        'luci_builder': 'luci builder 2',
                        'legacy_master_name': 'buildbot master',
                        'legacy_build_number': 999
                    },
                    'time_happened': '2018-01-02 03:00:00 UTC',
                    'time_detected': '2018-01-02 03:00:00 UTC',
                    'gerrit_cl_id': gerrit_cl_id
                },
                {
                    'flake_type': 'cq false rejection',
                    'build_id': '125',
                    'step_ui_name': step_ui_name,
                    'test_name': test_name,
                    'tags': [],
                    'build_configuration': {
                        'luci_project': 'chromium',
                        'luci_bucket': 'try',
                        'luci_builder': 'luci builder 2',
                        'legacy_master_name': 'buildbot master',
                        'legacy_build_number': 999
                    },
                    'time_happened': '2018-01-02 02:00:00 UTC',
                    'time_detected': '2018-01-02 02:00:00 UTC',
                    'gerrit_cl_id': gerrit_cl_id
                },
            ]
        },
                        {
                            'group_by_field':
                                'luci builder',
                            'occurrences': [{
                                'flake_type': 'cq false rejection',
                                'build_id': '123',
                                'step_ui_name': step_ui_name,
                                'test_name': test_name,
                                'tags': [],
                                'build_configuration': {
                                    'luci_project': 'chromium',
                                    'luci_bucket': 'try',
                                    'luci_builder': 'luci builder',
                                    'legacy_master_name': 'buildbot master',
                                    'legacy_build_number': 999
                                },
                                'time_happened': '2018-01-01 00:00:00 UTC',
                                'time_detected': '2018-01-01 00:00:00 UTC',
                                'gerrit_cl_id': gerrit_cl_id
                            }]
                        }],
    }
    self.assertEqual(expected_flake_dict,
                     flake_detection_utils.GetFlakeInformation(flake, 5))

  def testGetFlakeInformationNoOccurrences(self):

    luci_project = 'chromium'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name_2'
    test_label_name = 'test_label'
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)
    flake.put()

    self.assertIsNone(flake_detection_utils.GetFlakeInformation(flake, None))

  @mock.patch.object(time_util, 'GetUTCNow', return_value=datetime(2018, 1, 3))
  @mock.patch.object(
      time_util, 'GetDateDaysBeforeNow', return_value=datetime(2017, 12, 27))
  def testGetFlakeInformationClosedIssue(self, *_):
    flake_issue = FlakeIssue.Create(monorail_project='chromium', issue_id=900)
    flake_issue.last_updated_time_by_flake_detection = datetime(2018, 1, 1)
    flake_issue.last_updated_time_in_monorail = datetime(2018, 1, 2)
    flake_issue.status = 'WontFix'
    flake_issue.put()

    luci_project = 'chromium'
    step_ui_name = 'step'
    test_name = 'test'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name_3'
    test_label_name = 'test_label'
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)
    flake.flake_issue_key = flake_issue.key
    flake.put()

    build_id = 123
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    legacy_build_number = 999
    time_happened = datetime(2018, 1, 1)
    gerrit_cl_id = 98765
    occurrence = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_FALSE_REJECTION,
        build_id=build_id,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=time_happened,
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence.time_detected = datetime(2018, 1, 1)
    occurrence.put()

    expected_flake_dict = {
        'luci_project':
            'chromium',
        'normalized_step_name':
            normalized_step_name,
        'normalized_test_name':
            normalized_test_name,
        'test_label_name':
            test_label_name,
        'flake_issue_key':
            flake_issue.key,
        'last_occurred_time':
            None,
        'last_test_location_based_tag_update_time':
            None,
        'false_rejection_count_last_week':
            0,
        'impacted_cl_count_last_week':
            0,
        'archived':
            False,
        'flake_counts_last_week': [
            {
                'flake_type': 'cq false rejection',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
            {
                'flake_type': 'cq step level retry',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
            {
                'flake_type': 'cq hidden flake',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
            {
                'flake_type': 'ci failed step',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
        ],
        'flake_score_last_week':
            0,
        'component':
            None,
        'test_location':
            None,
        'tags': [],
        'occurrences': [{
            'group_by_field':
                'luci builder',
            'occurrences': [{
                'flake_type': 'cq false rejection',
                'build_id': '123',
                'step_ui_name': step_ui_name,
                'test_name': test_name,
                'tags': [],
                'build_configuration': {
                    'luci_project': 'chromium',
                    'luci_bucket': 'try',
                    'luci_builder': 'luci builder',
                    'legacy_master_name': 'buildbot master',
                    'legacy_build_number': 999
                },
                'time_happened': '2018-01-01 00:00:00 UTC',
                'time_detected': '2018-01-01 00:00:00 UTC',
                'gerrit_cl_id': gerrit_cl_id
            }]
        }],
    }

    self.assertEqual(expected_flake_dict,
                     flake_detection_utils.GetFlakeInformation(flake, 1))

  @mock.patch.object(time_util, 'GetUTCNow', return_value=datetime(2018, 1, 3))
  @mock.patch.object(
      time_util, 'GetDateDaysBeforeNow', return_value=datetime(2017, 12, 27))
  def testGetFlakeInformationNoIssue(self, *_):

    luci_project = 'chromium'
    step_ui_name = 'step'
    test_name = 'test'
    normalized_step_name = 'normalized_step_name'
    normalized_test_name = 'normalized_test_name_3'
    test_label_name = 'test_label'
    flake = Flake.Create(
        luci_project=luci_project,
        normalized_step_name=normalized_step_name,
        normalized_test_name=normalized_test_name,
        test_label_name=test_label_name)
    flake.put()

    build_id = 123
    luci_bucket = 'try'
    luci_builder = 'luci builder'
    legacy_master_name = 'buildbot master'
    legacy_build_number = 999
    time_happened = datetime(2018, 1, 1)
    gerrit_cl_id = 98765
    occurrence = FlakeOccurrence.Create(
        flake_type=FlakeType.CQ_FALSE_REJECTION,
        build_id=build_id,
        step_ui_name=step_ui_name,
        test_name=test_name,
        luci_project=luci_project,
        luci_bucket=luci_bucket,
        luci_builder=luci_builder,
        legacy_master_name=legacy_master_name,
        legacy_build_number=legacy_build_number,
        time_happened=time_happened,
        gerrit_cl_id=gerrit_cl_id,
        parent_flake_key=flake.key)
    occurrence.time_detected = datetime(2018, 1, 1)
    occurrence.put()

    expected_flake_dict = {
        'luci_project':
            'chromium',
        'normalized_step_name':
            normalized_step_name,
        'normalized_test_name':
            normalized_test_name,
        'test_label_name':
            test_label_name,
        'flake_issue_key':
            None,
        'last_occurred_time':
            None,
        'last_test_location_based_tag_update_time':
            None,
        'false_rejection_count_last_week':
            0,
        'impacted_cl_count_last_week':
            0,
        'archived':
            False,
        'flake_counts_last_week': [
            {
                'flake_type': 'cq false rejection',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
            {
                'flake_type': 'cq step level retry',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
            {
                'flake_type': 'cq hidden flake',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
            {
                'flake_type': 'ci failed step',
                'impacted_cl_count': 0,
                'occurrence_count': 0
            },
        ],
        'flake_score_last_week':
            0,
        'component':
            None,
        'test_location':
            None,
        'tags': [],
        'occurrences': [{
            'group_by_field':
                'luci builder',
            'occurrences': [{
                'flake_type': 'cq false rejection',
                'build_id': '123',
                'step_ui_name': step_ui_name,
                'test_name': test_name,
                'tags': [],
                'build_configuration': {
                    'luci_project': 'chromium',
                    'luci_bucket': 'try',
                    'luci_builder': 'luci builder',
                    'legacy_master_name': 'buildbot master',
                    'legacy_build_number': 999
                },
                'time_happened': '2018-01-01 00:00:00 UTC',
                'time_detected': '2018-01-01 00:00:00 UTC',
                'gerrit_cl_id': gerrit_cl_id
            }]
        }],
    }

    self.assertEqual(expected_flake_dict,
                     flake_detection_utils.GetFlakeInformation(flake, 1))

  def testGetFlakeAnalysesResultsNoAnalyses(self):
    self.assertEqual(([], None),
                     flake_detection_utils._GetFlakeAnalysesResults(123))

  def testGetFlakeAnalysesResultsFailedToGetCulprit(self):
    analysis = MasterFlakeAnalysis.Create('m', 'b', 12345, 's', 't')
    analysis.bug_id = 123
    analysis.culprit_urlsafe_key = 'culprit.key'
    analysis.status = analysis_status.COMPLETED
    analysis.put()

    self.assertEqual(([], {
        'status': 'Completed, no culprit found',
        'analysis_key': analysis.key.urlsafe()
    }), flake_detection_utils._GetFlakeAnalysesResults(123))

  def testGetFlakeAnalysesResultsShowRunningAnalysis(self):
    analysis_1 = MasterFlakeAnalysis.Create('m', 'b', 12345, 's', 't')
    analysis_1.bug_id = 123
    analysis_1.status = analysis_status.RUNNING
    analysis_1.put()

    analysis_2 = MasterFlakeAnalysis.Create('m', 'b', 12345, 's', 't')
    analysis_2.bug_id = 123
    analysis_2.status = analysis_status.ERROR
    analysis_2.put()

    self.assertEqual(([], {
        'status': 'Running',
        'analysis_key': analysis_1.key.urlsafe()
    }), flake_detection_utils._GetFlakeAnalysesResults(123))

  def testGetFlakeAnalysesResultsShowPendingAnalysis(self):
    analysis_1 = MasterFlakeAnalysis.Create('m', 'b', 12345, 's', 't')
    analysis_1.bug_id = 123
    analysis_1.put()

    self.assertEqual(([], {
        'status': 'Pending',
        'analysis_key': analysis_1.key.urlsafe()
    }), flake_detection_utils._GetFlakeAnalysesResults(123))

  def testGetFlakeAnalysesResultsNotShowErrorAnalysis(self):
    analysis_2 = MasterFlakeAnalysis.Create('m', 'b', 12345, 's', 't')
    analysis_2.bug_id = 123
    analysis_2.status = analysis_status.ERROR
    analysis_2.put()

    self.assertEqual(([], {}),
                     flake_detection_utils._GetFlakeAnalysesResults(123))
