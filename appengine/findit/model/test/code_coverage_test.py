# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from google.appengine.api import datastore_errors

from model.code_coverage import CoveragePercentage
from model.code_coverage import DependencyRepository
from model.code_coverage import FileCoverageData
from model.code_coverage import PostsubmitReport
from model.code_coverage import PresubmitCoverageData
from model.code_coverage import SummaryCoverageData
from waterfall.test.wf_testcase import WaterfallTestCase


class CodeCoverageTest(WaterfallTestCase):

  def testCreateAndGetPostsubmitReport(self):
    server_host = 'chromium.googlesource.com'
    project = 'chromium/src'
    ref = 'refs/heads/master'
    revision = '99999'
    bucket = 'coverage'
    builder = 'linux-code-coverage'
    commit_position = 100
    commit_timestamp = datetime.datetime(2018, 1, 1)

    manifest = [
        DependencyRepository(
            path='//src',
            server_host='chromium.googlesource.com',
            project='chromium/src.git',
            revision='88888')
    ]

    summary_metrics = [{
        'covered': 1,
        'total': 2,
        'name': 'region'
    }, {
        'covered': 1,
        'total': 2,
        'name': 'function'
    }, {
        'covered': 1,
        'total': 2,
        'name': 'line'
    }]

    build_id = 123456789
    visible = True

    report = PostsubmitReport.Create(
        server_host=server_host,
        project=project,
        ref=ref,
        revision=revision,
        bucket=bucket,
        builder=builder,
        commit_position=commit_position,
        commit_timestamp=commit_timestamp,
        manifest=manifest,
        summary_metrics=summary_metrics,
        build_id=build_id,
        visible=visible)
    report.put()

    # Test key.
    self.assertEqual(
        'chromium.googlesource.com$chromium/src$refs/heads/master$99999$'
        'coverage$linux-code-coverage', report.key.id())

    # Test Create.
    fetched_reports = PostsubmitReport.query().fetch()
    self.assertEqual(1, len(fetched_reports))
    self.assertEqual(report, fetched_reports[0])

    # Test Get.
    self.assertEqual(
        report,
        PostsubmitReport.Get(
            server_host=server_host,
            project=project,
            ref=ref,
            revision=revision,
            bucket=bucket,
            builder=builder))

  def testCreateAndGetCoveragePercentage(self):
    path = '//base/test.cc'
    total_lines = 10
    covered_lines = 1

    percentage = CoveragePercentage(
        path=path, total_lines=total_lines, covered_lines=covered_lines)
    self.assertEqual(path, percentage.path)
    self.assertEqual(total_lines, percentage.total_lines)
    self.assertEqual(covered_lines, percentage.covered_lines)

  def testCreateCoveragePercentageRaiseError(self):
    with self.assertRaises(datastore_errors.BadValueError):
      CoveragePercentage(path='//base/test.cc', total_lines=0, covered_lines=0)

  def testCreateAndGetPresubmitCoverageData(self):
    server_host = 'chromium-review.googlesource.com'
    change = 138000
    patchset = 4
    build_id = 123456789
    data = [
        {
            'path': '//base1/test1.cc',
            'lines': [{
                'count': 100,
                'first': 1,
                'last': 3,
            }],
        },
        {
            'path': '//dir2/test2.cc',
            'lines': [{
                'count': 0,
                'first': 5,
                'last': 10,
            }],
        },
    ]

    coverage_data = PresubmitCoverageData.Create(
        server_host=server_host,
        change=change,
        patchset=patchset,
        build_id=build_id,
        data=data)
    coverage_data.put()

    # Test key.
    self.assertEqual('chromium-review.googlesource.com$138000$4',
                     coverage_data.key.id())

    # Test Create.
    fetched_coverage_data = PresubmitCoverageData.query().fetch()
    self.assertEqual(1, len(fetched_coverage_data))
    self.assertEqual(coverage_data, fetched_coverage_data[0])

    # Test Get.
    self.assertEqual(
        coverage_data,
        PresubmitCoverageData.Get(
            server_host=server_host, change=change, patchset=patchset))

  def testCreateAndGetFileCoverageData(self):
    server_host = 'chromium.googlesource.com'
    project = 'chromium/src'
    ref = 'refs/heads/master'
    revision = '99999'
    path = '//dir/test.cc'
    bucket = 'coverage'
    builder = 'linux-code-coverage'
    data = {
        'path': '//dir/test.cc',
        'lines': [{
            'count': 100,
            'first': 1,
            'last': 5,
        }],
        'timestamp': 1357,
        'revision': '12345'
    }

    file_coverage_data = FileCoverageData.Create(
        server_host=server_host,
        project=project,
        ref=ref,
        revision=revision,
        path=path,
        bucket=bucket,
        builder=builder,
        data=data)
    file_coverage_data.put()

    # Test key.
    self.assertEqual(
        ('chromium.googlesource.com$chromium/src$refs/heads/master$99999$'
         '//dir/test.cc$coverage$linux-code-coverage'),
        file_coverage_data.key.id())

    # Test Create.
    fetched_file_coverage_data = FileCoverageData.query().fetch()
    self.assertEqual(1, len(fetched_file_coverage_data))
    self.assertEqual(file_coverage_data, fetched_file_coverage_data[0])

    # Test Get.
    self.assertEqual(
        file_coverage_data,
        FileCoverageData.Get(
            server_host=server_host,
            project=project,
            ref=ref,
            revision=revision,
            path=path,
            bucket=bucket,
            builder=builder))

  def testAndCreateAndGetDirectoryCoverageData(self):
    server_host = 'chromium.googlesource.com'
    project = 'chromium/src'
    ref = 'refs/heads/master'
    revision = '99999'
    data_type = 'dirs'
    path = '//dir/'
    bucket = 'coverage'
    builder = 'linux-code-coverage'
    data = {
        'dirs': [],
        'files': [],
        'summaries': [{
            'covered': 1,
            'total': 1,
            'name': 'region'
        }, {
            'covered': 1,
            'total': 1,
            'name': 'function'
        }, {
            'covered': 1,
            'total': 1,
            'name': 'line'
        }],
        'path':
            '//dir/',
    }

    dir_coverage_data = SummaryCoverageData.Create(
        server_host=server_host,
        project=project,
        ref=ref,
        revision=revision,
        data_type=data_type,
        path=path,
        bucket=bucket,
        builder=builder,
        data=data)
    dir_coverage_data.put()

    # Test key.
    self.assertEqual(
        'chromium.googlesource.com$chromium/src$refs/heads/master$99999$'
        'dirs$//dir/$coverage$linux-code-coverage', dir_coverage_data.key.id())

    # Test Create.
    fetched_dir_coverage_data = SummaryCoverageData.query().fetch()
    self.assertEqual(1, len(fetched_dir_coverage_data))
    self.assertEqual(dir_coverage_data, fetched_dir_coverage_data[0])

    # Test Get.
    self.assertEqual(
        dir_coverage_data,
        SummaryCoverageData.Get(
            server_host=server_host,
            project=project,
            ref=ref,
            revision=revision,
            data_type=data_type,
            path=path,
            bucket=bucket,
            builder=builder))

  def testAndCreateAndGetComponentCoverageData(self):
    server_host = 'chromium.googlesource.com'
    project = 'chromium/src'
    ref = 'refs/heads/master'
    revision = '99999'
    data_type = 'components'
    path = 'Test>Component'
    bucket = 'coverage'
    builder = 'linux-code-coverage'
    data = {
        'dirs': [],
        'files': [],
        'summaries': [{
            'covered': 1,
            'total': 1,
            'name': 'region'
        }, {
            'covered': 1,
            'total': 1,
            'name': 'function'
        }, {
            'covered': 1,
            'total': 1,
            'name': 'line'
        }],
        'path':
            'Test>Component',
    }

    component_coverage_data = SummaryCoverageData.Create(
        server_host=server_host,
        project=project,
        ref=ref,
        revision=revision,
        data_type=data_type,
        path=path,
        bucket=bucket,
        builder=builder,
        data=data)
    component_coverage_data.put()

    # Test key.
    self.assertEqual(
        'chromium.googlesource.com$chromium/src$refs/heads/master$99999$'
        'components$Test>Component$coverage$linux-code-coverage',
        component_coverage_data.key.id())

    # Test Create.
    fetched_component_coverage_data = SummaryCoverageData.query().fetch()
    self.assertEqual(1, len(fetched_component_coverage_data))
    self.assertEqual(component_coverage_data,
                     fetched_component_coverage_data[0])

    # Test Get.
    self.assertEqual(
        component_coverage_data,
        SummaryCoverageData.Get(
            server_host=server_host,
            project=project,
            ref=ref,
            revision=revision,
            data_type=data_type,
            path=path,
            bucket=bucket,
            builder=builder))
