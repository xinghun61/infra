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
  antibody.setup_antibody_db(cc, os.path.join(DATA_DIR,
                                              'ANTIBODY_DB_schema_setup.sql'))
  checkout = args.git_checkout_path
  if args.parse_git_rietveld or args.run_antibody:
    git_commit_parser.upload_to_sql(cc, checkout, args.since)
    git_commits_with_review_urls = git_commit_parser.get_urls_from_git_commit(
        cc)
    for review_url in git_commits_with_review_urls:
      # cannot get access into chromereview.googleplex.com
      # cannot support chromium-review.googlesource.com (gerrit)
      if not any(host in review_url for host in (
          'chromereviews.googleplex',
          'chromium-review.googlesource',
      )):
        code_review_parse.add_rietveld_data_to_review(review_url, cc)
        code_review_parse.add_rietveld_data_to_review_people(review_url, cc)
    csql.commit(connection)
  if args.write_html or args.run_antibody:
    if not os.path.exists(args.output_dir_path):
      os.makedirs(args.output_dir_path)
    antibody.generate_stats_files(cc, args.output_dir_path)
    gitiles_prefix = antibody.get_gitiles_prefix(checkout)
    if not gitiles_prefix:
      gitiles_prefix = ''
    antibody.get_tbr_by_user(code_review_parse.get_tbr_no_lgtm(cc, 'tbr'),
                             gitiles_prefix, args.output_dir_path)
    antibody.generate_antibody_ui(gitiles_prefix, args.output_dir_path,
        code_review_parse.get_tbr_no_lgtm(cc, 'author'))

  csql.close(connection, cc)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
