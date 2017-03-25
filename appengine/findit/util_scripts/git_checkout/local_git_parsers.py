# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Parse output of local git commands into Gitile response format."""

from collections import namedtuple
from collections import defaultdict
from datetime import datetime
import re

from libs import time_util
from libs.gitiles import commit_util
from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.diff import ChangeType

REGION_START_COUNT_PATTERN = re.compile(r'^(\S+) \d+ (\d+) (\d+)')

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

AUTHOR_NAME_PATTERN = re.compile(r'^author (.*)')
AUTHOR_MAIL_PATTERN = re.compile(r'^author-mail (\S+)')
AUTHOR_TIME_PATTERN = re.compile(r'^author-time (.+)')
AUTHOR_TIMEZONE_PATTERN = re.compile(r'^author-tz (.*)')

COMMITTER_NAME_PATTERN = re.compile(r'^committer (.*)')
COMMITTER_MAIL_PATTERN = re.compile(r'^committer-mail (\S+)')
COMMITTER_TIME_PATTERN = re.compile(r'^committer-time (.+)')

COMMIT_HASH_PATTERN = re.compile(r'^commit (\S+)')

MESSAGE_START_PATTERN = re.compile(r'^--Message start--')
MESSAGE_END_PATTERN = re.compile(r'^--Message end--')

# This pattern is for M, A, D.
CHANGED_FILE_PATTERN1 = re.compile(r':(\d+) (\d+) (\S+) (\S+) (\w)\s+(\S+)')
# This pattern is for R, C.
CHANGED_FILE_PATTERN2 = re.compile(
    r':(\d+) (\d+) (\S+) (\S+) ([A-Z0-9]*)\s+(\S+)\s(\S+)')

CHANGELOG_START_PATTERN = re.compile(r'^\*\*Changelog start\*\*')

INITIAL_TO_CHANGE_TYPE = {
    'M': ChangeType.MODIFY,
    'A': ChangeType.ADD,
    'D': ChangeType.DELETE,
    'C': ChangeType.COPY,
    'R': ChangeType.RENAME
}


class RegionInfo(namedtuple('RegionInfo', ['start', 'count', 'revision'])):
  __slots__ = ()
  def __new__(cls, start, count, revision):
    return super(cls, RegionInfo).__new__(cls, int(start), int(count), revision)


class GitParser(object):

  def __call__(self, output):
    raise NotImplementedError()


class GitBlameParser(GitParser):
  """Parses output of 'git blame --porcelain <rev> <file_path>'.

  For example:
  Git blame output of a Region is:
  ed268bfed3205347a90557c5029f37e90cc01956 18 18 3
  author test@google.com
  author-mail <test@google.com@2bbb7eff-a529-9590-31e7-b0007b416f81>
  author-time 1363032816
  author-tz +0000
  committer test@google.com
  committer-mail <test@google.com@2bbb7eff-a529-9590-31e7-b0007b416f81>
  committer-time 1363032816
  committer-tz +0000
  summary add (mac) test for ttcindex in SkFontStream
  previous fe7533eebe777cc66c7f8fa7a03f00572755c5b4 src/core/SkFontStream.h
  filename src/core/SkFontStream.h
               *  Return the number of shared directories.
  ed268bfed3205347a90557c5029f37e90cc01956 19 19
               *  if the stream is a normal sfnt (ttf). If there is an error or
  ed268bfed3205347a90557c5029f37e90cc01956 20 20
               *  no directory is found, return 0.

  Returns:
  A list of parsed Blame objects.
  """
  def __call__(self, output, path, revision):  # pylint:disable=W
    if not output:
      return None

    blame = Blame(revision, path)
    commit_info = defaultdict(dict)
    region_info = None
    for line in output.splitlines():
      # Sample: ec3ed6... 2 1 7.
      match = REGION_START_COUNT_PATTERN.match(line)
      if match:
        if region_info:
          blame.AddRegion(
              Region(region_info.start,
                     region_info.count,
                     region_info.revision,
                     commit_info[region_info.revision]['author_name'],
                     commit_info[region_info.revision]['author_email'],
                     commit_info[region_info.revision]['author_time']))

        region_info = RegionInfo(
            start = int(match.group(2)),
            count = int(match.group(3)),
            revision = match.group(1))

      elif region_info:
        # Sample: author test@google.com.
        if AUTHOR_NAME_PATTERN.match(line):
          commit_info[region_info.revision]['author_name'] = (
              AUTHOR_NAME_PATTERN.match(line).group(1))
        # Sample: author-mail <test@google.com@2eff-a529-9590-31e7-b00076f81>.
        elif AUTHOR_MAIL_PATTERN.match(line):
          commit_info[region_info.revision]['author_email'] = (
              commit_util.NormalizeEmail(
                  AUTHOR_MAIL_PATTERN.match(line).group(1).replace(
                      '<', '').replace('>', '')))
        # Sample: author-time 1311863160.
        elif AUTHOR_TIME_PATTERN.match(line):
          commit_info[region_info.revision]['author_time'] = (
              AUTHOR_TIME_PATTERN.match(line).group(1))
        # Sample: author-tz +0800.
        elif AUTHOR_TIMEZONE_PATTERN.match(line):
          time_zone = time_util.TimeZoneInfo(
              AUTHOR_TIMEZONE_PATTERN.match(line).group(1))
          commit_info[region_info.revision]['author_time'] = (
              time_zone.LocalToUTC(datetime.fromtimestamp(
                  int(commit_info[region_info.revision]['author_time']))))

    if region_info:
      blame.AddRegion(
          Region(region_info.start,
                 region_info.count,
                 region_info.revision,
                 commit_info[region_info.revision]['author_name'],
                 commit_info[region_info.revision]['author_email'],
                 commit_info[region_info.revision]['author_time']))

    return blame if blame else None


