# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import with_statement

import datetime
import json
import logging
import os
import random
import re
import string
import urllib

from google.appengine.api import files, memcache, urlfetch
from google.appengine.api.app_identity import get_application_id
from google.appengine.ext import blobstore, db, deferred
# F0401: 16,0: Unable to import 'webapp2_extras'
# W0611: 16,0: Unused import jinja2
# pylint: disable=F0401, W0611
from webapp2_extras import jinja2
# F0401:22,0: Unable to import 'jinja2'
# pylint: disable=F0401
from jinja2 import Environment, FileSystemLoader

from third_party.BeautifulSoup.BeautifulSoup import BeautifulSoup


# Current application name.
APP_NAME = get_application_id()

# Deadline for fetching URLs (in seconds).
URLFETCH_DEADLINE = 60*5  # 5 mins


# Perform initial bootstrap for this module.
console_template = ''
def bootstrap():
  global console_template
  with open('templates/merger.html', 'r') as fh:
    console_template = fh.read()


def get_pagedata_from_cache(localpath):
  memcache_data = memcache.get(localpath)
  if not memcache_data:
    return None
  logging.debug('content for %s found in memcache' % localpath)
  return json.loads(memcache_data)


def put_pagedata_into_cache(localpath, page_data):
  memcache_data = json.dumps(page_data)
  if not memcache.set(key=localpath, value=memcache_data, time=2*60):
    logging.error('put_pagedata_into_cache(\'%s\'): memcache.set() failed' % (
        localpath))


def get_and_cache_pagedata(localpath):
  """Returns a page_data dict, optionally caching and looking up a blob.

  get_and_cache_pagedata takes a localpath which is used to fetch data
  from the cache.  If the data is present and there's no content blob,
  then we have all of the data we need to return a page view to the user
  and we return early.

  Otherwise, we need to fetch the page object and set up the page data
  for the page view.  If the page has a blob associated with it, then we
  mark the page data as having a blob and cache it as-is without the blob.
  If there's no blob, we associate the content with the page data and
  cache that.  This is so the next time get_and_cache_pagedata is called
  for either case, we'll get the same behavior (a page-lookup for blobful
  content and a page cache hit for blobless content).

  Here we assume localpath is already unquoted.
  """
  page_data = get_pagedata_from_cache(localpath)
  if page_data and not page_data.get('content_blob'):
    return page_data
  page = Page.all().filter('localpath =', localpath).get()
  if not page:
    logging.error('get_and_cache_pagedata(\'%s\'): no matching localpath in '
        'datastore' % localpath)
    return {'content': None}
  page_data = {
    'body_class': page.body_class,
    'offsite_base': page.offsite_base,
    'title': page.title,
  }
  if page.content_blob:
    # Get the blob.
    logging.debug('content for %s found in blobstore' % localpath)
    blob_reader = blobstore.BlobReader(page.content_blob)
    page_data['content_blob'] = True
    put_pagedata_into_cache(localpath, page_data)
    page_data['content'] = blob_reader.read().decode('utf-8', 'replace')
  else:
    logging.debug('content for %s found in datastore' % localpath)
    page_data['content'] = page.content
    put_pagedata_into_cache(localpath, page_data)
  return page_data


