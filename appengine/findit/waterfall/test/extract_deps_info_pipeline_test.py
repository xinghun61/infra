# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from common import chrome_dependency_fetcher
from common.dependency import Dependency
from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs.gitiles.diff import ChangeType
from waterfall.extract_deps_info_pipeline import ExtractDEPSInfoPipeline


class ExtractDEPSInfoPipelineTest(testing.AppengineTestCase):
  app_module = pipeline_handlers._APP

  def testExtractDEPSInfo(self):
    def MockGetDependency(_, revision, os_platform):
      self.assertEqual('unix', os_platform)
      if revision == 'rev2':
        return {
            'src/': Dependency('src/', 'https://url_src', 'rev2', 'DEPS'),
            'src/dep1': Dependency('src/dep1', 'https://url_dep1', '9', 'DEPS'),
        }
      else:
        self.assertEqual('rev2^', revision)
        return {
            'src/': Dependency('src/', 'https://url_src', 'rev2^', 'DEPS'),
            'src/dep1': Dependency('src/dep1', 'https://url_dep1', '7', 'DEPS'),
        }

    failure_info = {
        'master_name': 'chromium.linux',
        'builder_name': 'Linux Tests',
        'build_number': 123,
        'chromium_revision': 'rev2',
        'failed': True,
    }
    change_logs = {
        'rev2': {
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'DEPS',
                    'new_path': 'DEPS'
                },
            ]
        },
        'rev1': {
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/file.cc',
                    'new_path': 'a/file.cc'
                },
            ]
        },
    }
    expected_deps_info = {
        'deps': {
            'src/': {
                'repo_url': 'https://url_src',
                'revision': 'rev2',
            },
            'src/dep1': {
                'repo_url': 'https://url_dep1',
                'revision': '9',
            },
        },
        'deps_rolls': {
            'rev2': [
                {
                    'path': 'src/dep1',
                    'repo_url': 'https://url_dep1',
                    'old_revision': '7',
                    'new_revision': '9',
                },
            ]
        }
    }

    pipeline = ExtractDEPSInfoPipeline()
    self.mock(chrome_dependency_fetcher.ChromeDependencyFetcher,
              'GetDependency', MockGetDependency)
    deps_info = pipeline.run(failure_info, change_logs)
    self.assertEqual(expected_deps_info, deps_info)

  def testBailOutIfNotAFailedBuild(self):
    failure_info = {
        'failed': False,
    }
    change_logs = {}
    expected_deps_info = {
        'deps': {},
        'deps_rolls': {},
    }

    pipeline = ExtractDEPSInfoPipeline()
    deps_info = pipeline.run(failure_info, change_logs)
    self.assertEqual(expected_deps_info, deps_info)

  def testBailOutIfNoValidChromiumRevision(self):
    failure_info = {
        'failed': True,
        'chromium_revision': None,
    }
    change_logs = {}
    expected_deps_info = {
        'deps': {},
        'deps_rolls': {},
    }

    pipeline = ExtractDEPSInfoPipeline()
    deps_info = pipeline.run(failure_info, change_logs)
    self.assertEqual(expected_deps_info, deps_info)

  def testBailOutIfInfraFailure(self):
    failure_info = {
        'failed': True,
        'failure_type': failure_type.INFRA,
        'chromium_revision': '00baf00ba',
    }
    change_logs = {}
    expected_deps_info = {
        'deps': {},
        'deps_rolls': {},
    }

    pipeline = ExtractDEPSInfoPipeline()
    deps_info = pipeline.run(failure_info, change_logs)
    self.assertEqual(expected_deps_info, deps_info)