def GetChangeType(initial):
  """Gets Change type based on the initial character."""
  return INITIAL_TO_CHANGE_TYPE.get(initial[0])


def GetFileChangeInfo(change_type, path1, path2):
  """Set old/new path and old/new mode."""
  change_type = change_type.lower()
  if change_type == ChangeType.MODIFY:
    return FileChangeInfo.Modify(path1)

  if change_type == ChangeType.ADD:
    return FileChangeInfo.Add(path1)

  if change_type == ChangeType.DELETE:
    return FileChangeInfo.Delete(path1)

  if change_type == ChangeType.RENAME:
    return FileChangeInfo.Rename(path1, path2)

  # TODO(http://crbug.com/659346): write coverage test for this branch
  if change_type.lower() == ChangeType.COPY: # pragma: no cover
    return FileChangeInfo.Copy(path1, path2)

  return None


class GitChangeLogParser(GitParser):

  def __call__(self, output, repo_url):  # pylint:disable=W
    """Parses output of 'git log --pretty=format:<format>.

    For example:
    Git changelog output is:
    commit 21a8979218c096f4a96b07b67c9531f5f09e28a3
    tree 7d9a79c9b060c9a030abe20a8429d2b81ca1d4db
    parents 9640406d426a2d153b16e1d9ae7f9105268b36c9

    author Test
    author-email test@google.com
    author-time 2016-10-24 22:21:45

    committer Test
    committer-email test@google.com
    committer-time 2016-10-24 22:25:45

    --Message start--
    Commit messages...
    --Message end--

    :100644 100644 25f95f c766f1 M      src/a/delta/git_parsers.py

    Returns:
    Parsed ChangeLog object.
    """
    if not output:
      return None

    is_message_line = False
    info = {'author':{}, 'committer': {}, 'message': '', 'touched_files': []}
    for line in output.splitlines():
      if MESSAGE_START_PATTERN.match(line):
        is_message_line = True
        continue

      if MESSAGE_END_PATTERN.match(line):
        is_message_line = False
        # Remove the added '\n' at the end.
        info['message'] = info['message'][:-1]
        continue

      if is_message_line:
        info['message'] += line + '\n'
      elif COMMIT_HASH_PATTERN.match(line):
        info['revision'] = COMMIT_HASH_PATTERN.match(line).group(1)
      elif AUTHOR_NAME_PATTERN.match(line):
        info['author']['name'] = AUTHOR_NAME_PATTERN.match(line).group(1)
      elif AUTHOR_MAIL_PATTERN.match(line):
        info['author']['email'] = commit_util.NormalizeEmail(
            AUTHOR_MAIL_PATTERN.match(line).group(1))
      elif AUTHOR_TIME_PATTERN.match(line):
        info['author']['time'] = datetime.strptime(
            AUTHOR_TIME_PATTERN.match(line).group(1), DATETIME_FORMAT)
      elif COMMITTER_NAME_PATTERN.match(line):
        info['committer']['name'] = (
            COMMITTER_NAME_PATTERN.match(line).group(1))
      elif COMMITTER_MAIL_PATTERN.match(line):
        info['committer']['email'] = commit_util.NormalizeEmail(
            COMMITTER_MAIL_PATTERN.match(line).group(1))
      elif COMMITTER_TIME_PATTERN.match(line):
        info['committer']['time'] = datetime.strptime(
            COMMITTER_TIME_PATTERN.match(line).group(1), DATETIME_FORMAT)
      elif (CHANGED_FILE_PATTERN1.match(line) or
            CHANGED_FILE_PATTERN2.match(line)):
        match = (CHANGED_FILE_PATTERN1.match(line) or
                 CHANGED_FILE_PATTERN2.match(line))
        # For modify, add, delete, the pattern is like:
        # :100644 100644 df565d 6593e M modules/audio_coding/BUILD.gn
        # For rename, copy, the pattern is like:
        # :100644 100644 3f2e 20a5 R078 path1 path2
        info['touched_files'].append(
            GetFileChangeInfo(GetChangeType(match.group(5)),
                                            match.group(6),
                                            None if len(match.groups()) < 7
                                            else match.group(7)))

    # If commit is not parsed, the changelog will be {'author': {}, 'committer':
    # {}, 'message': ''}, return None instead.
    if not 'revision' in info:
      return None

    change_info = commit_util.ExtractChangeInfo(info['message'])
    info['commit_position'] = change_info.get('commit_position')
    info['code_review_url'] = change_info.get('code_review_url')
    info['reverted_revision'] = commit_util.GetRevertedRevision(
        info['message'])
    info['commit_url'] = '%s/+/%s' % (repo_url, info['revision'])

    return ChangeLog.FromDict(info)