class ConsoleData(object):
  def __init__(self):
    self.row_orderedkeys = []
    self.row_data = {}

    # Retain order of observed masters.
    self.masters = []

    # Map(k,v): k=Master, v=List of categories
    self.category_order = {}
    # Map(k,v): k=Master, v=Dict of category data
    self.category_data = {}

    self.category_count = 0
    self.master = ''
    self.lastRevisionSeen = None
    self.lastMasterSeen = None

  @staticmethod
  def ContentsToHtml(contents):
    return ''.join([str(content) for content in contents])

  @property
  def last_row(self):
    return self.row_data[self.lastRevisionSeen]

  def SawMaster(self, master):
    self.lastMasterSeen = master
    assert(self.lastMasterSeen not in self.category_order)
    self.masters.append(self.lastMasterSeen)
    self.category_order.setdefault(self.lastMasterSeen, [])
    self.category_data.setdefault(self.lastMasterSeen, {})

  def SawRevision(self, revision):
    self.lastRevisionSeen = revision
    # TODO(cmp): Fix the order of the revision data in self.row_orderedkeys
    if self.lastRevisionSeen not in self.row_orderedkeys:
      logging.debug('SawRevision: guessing at row ordering')
      self.row_orderedkeys.append(self.lastRevisionSeen)
    self.row_data.setdefault(self.lastRevisionSeen, {})
    self.last_row.setdefault('status', {})
    self.last_row['status'].setdefault(self.lastMasterSeen, {})

  def SetLink(self, revlink):
    self.last_row['revlink'] = revlink

  def SetName(self, who):
    self.last_row['who'] = who

  def SetStatus(self, category, status):
    self.last_row['status'][self.lastMasterSeen][category] = status

  def SetComment(self, comment):
    self.last_row['comment'] = comment

  def SetDetail(self, detail):
    self.last_row['detail'] = detail

  def AddCategory(self, category, builder_status):
    self.category_order[self.lastMasterSeen].append(category)
    # Map(k,v): k=Master/category, v=Dict of category data (last build status)
    self.category_data[self.lastMasterSeen].setdefault(category, {})
    self.category_data[self.lastMasterSeen][category] = builder_status
    self.category_count += 1

  def ParseRow(self, row):
    cells = row.findAll('td', recursive=False)
    # Figure out which row this is.
    for attrname, attrvalue in cells[0].attrs:
      if attrname != 'class':
        continue
      attrvalue = re.sub(r'^(\S+).*', r'\1', attrvalue)
      if attrvalue == 'DevRev':
        revision = cells[0]
        self.SawRevision(revision=revision.findAll('a')[0].contents[0])
        self.SetLink(revlink=revision.findAll('a')[0].attrs[0][1])
        nameparts = cells[1].contents
        self.SetName(who=re.sub(r'^\s+(.*)\s*$',
                                r'\1',
                                self.ContentsToHtml(nameparts)))
        for i, bs in enumerate(cells[2:]):
          self.SetStatus(category=self.category_order[self.lastMasterSeen][i],
                         status=str(bs.findAll('table', recursive=False)[0]))
      if attrvalue == 'DevComment':
        self.SetComment(comment=self.ContentsToHtml(cells[0].contents))
      if attrvalue == 'DevDetails':
        self.SetDetail(detail=self.ContentsToHtml(cells[0].contents))

  def Finish(self):
    self.row_orderedkeys = sorted(self.row_orderedkeys, key=int, reverse=True)
    # TODO(cmp): Look for row/master/categories that are unset.  If they are
    #            at the latest revisions, leave them unset.  If they are at
    #            the earliest revisions, set them to ''.


