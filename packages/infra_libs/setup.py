# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from setuptools import setup, find_packages

setup(
    name='infra_libs',
    version='1.1.11',
    description='Chrome Infra Libraries',
    long_description='Chrome Infra Libraries',
    classifiers=[
        'Programming Language :: Python :: 2.7',
    ],
    packages=find_packages(exclude=['*.test']),
    install_requires=[
        'google-api-python-client',
        'oauth2client',
        'protobuf',
        'requests',
    ],
    package_data={
        '': ['*.md', '*.proto'],
    },
)
