# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from setuptools import setup

setup(
    name='dataflow',
    version='0.0.2',
    description='Chrome Infra Dataflow Workflows',
    long_description=('This package includes Chrome Infra workflows as well as '
                      'common modules.'),
    classifiers=[
        'Programming Language :: Python :: 2.7',
    ],
    package_dir={'dataflow': ''},
    packages=['dataflow', 'dataflow.common'],
)