# W0613:169,39:console_merger: Unused argument 'remoteurl'
# W0613:169,19:console_merger: Unused argument 'unquoted_localpath'
# pylint: disable=W0613
def console_merger(unquoted_localpath, remote_url, page_data=None):
  page_data = page_data or {}

  masters = [
    'chromium.main',
    'chromium.chromiumos',
    'chromium.chrome',
    'chromium.memory',
  ]
  mergedconsole = ConsoleData()
  merged_page = None
  merged_tag = None
  fetch_timestamp = datetime.datetime.now()
  for master in masters:
    page_data = get_and_cache_pagedata('%s/console' % master)
    master_content = page_data['content']
    if master_content is None:
      continue
    master_content = master_content.encode('ascii', 'replace')
    this_page = BeautifulSoup(master_content)
    this_tag = this_page.find('table', {'class': 'ConsoleData'})
    # The first console is special, we reuse all of the console page.
    if not merged_page:
      merged_page = this_page
      merged_tag = this_tag
    mergedconsole.SawMaster(master)

    # Parse each of the rows.
    CATEGORY_ROW = 0
    trs = this_tag.findAll('tr', recursive=False)

    # Get the list of categories in |master|.
    category_tds = trs[CATEGORY_ROW].findAll('td', recursive=False)[2:]
    third_cell = category_tds[0]
    third_cell_class = third_cell.attrs[0][1]
    categories = []
    if third_cell_class.startswith('DevStatus '):
      BUILDER_STATUS_ROW = 2
      FIRST_CL_ROW = 3
      for index, category_td in enumerate(category_tds):
        categories.append(category_td.contents[0].strip())
    else:
      # There's no categories + spacing row, the first row will be the builder
      # status row.
      categories.append('')
      BUILDER_STATUS_ROW = 0
      FIRST_CL_ROW = 1

    # For each category in |master|, add the category plus its |builder_status|.
    builder_tds = trs[BUILDER_STATUS_ROW].findAll('td', recursive=False)[2:]
    for index, category in enumerate(categories):
      builder_status = builder_tds[index].findAll('table', recursive=False)[0]
      mergedconsole.AddCategory(category=category,
                                builder_status=builder_status)

    # For each of the remaining rows, add them to the console data.
    for console_index in range(FIRST_CL_ROW, len(trs)):
      console_row = trs[console_index]
      mergedconsole.ParseRow(console_row)
  # Add GC memory profiling.
  # import gc
  # gc.set_debug(gc.DEBUG_LEAK)
  # logging.debug(gc.garbage)
  # del gc.garbage[:]
  mergedconsole.Finish()

  # Convert the merged content into console content.
  template_environment = Environment()
  template_environment.loader = FileSystemLoader('.')
  def notstarted(builder_status):
    """Convert a BeautifulSoup Tag from builder status to a notstarted line."""
    builder_status = re.sub(r'DevSlaveBox', 'DevStatusBox', str(builder_status))
    builder_status = re.sub(r'class=\'([^\']*)\' target=',
                            'class=\'DevStatusBox notstarted\' target=',
                            builder_status)
    builder_status = re.sub(r'class="([^"]*)" target=',
                            'class="DevStatusBox notstarted" target=',
                            builder_status)
    return builder_status
  template_environment.filters['notstarted'] = notstarted
  merged_template = template_environment.from_string(console_template)
  merged_content = merged_template.render(data=mergedconsole)
  # For debugging:
  # print merged_content
  # import code
  # code.interact(local=locals())

  # Place merged data at |merged_tag|'s location in |merged_page|, and put the
  # result in |merged_content|.
  merged_tag.replaceWith(str(merged_content))
  # .prettify() may damage the HTML but makes output more nice.  However, that
  # cost is a bunch of extra whitespace.  We reduce page size by not using
  # .prettify().
  merged_content = str(merged_page)
  merged_content = re.sub(
      r'\'\<a href="\'', '\'<a \' + attributes + \' href="\'', merged_content)
  merged_content = re.sub(
      r'\'\<table\>\'', r"'<table ' + attributes + '>'", merged_content)
  merged_content = re.sub(
      r'\'\<div\>\'', r"'<div ' + attributes + '>'", merged_content)
  merged_content = re.sub(
      r'\'\<td\>\'', r"'<td ' + attributes + '>'", merged_content)
  merged_content = re.sub(
      r'\<iframe\>\</iframe\>',
      '<iframe \' + attributes + \' src="\' + url + \'"></iframe>',
      merged_content)

  # Update the merged console page.
  merged_page = get_or_create_page('chromium/console', None, maxage=30)
  logging.debug('console_merger: saving merged console')
  page_data['title'] = 'BuildBot: Chromium'
  page_data['offsite_base'] = 'http://build.chromium.org/p/chromium'
  page_data['body_class'] = 'interface'
  page_data['content'] = merged_content
  save_page(merged_page, 'chromium/console', fetch_timestamp, page_data)
  return