class GitChangeLogsParser(GitParser):

  def __call__(self, output, repo_url):  # pylint:disable=W
    """Parses output of 'git log --pretty=format:<format> s_rev..e_rev'.

    For example:
    The output is:
    **Changelog start**
    commit 9af040a364c15bdc2adeea794e173a2c529a3ddc
    tree 27b0421273ed4aea25e497c6d26d9c7db6481852
    parents c39b0cc8a516de1fa57d032dc0135a4eadfe2c9e

    author author1
    author-mail author1@chromium.org
    author-time 2016-10-24 22:21:45

    committer Commit bot
    committer-mail commit-bot@chromium.org
    committer-time 2016-10-24 22:23:45

    --Message start--
    Message 1
    --Message end--

    :100644 100644 28e117 f12d3 M      tools/win32.txt


    **Changelog start**
    commit c39b0cc8a516de1fa57d032dc0135a4eadfe2c9e
    tree d22d3786e135b83183cfeba5f3d8913959f56299
    parents ac7ee4ce7b8d39b22a710c58d110e0039c11cf9a

    author author2
    author-mail author2@chromium.org
    author-time 2016-10-24 22:22:45

    committer Commit bot
    committer-mail commit-bot@chromium.org
    committer-time 2016-10-24 22:23:45

    --Message start--
    Message2
    --Message end--

    :100644 100644 7280f df186 M      tools/perf/benchmarks/memory_infra.py

    Returns:
    A list of parsed ChangeLog objects.
    """
    if not output:
      return None

    git_changelog_parser = GitChangeLogParser()

    changelog_str = ''
    changelogs = []
    for line in output.splitlines():
      if CHANGELOG_START_PATTERN.match(line):
        if not changelog_str:
          continue

        change_log = git_changelog_parser(changelog_str, repo_url)
        if change_log:
          changelogs.append(change_log)
        changelog_str = ''
      else:
        changelog_str += line + '\n'

    change_log = git_changelog_parser(changelog_str, repo_url)
    if change_log:
      changelogs.append(change_log)

    return changelogs


class GitDiffParser(GitParser):

  def __call__(self, output):
    """Returns the raw text output of 'git log --format="" --max-count=1'.

    For example:
    The output is like:

    diff --git a/chrome/print_header.js b/chrome/print_header.js
    index 51f25e7..4eec37f 100644
    --- a/chrome/browser/resources/print_preview/print_header.js
    +++ b/chrome/browser/resources/print_preview/print_header.js
    @@ -188,20 +188,25 @@ cr.define('print_preview', function() {
           var html;
           var label;
           if (numPages != numSheets) {
    -        html = loadTimeData.getStringF('printPreviewSummaryFormatLong',
    -                                       '<b>' + numSheets + '</b>',
    -                                       '<b>' + summaryLabel + '</b>',
    -                                       numPages,
    -                                       pagesLabel);
    +        html = loadTimeData.getStringF(
    +            'printPreviewSummaryFormatLong',
    +            '<b>' + numSheets.toLocaleString() + '</b>',
    +            '<b>' + summaryLabel + '</b>',
    +            numPages.toLocaleString(),
    +            pagesLabel);
             label = loadTimeData.getStringF('printPreviewSummaryFormatLong',
    -                                        numSheets, summaryLabel,
    -                                        numPages, pagesLabel);
    +                                        numSheets.toLocaleString(),
    +                                        summaryLabel,
    +                                        numPages.toLocaleString(),
    +                                        pagesLabel);
           } else {
    -        html = loadTimeData.getStringF('printPreviewSummaryFormatShort',
    -                                       '<b>' + numSheets + '</b>',
    -                                       '<b>' + summaryLabel + '</b>');
    +        html = loadTimeData.getStringF(
    +            'printPreviewSummaryFormatShort',
    +            '<b>' + numSheets.toLocaleString() + '</b>',
    +            '<b>' + summaryLabel + '</b>');
             label = loadTimeData.getStringF('printPreviewSummaryFormatShort',
    -                                        numSheets, summaryLabel);
    +                                        numSheets.toLocaleString(),
    +                                        summaryLabel);
           }
    """
    return output if output else None
