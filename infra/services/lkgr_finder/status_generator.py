# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Status generators to have easy views of lkgr_finder's internals."""


import textwrap
import urllib

from infra.services.lkgr_finder.lkgr_lib import STATUS


class StatusGeneratorStub(object):  # pragma: no cover

  def category_cb(self, category):
    pass

  def builder_cb(self, builder):
    pass

  def revision_cb(self, revision):
    pass

  def build_cb(self, category, builder, status, build_num=None):
    pass

  def lkgr_cb(self, revision):
    pass


class DebugStatusGenerator(StatusGeneratorStub):  # pragma: no cover

  def category_cb(self, category):
    print category

  def builder_cb(self, builder):
    print '  %s' % builder

  def revision_cb(self, revision):
    print '    %s' % revision

  def build_cb(self, category, builder, status, build_num=None):
    print '%s : %s : %s : %s' % (category, builder, build_num, status)

  def lkgr_cb(self, revision):
    print 'LKGR %s' % revision


class HTMLStatusGenerator(StatusGeneratorStub):  # pragma: no cover

  def __init__(self, viewvc, config):
    self.categories = []
    self.rows = []
    self.config = config
    self.viewvc = viewvc

  def category_cb(self, category):
    self.categories.append((category, []))

  def builder_cb(self, builder):
    self.categories[-1][1].append(builder)

  def revision_cb(self, revision):
    row = [
        revision,
        '<td class="revision"><a href="%s" target="_blank">%s</a></td>\n' % (
            self.viewvc % urllib.quote(revision), revision)]
    self.rows.append(row)

  def _get_luci_location(self, category):
    master_config = self.config.get('masters', {}).get(category)
    bucket_config = self.config.get('buckets', {}).get(category)
    if master_config:
      return (master_config.get('luci_project'),
              master_config.get('luci_bucket'))
    elif bucket_config:
      luci_project, luci_bucket = category.split('/', 1)
      old_style_luci_bucket = 'luci.%s.%s' % (luci_project, luci_bucket)
      return (luci_project, old_style_luci_bucket)
    return (None, None)


  def build_cb(self, category, builder, status, build_num=None):
    stat_txt = STATUS.tostr(status)
    cell = '  <td class="%s">' % stat_txt
    if build_num is not None:
      luci_project, luci_bucket = self._get_luci_location(category)
      if luci_project and luci_bucket:
        build_url = 'ci.chromium.org/p/%s/builders/%s/%s/%s' % (
            luci_project, luci_bucket, builder, build_num)
      else:
        build_url = 'build.chromium.org/p/%s/builders/%s/builds/%s' % (
            category, builder, build_num)
      cell += '<a href="http://%s" target="_blank">X</a>' % (
          urllib.quote(build_url))
    cell += '</td>\n'
    self.rows[-1].append(cell)

  def lkgr_cb(self, revision):
    row = self.rows[-1]
    row[1] = row[1].replace('class="revision"', 'class="lkgr"', 1)
    for i in range(2, len(row)):
      row[i] = row[i].replace('class="success"', 'class="lkgr"', 1)

  def generate(self):
    html_chunks = [textwrap.dedent("""
        <html>
        <head>
        <style type="text/css">
        table { border-collapse: collapse; }
        th { font-size: xx-small; }
        td, th { text-align: center; }
        .header { border: 1px solid black; }
        .revision { padding-left: 5px; padding-right: 5px; }
        .revision { border-left: 1px solid black; border-right: 1px solid black; }
        .success { background-color: #8d4; }
        .failure { background-color: #e88; }
        .running { background-color: #fe1; }
        .unknown { background-color: #ddd; }
        .lkgr { background-color: #4af; }
        .roll { border-top: 2px solid black; }
        </style>
        </head>
        <body><table>
        """)]
    category_headers = ['<tr class="header"><th></th>\n']
    builder_headers = ['<tr class="header">']
    builder_headers.append('<th>chromium revision</th>\n')
    for category, builders in self.categories:
      hdr = '  <th colspan="%d" class="header">%s</th>' % (
          len(builders), category)
      category_headers.append(hdr)
      for builder in builders:
        luci_project, luci_bucket = self._get_luci_location(category)
        if luci_project and luci_bucket:
          builder_url = 'ci.chromium.org/p/%s/builders/%s/%s' % (
              luci_project, luci_bucket, builder)
        else:
          builder_url = 'build.chromium.org/p/%s/builders/%s' % (
              category, builder)
        hdr = '  <th><a href="%s" target="_blank">%s</a></th>\n' % (
            'http://%s' % urllib.quote(builder_url), builder)
        builder_headers.append(hdr)
    category_headers.append('</tr>\n')
    builder_headers.append('</tr>\n')
    html_chunks.extend(category_headers)
    html_chunks.extend(builder_headers)
    for row in self.rows:
      html_chunks.extend(row[1:])
      html_chunks.append('</tr>\n')
    html_chunks.append('</table></body></html>\n')
    return ''.join(html_chunks)