def console_handler(_unquoted_localpath, remoteurl, page_data=None):
  page_data = page_data or {}
  content = page_data.get('content')
  if not content:
    return page_data

  # Decode content from utf-8 to unicode, replacing bad characters.
  content = content.decode('utf-8', 'replace')

  # Scrub in sheriff file content to console.
  sheriff_files = [
    'sheriff',
    'sheriff_android',
    'sheriff_cr_cros_gardeners',
    'sheriff_cros_mtv',
    'sheriff_cros_nonmtv',
    'sheriff_gpu',
    'sheriff_memory',
    'sheriff_nacl',
    'sheriff_perf',
    'sheriff_webkit',
  ]
  for sheriff_file in sheriff_files:
    sheriff_page_data = get_and_cache_pagedata('chromium/%s.js' % sheriff_file)
    sheriff_content = sheriff_page_data['content']
    console_re = (r'<script src=\'http://chromium-build.appspot.com/'
                   'p/chromium/%s.js\'></script>')
    content = re.sub(console_re % sheriff_file,
                     '<script>%s</script>' % sheriff_content, content)

  # Replace showBuildBox with direct links.
  content = re.sub(r'<a href=\'#\' onclick=\'showBuildBox\(\"./(.+)\", event\);'
                    ' return false;\'',
                   r"<a href='\1'", content)

  # Create a string representing the parent of remoteurl.  If remoteurl looks
  # like 'http://somehost/somepath/foo', then remoteurl_parent would be
  # 'http://somehost/somepath/'.
  remoteurl_parent = re.sub(r'^(.*?)[^/]*$', r'\1', remoteurl)

  # JavaScript can bring about text that looks like <a href="' + ..., so our
  # regex needs to avoid introducing a new base URL in those cases.  Hence we
  # exclude single and double quotes in both cases.
  content = re.sub(r'<a href="([^:\"\'\$]+)"',
                   r'<a href="%s\1"' % remoteurl_parent,
                   content)
  content = re.sub(r'<a href=\'([^:\'\"\$]+)\'',
                   r"<a href='%s\1'" % remoteurl_parent,
                   content)

  # Convert any occurrences of ['"]./ and ['"]../ to prepend b.c.o.
  content = re.sub(r'"\./', r'"%s' % remoteurl_parent, content)
  content = re.sub(r"'\./", r"'%s" % remoteurl_parent, content)
  content = re.sub(r'"\.\./', r'"%s../' % remoteurl_parent, content)
  content = re.sub(r"'\.\./", r"'%s../" % remoteurl_parent, content)

  # Convert the webkit waterfall reference to reuse the local instance.
  content = re.sub(r"c.webkit = '([^\']+)'", r"c.webkit = ''", content)
  content = re.sub("'http://build\.chromium.org/p/chromium\.webkit/"
                   "horizontal_one_box_per_builder'",
                   "'https://chromium-build.appspot.com/p/"
                   "chromium.webkit/horizontal_one_box_per_builder"
                   "?chromiumconsole'", content)

  # Convert the chromium-status reference to reuse the local instance.
  content = re.sub(r"http://chromium-status\.appspot\.com/current",
                   "https://chromium-build.appspot.com/p/"
                   "chromium-status/current", content)

  # Disable the personalized for box for now.
  content = re.sub(r"<input id='namebox", r"<!-- <input id='namebox", content)
  content = re.sub(r"reload_page\(\)'/>", r"reload_page()'/> -->", content)

  # Replace lkgrPath with a URL to chromium-build.
  content = re.sub(
      "var lkgrPath = c.status_lkgr",
      "var lkgrPath = '/p/chromium.lkgr'",
      content)
  content = string.replace(content,
      "'/json/builders/Linux%20x64/builds/-1?as_text=1';",
      "'/json/builders/Linux%20x64/builds/-1/as_text=1.json';")

  # Fix up a reference to http chromium-build in BarUrl().
  content = string.replace(content,
      "return 'http://chromium-build.appspot.com/p/'",
      "return 'https://chromium-build.appspot.com/p/'")

  # Encode content from unicode to utf-8.
  page_data['content'] = content.encode('utf-8')

  # Last tweaks to HTML, plus extracting metadata about the page itself.
  page_data['offsite_base'] = remoteurl + '/../'

  # Extract the title from the page.
  md = re.search(
      r'^.*<title>([^\<]+)</title>',
      page_data['content'],
      re.MULTILINE|re.DOTALL)
  if not md:
    raise Exception('failed to locate title in page')
  page_data['title'] = md.group(1)

  # Remove the leading text up to the end of the opening body tag.  While
  # there, extract the body_class from the page.
  md = re.search(
      r'^.*<body class="(\w+)\">(.*)$',
      page_data['content'],
      re.MULTILINE|re.DOTALL)
  if not md:
    raise Exception('failed to locate leading text up to body tag')
  page_data['body_class'] = md.group(1)
  page_data['content'] = md.group(2)

  # Remove the leading div and hr tags.
  md = re.search(
      r'^.*?<hr/>(.*)$',
      page_data['content'],
      re.MULTILINE|re.DOTALL)
  if not md:
    raise Exception('failed to locate leading div and hr tags')
  page_data['content'] = md.group(1)

  # Strip the trailing body and html tags.
  md = re.search(
      r'^(.*)</body>.*$',
      page_data['content'],
      re.MULTILINE|re.DOTALL)
  if not md:
    raise Exception('failed to locate trailing body and html tags')
  page_data['content'] = md.group(1)

  return page_data


