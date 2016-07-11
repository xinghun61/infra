# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from setuptools import setup, find_packages

setup(
    name='infra_libs',
    version='1.1.0',
    description='Time series monitoring library',
    long_description='Time series monitoring library',
    classifiers=[
        'Programming Language :: Python :: 2.7',
    ],
    packages=find_packages(exclude=['*.test']),
    # google.protobuf - what package is that?
    install_requires=['googleapiclient', 'oauth2client', 'protobuf'],
    package_data={
        '': ['*.md', '*.proto'],
    },
)
