# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
from glucose import selfpack


def add_argparse_options(parser):
  subparsers = parser.add_subparsers()
  selfpack.add_subparser(subparsers)


def process_argparse_options(options):
  options.command(options)


def main():
  parser = argparse.ArgumentParser(
    description="Glyco is a tool to pack and unpack wheel files.")
  add_argparse_options(parser)

  options = parser.parse_args()

  process_argparse_options(options)