def one_box_handler(unquoted_localpath, remoteurl, page_data=None):
  page_data = page_data or {}
  content = page_data.get('content')
  if content is None:
    return page_data
  # Get the site name from the local path.
  md = re.match('^([^\/]+)/.*$', unquoted_localpath)
  if not md:
    logging.error('one_box_handler(\'%s\', \'%s\', \'%s\'): cannot get site '
                  'from local path' % (
                      unquoted_localpath, remoteurl, page_data))
    return page_data
  site = md.group(1)
  new_waterfall_url = 'http://build.chromium.org/p/%s/waterfall' % site
  page_data['content'] = re.sub(
      r'waterfall',
      new_waterfall_url,
      page_data['content'])
  return page_data



# List of URLs to fetch.
URLS = [
  # Console URLs.
  {
    'remoteurl': 'http://build.chromium.org/p/chromium/console',
    'localpath': 'chromium.main/console',
    'postfetch': console_handler,
    'postsave': console_merger,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.chrome/console',
    'localpath': 'chromium.chrome/console',
    'postfetch': console_handler,
    'postsave': console_merger,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.chromiumos/console',
    'localpath': 'chromium.chromiumos/console',
    'postfetch': console_handler,
    'postsave': console_merger,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.memory/console',
    'localpath': 'chromium.memory/console',
    'postfetch': console_handler,
    'postsave': console_merger,
    'maxage': 30,  # 30 secs
  },

  # Tree status URL.
  {
    'remoteurl': 'http://chromium-status.appspot.com/current',
    'localpath': 'chromium-status/current',
    'maxage': 30,  # 30 secs
  },

  # Static resources.
  {
    'remoteurl': 'http://build.chromium.org/p/chromium/default.css',
    'localpath': 'chromium/default.css',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.chrome/default.css',
    'localpath': 'chromium.chrome/default.css',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.chromiumos/default.css',
    'localpath': 'chromium.chromiumos/default.css',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.gpu/default.css',
    'localpath': 'chromium.gpu/default.css',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.gpu.fyi/default.css',
    'localpath': 'chromium.gpu.fyi/default.css',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.lkgr/default.css',
    'localpath': 'chromium.lkgr/default.css',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.memory/default.css',
    'localpath': 'chromium.memory/default.css',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.memory.fyi/default.css',
    'localpath': 'chromium.memory.fyi/default.css',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.perf/default.css',
    'localpath': 'chromium.perf/default.css',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.pyauto/default.css',
    'localpath': 'chromium.pyauto/default.css',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromebot/default.css',
    'localpath': 'chromebot/default.css',
    'maxage': 15*60,  # 15 mins
  },

  # Sheriff URLs.
  {
    'remoteurl': 'http://build.chromium.org/p/chromium/sheriff.js',
    'localpath': 'chromium/sheriff.js',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium/sheriff_android.js',
    'localpath': 'chromium/sheriff_android.js',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl':
        'http://build.chromium.org/p/chromium/sheriff_cr_cros_gardeners.js',
    'localpath': 'chromium/sheriff_cr_cros_gardeners.js',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium/sheriff_cros_mtv.js',
    'localpath': 'chromium/sheriff_cros_mtv.js',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium/sheriff_cros_nonmtv.js',
    'localpath': 'chromium/sheriff_cros_nonmtv.js',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium/sheriff_gpu.js',
    'localpath': 'chromium/sheriff_gpu.js',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium/sheriff_memory.js',
    'localpath': 'chromium/sheriff_memory.js',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium/sheriff_nacl.js',
    'localpath': 'chromium/sheriff_nacl.js',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium/sheriff_perf.js',
    'localpath': 'chromium/sheriff_perf.js',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium/sheriff_webkit.js',
    'localpath': 'chromium/sheriff_webkit.js',
    'maxage': 15*60,  # 15 mins
  },

  # Buildbot "One Boxes".
  {
    'remoteurl':
        ('http://build.chromium.org/p/chromebot/horizontal_one_box_per_builder?'
         'builder=Win+Chromebot+Server&builder=Linux+Chromebot+Server&'
         'builder=Mac+Chromebot+Server'),
    'localpath':
        ('chromebot/horizontal_one_box_per_builder?'
         'builder=Win+Chromebot+Server&builder=Linux+Chromebot+Server&'
         'builder=Mac+Chromebot+Server'),
    'postfetch': one_box_handler,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl':
        'http://build.chromium.org/p/chromium/horizontal_one_box_per_builder',
    'localpath': 'chromium/horizontal_one_box_per_builder',
    'postfetch': one_box_handler,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl':
        ('http://build.chromium.org/p/chromium.chrome/'
         'horizontal_one_box_per_builder'),
    'localpath': 'chromium.chrome/horizontal_one_box_per_builder',
    'postfetch': one_box_handler,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl':
        ('http://build.chromium.org/p/chromium.chromiumos/'
         'horizontal_one_box_per_builder'),
    'localpath': 'chromium.chromiumos/horizontal_one_box_per_builder',
    'postfetch': one_box_handler,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl':
        ('http://build.chromium.org/p/chromium.gpu/'
         'horizontal_one_box_per_builder'),
    'localpath': 'chromium.gpu/horizontal_one_box_per_builder',
    'postfetch': one_box_handler,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl':
        ('http://build.chromium.org/p/chromium.gpu.fyi/'
         'horizontal_one_box_per_builder'),
    'localpath': 'chromium.gpu.fyi/horizontal_one_box_per_builder',
    'postfetch': one_box_handler,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl':
        ('http://build.chromium.org/p/chromium.lkgr/'
         'horizontal_one_box_per_builder'),
    'localpath': 'chromium.lkgr/horizontal_one_box_per_builder',
    'postfetch': one_box_handler,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl':
        ('http://build.chromium.org/p/chromium.memory/'
         'horizontal_one_box_per_builder'),
    'localpath': 'chromium.memory/horizontal_one_box_per_builder',
    'postfetch': one_box_handler,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl':
        ('http://build.chromium.org/p/chromium.memory.fyi/'
         'horizontal_one_box_per_builder'),
    'localpath': 'chromium.memory.fyi/horizontal_one_box_per_builder',
    'postfetch': one_box_handler,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl':
        ('http://build.chromium.org/p/chromium.perf/'
         'horizontal_one_box_per_builder'),
    'localpath': 'chromium.perf/horizontal_one_box_per_builder',
    'postfetch': one_box_handler,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl':
        ('http://build.chromium.org/p/chromium.pyauto/'
         'horizontal_one_box_per_builder'),
    'localpath': 'chromium.pyauto/horizontal_one_box_per_builder',
    'postfetch': one_box_handler,
    'maxage': 30,  # 30 secs
  },

  # LKGR JSON.
  {
    'remoteurl':
        ('http://build.chromium.org/p/chromium.lkgr/json/builders/Linux%20x64/'
         'builds/-1?as_text=1'),
    'localpath':
        'chromium.lkgr/json/builders/Linux%20x64/builds/-1/as_text=1.json',
    'maxage': 2*60,  # 2 mins
  },
]


