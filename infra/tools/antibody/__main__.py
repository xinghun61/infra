# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Antibody is meant to audit reviews for the Chromium project.

Example invocation: [TBD]
  ./run.py infra.tools.antibody <arguments>
"""

# This file is untested, keep as little code as possible in there.

import argparse
import logging
import os
import requests_cache
import sys

from infra.tools.antibody import antibody
import infra.tools.antibody.cloudsql_connect as csql
from infra.tools.antibody import code_review_parse
from infra.tools.antibody import git_commit_parser
import infra_libs.logs

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# https://storage.googleapis.com/chromium-infra-docs/infra/html/logging.html
LOGGER = logging.getLogger(__name__)


def main(argv):
  parser = argparse.ArgumentParser(
    prog="antibody",
    description=sys.modules['__main__'].__doc__)
  antibody.add_argparse_options(parser)
  infra_libs.logs.add_argparse_options(parser)
  args = parser.parse_args(argv)

  infra_libs.logs.process_argparse_options(args)

  if args.cache_path:
    requests_cache.install_cache(args.cache_path)
  else:
    requests_cache.install_cache(os.path.join(DATA_DIR, 'rietveld_cache'))

  # Do more processing here
  LOGGER.info('Antibody starting')
  with open(args.sql_password_file, 'r') as f:
    password = f.read().strip()
  connection, cc = csql.connect(password)
  antibody.setup_antibody_db(cc)
  if args.parse_git_rietveld or args.run_antibody:
    checkout = args.git_checkout_path
    git_commit_parser.upload_git_to_sql(cc, checkout)
    git_commits_with_review_urls = git_commit_parser.get_urls_from_git_db(cc)
    for git_hash, review_url in git_commits_with_review_urls:
      # cannot get access into chromereview.googleplex.com
      if 'chromereviews.googleplex' not in review_url:
        code_review_parse.add_rietveld_data_to_db(git_hash, review_url, cc)
  if args.write_html or args.run_antibody:
    suspicious_commits = code_review_parse.get_tbr_no_lgtm(cc)
    # TODO(ksho): un-hardcode the gitiles prefix once git checkout path command
    # line functionality comes in from Keeley's cl, read in from 
    # codereview.settings instead
    gitiles_prefix = "https://chromium.googlesource.com/infra/infra/+/"
    antibody.generate_antibody_ui(suspicious_commits, gitiles_prefix)

  csql.close(connection, cc)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))