def nonfatal_fetch_url(url, *args, **kwargs):
  # Temporary workaround to disable AppEngine global cache of these pages.
  if '?' in url:
    url += '&' + str(random.random())
  else:
    url += '?' + str(random.random())

  try:
    return urlfetch.fetch(url, deadline=URLFETCH_DEADLINE, *args, **kwargs)
  except urlfetch.DownloadError:
    logging.warn('urlfetch failed: %s' % url, exc_info=1)
    return None


class Page(db.Model):
  fetch_timestamp = db.DateTimeProperty(required=True)
  localpath = db.StringProperty(required=True)
  content = db.TextProperty()
  title = db.StringProperty()
  offsite_base = db.StringProperty()
  body_class = db.StringProperty()
  remoteurl = db.TextProperty()
  # Data updated separately, after creation.
  content_blob = blobstore.BlobReferenceProperty()


def write_blob(data, mime_type):
  """Saves a Unicode string as a new blob, returns the blob's key."""
  file_name = files.blobstore.create(mime_type=mime_type)
  data = data.encode('utf-8')
  with files.open(file_name, 'a') as blob_file:
    blob_file.write(data)
  files.finalize(file_name)
  return files.blobstore.get_blob_key(file_name)


def save_page(page, localpath, fetch_timestamp, page_data):
  body_class = page_data.get('body_class', '')
  content = page_data.get('content')
  offsite_base = page_data.get('offsite_base', '')
  title = page_data.get('title', '')

  content_blob_key = None
  try:
    content = content.decode('utf-8', 'replace')
  except UnicodeEncodeError:
    logging.debug('save_page: content was already in unicode')
  logging.debug('save_page: content size is %d' % len(content))
  if len(content.encode('utf-8')) >= 1024*1024:
    logging.debug('save_page: saving to blob')
    content_blob_key = write_blob(content, path_to_mime_type(localpath))
    content = None
  def tx_page(page_key):
    page = Page.get(page_key)
    # E1103:225,7:fetch_page.tx_page: Instance of 'list' has no
    # 'fetch_timestamp' member (but some types could not be inferred)
    # pylint: disable=E1103
    if page.fetch_timestamp > fetch_timestamp:
      return
    page.content = content
    page.content_blob = content_blob_key
    page.fetch_timestamp = fetch_timestamp
    # title, offsite_base, body_class can all be empty strings for some
    # content.  Where that's true, they're not used for displaying a console-
    # like resource, and the content alone is returned to the web user.
    page.title = title
    page.offsite_base = offsite_base
    page.body_class = body_class
    # E1103:231,4:fetch_page.tx_page: Instance of 'list' has no 'put' member
    # (but some types could not be inferred)
    # pylint: disable=E1103
    page.put()
  db.run_in_transaction(tx_page, page.key())
  page_data = {
    'body_class': body_class,
    'content': content,
    'offsite_base': offsite_base,
    'title': title,
  }
  if content_blob_key:
    page_data['content_blob'] = True
  put_pagedata_into_cache(localpath, page_data)


def get_or_create_page(localpath, remoteurl, maxage):
  return Page.get_or_insert(
    key_name=localpath,
    localpath=localpath,
    remoteurl=remoteurl,
    maxage=maxage,
    fetch_timestamp=datetime.datetime.now() - datetime.timedelta(hours=24),
    content=None,
    content_blob=None)


def fetch_page(localpath, remoteurl, maxage, postfetch=None, postsave=None,
               fetch_url=nonfatal_fetch_url):
  """Fetches data about a set of pages."""
  if type(localpath) != type(''):
    logging.error('fetch_page: localpath is %r, expected a string' % (
        repr(localpath)))
    return
  unquoted_localpath = urllib.unquote(localpath)
  logging.debug('fetch_page("%s", "%s", "%s")' % (
      unquoted_localpath, remoteurl, maxage))
  page = get_or_create_page(unquoted_localpath, remoteurl, maxage)

  # Check if our copy of the page is younger than maxage.  If it is, we'll
  # skip the fetch.
  oldest_acceptable_timestamp = datetime.datetime.now() - datetime.timedelta(
      seconds=maxage)
  if (page.fetch_timestamp and
      page.fetch_timestamp > oldest_acceptable_timestamp):
    logging.debug('fetch_page: too recent, skipping')
    return

  # Perform the actual page fetch.
  fetch_timestamp = datetime.datetime.now()
  response = fetch_url(remoteurl)
  if not response:
    logging.warning('fetch_page: got empty response')
    return
  if response.status_code != 200:
    logging.warning('fetch_page: got non-empty response but code '
                    '%d' % response.status_code)
    return

  # We have actual content.  If there's one or more handlers, call them.
  page_data = {}
  page_data['content'] = response.content
  if postfetch:
    if not isinstance(postfetch, list):
      postfetch = [postfetch]
    for handler in postfetch:
      logging.debug('fetch_page: calling postfetch handler '
                    '%s' % handler.__name__)
      page_data = handler(unquoted_localpath, remoteurl, page_data)

  # Save the returned content into the DB and caching layers.
  logging.debug('fetch_page: saving page')
  save_page(page, unquoted_localpath, fetch_timestamp, page_data)
  if postsave:
    if not isinstance(postsave, list):
      postsave = [postsave]
    for handler in postsave:
      logging.debug('fetch_page: calling postsave handler '
                    '%s' % handler.__name__)
      handler(unquoted_localpath, remoteurl, page_data)


EXT_TO_MIME = {
  '.css': 'text/css',
  '.js': 'text/javascript',
  '.json': 'application/json',
  '.html': 'text/html',
}


def path_to_mime_type(path):
  return EXT_TO_MIME.get(os.path.splitext(path)[1], 'text/html')


def fetch_pages():
  """Starts a background fetch operation for pages that need it."""
  logging.debug('fetch_pages()')
  for url in URLS:
    deferred.defer(fetch_page, **url)
