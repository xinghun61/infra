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
from google.appengine.ext import blobstore, db, deferred
# F0401: 16,0: Unable to import 'webapp2_extras'
# W0611: 16,0: Unused import jinja2
# pylint: disable=F0401, W0611
from webapp2_extras import jinja2
# F0401:22,0: Unable to import 'jinja2'
# pylint: disable=F0401
from jinja2 import Environment, FileSystemLoader

from third_party.BeautifulSoup.BeautifulSoup import BeautifulSoup, Tag


# pylint: disable=no-value-for-parameter


# Deadline for fetching URLs (in seconds).
URLFETCH_DEADLINE = 60*5  # 5 mins

# Default masters to merge together.
DEFAULT_MASTERS_TO_MERGE = [
  'chromium.main',
  'chromium.win',
  'chromium.mac',
  'chromium.linux',
  'chromium.chromiumos',
  'chromium.chrome',
  'chromium.memory',
]


# Perform initial bootstrap for this module.
console_template = ''
def bootstrap():
  global console_template
  merger_file = os.path.join(os.path.dirname(__file__), 'templates/merger.html')
  with open(merger_file, 'r') as fh:
    console_template = fh.read()


##########
# Page class definition and related functions.
##########
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


def get_or_create_page(localpath, remoteurl, maxage):
  return Page.get_or_insert(
    key_name=localpath,
    localpath=localpath,
    remoteurl=remoteurl,
    maxage=maxage,
    # The real timestamp and content will be filled when the page is saved.
    fetch_timestamp=datetime.datetime.min,
    content=None,
    content_blob=None)


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
  page_data = get_data_from_cache(localpath)
  if page_data and not page_data.get('content_blob'):
    logging.debug('content for %s found in cache' % localpath)
    return page_data
  page = Page.all().filter('localpath =', localpath).get()
  if not page:
    logging.debug('get_and_cache_pagedata(\'%s\'): no matching localpath in '
        'datastore' % localpath)
    return {'content': None}
  page_data = {
    'body_class': page.body_class,
    'offsite_base': page.offsite_base,
    'title': page.title,
    'fetch_timestamp': page.fetch_timestamp,
  }
  if page.content_blob:
    # Get the blob.
    logging.debug('content for %s found in blobstore' % localpath)
    blob_reader = blobstore.BlobReader(page.content_blob)
    page_data['content_blob'] = True
    page_data['content'] = blob_reader.read().decode('utf-8', 'replace')
  else:
    logging.debug('content for %s found in datastore' % localpath)
    page_data['content'] = page.content
    put_data_into_cache(localpath, page_data)
  return page_data


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
  # Save to blobstore if content + metadata is too big.
  json_data = json.dumps(content.encode('utf-8'), default=dtdumper)
  if len(json_data) >= 10**6 - 10**5:
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
    'fetch_timestamp': fetch_timestamp,
  }
  if content_blob_key:
    page_data['content_blob'] = True
  put_data_into_cache(localpath, page_data)
  logging.info('Saved and cached page with localpath %s' % localpath)


##########
# Row class definition and related functions.
##########
class Row(db.Model):
  fetch_timestamp = db.DateTimeProperty(required=True)
  rev_number = db.StringProperty(required=True)
  localpath = db.StringProperty(required=True)
  revision = db.TextProperty()
  name = db.TextProperty()
  status = db.TextProperty()
  comment = db.TextProperty()
  details = db.TextProperty()


def get_or_create_row(localpath, revision):
  return Row.get_or_insert(
    key_name=localpath,
    rev_number=revision,
    localpath=localpath,
    fetch_timestamp=datetime.datetime.min)


def get_and_cache_rowdata(localpath):
  """Returns a row_data dict.

  get_and_cache_rowdata takes a localpath which is used to fetch data from the
  cache. If the data is present, then we have all of the data we need and we
  return early.

  Otherwise, we need to fetch the row object and set up the row data.

  Here we assume localpath is already unquoted.
  """
  row_data = get_data_from_cache(localpath)
  if row_data and type(row_data) == type({}):
    return row_data
  row = Row.get_by_key_name(localpath)
  if not row:
    logging.debug('get_and_cache_rowdata(\'%s\'): no matching localpath in '
        'datastore' % localpath)
    return {}
  row_data = {}
  row_data['rev'] = row.revision
  row_data['name'] = row.name
  row_data['status'] = row.status
  row_data['comment'] = row.comment
  row_data['details'] = row.details
  row_data['rev_number'] = row.rev_number
  row_data['fetch_timestamp'] = row.fetch_timestamp
  logging.debug('content for %s found in datastore' % localpath)
  put_data_into_cache(localpath, row_data)
  return row_data


def save_row(row_data, localpath):
  rev_number = row_data['rev_number']
  row = get_or_create_row(localpath, rev_number)
  row_key = row.key()
  def tx_row(row_key):
    row = Row.get(row_key)
    # E1103:959,7:save_row.tx_row: Instance of 'list' has no
    # 'fetch_timestamp' member (but some types could not be inferred)
    # pylint: disable=E1103
    # if row.fetch_timestamp > timestamp:
    #   return
    row.fetch_timestamp = row_data['fetch_timestamp']
    row.revision = row_data['rev']
    row.name = row_data['name']
    row.status = row_data['status']
    row.comment = row_data['comment']
    row.details = row_data['details']
    # E1103:967,4:save_row.tx_row: Instance of 'list' has no 'put' member
    # (but some types could not be inferred)
    # pylint: disable=E1103
    row.put()
  db.run_in_transaction(tx_row, row_key)
  put_data_into_cache(localpath, row_data)
  logging.info('Saved and cached row with localpath %s' % localpath)
  # Update latest_rev in datastore & cache, or create it if it doesn't exist.
  prev_rev = get_and_cache_rowdata('latest_rev')
  if not prev_rev or rev_number > prev_rev['rev_number']:
    latest_rev_row = {
        'rev_number': rev_number,
        'fetch_timestamp': datetime.datetime.now(),
        'rev': None,
        'name': None,
        'status': None,
        'comment': None,
        'details': None,
    }
    prev_rev_db = get_or_create_row('latest_rev', rev_number)
    prev_rev_db.fetch_timestamp = datetime.datetime.now()
    prev_rev_db.rev_number = rev_number
    prev_rev_db.put()
    put_data_into_cache('latest_rev', latest_rev_row)


def utf8_convert(beautiful_soup_tag):
  # cmp also investigated:
  #   beautiful_soup_tag.__str__(encoding='utf-8').decode('utf-8')
  # He found that the BeautifulSoup() __str__ method when used with a 'utf-8'
  # encoding returned effectively the same thing as str(), a Python built-in.
  # After a handful of tests, he switched to using str() to avoid the add'l
  # complexity of another BeautifulSoup method.
  return str(beautiful_soup_tag).decode('utf-8')


##########
# ConsoleData class definition and related functions.
##########
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
    return ''.join(utf8_convert(content) for content in contents)

  @property
  def last_row(self):
    return self.row_data[self.lastRevisionSeen]

  def SawMaster(self, master):
    self.lastMasterSeen = master
    assert(self.lastMasterSeen not in self.category_order)
    self.masters.append(self.lastMasterSeen)
    self.category_order.setdefault(self.lastMasterSeen, [])
    self.category_data.setdefault(self.lastMasterSeen, {})

  def SawRevision(self, revision, rev_number):
    self.lastRevisionSeen = rev_number
    # TODO(cmp): Fix the order of the revision data in self.row_orderedkeys
    if self.lastRevisionSeen not in self.row_orderedkeys:
      logging.debug('SawRevision: guessing at row ordering')
      self.row_orderedkeys.append(self.lastRevisionSeen)
    self.row_data.setdefault(self.lastRevisionSeen, {})
    self.last_row['revision'] = revision
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

  def AddRow(self, row):
    self.SawRevision(row['rev'], row['rev_number'])
    revlink = BeautifulSoup(row['rev']).a['href']
    self.SetLink(revlink)
    name = BeautifulSoup(row['name'])
    self.SetName(self.ContentsToHtml(name))
    status = BeautifulSoup(row['status']).findAll('table')
    for i, stat in enumerate(status):
      self.SetStatus(self.category_order[self.lastMasterSeen][i],
                     unicode(stat))
    comment = BeautifulSoup(row['comment'])
    self.SetComment(self.ContentsToHtml(comment))
    if row['details']:
      details = BeautifulSoup(row['details'])
      self.SetDetail(self.ContentsToHtml(details))

  def ParseRow(self, row):
    cells = row.findAll('td', recursive=False)
    # Figure out which row this is.
    for attrname, attrvalue in cells[0].attrs:
      if attrname != 'class':
        continue
      attrvalue = re.sub(r'^(\S+).*', r'\1', attrvalue)
      if attrvalue == 'DevRev':
        revision = cells[0]
        self.SawRevision(self.ContentsToHtml(
            revision.findAll('a')[0].contents[0]))
        self.SetLink(self.ContentsToHtml(revision.findAll('a')[0].attrs[0][1]))
        nameparts = cells[1].contents
        self.SetName(re.sub(r'^\s+(.*)\s*$',
                            r'\1',
                            self.ContentsToHtml(nameparts)))
        for i, bs in enumerate(cells[2:]):
          self.SetStatus(self.category_order[self.lastMasterSeen][i],
                         self.ContentsToHtml(bs.findAll('table',
                                                        recursive=False)[0]))
      if attrvalue == 'DevComment':
        self.SetComment(comment=self.ContentsToHtml(cells[0].contents))
      if attrvalue == 'DevDetails':
        self.SetDetail(detail=self.ContentsToHtml(cells[0].contents))

  def Finish(self):
    self.row_orderedkeys = sorted(self.row_orderedkeys, key=int, reverse=True)
    # TODO(cmp): Look for row/master/categories that are unset.  If they are
    #            at the latest revisions, leave them unset.  If they are at
    #            the earliest revisions, set them to ''.


##########
# Heavy-lifting functions that do most of the console processing.
# AKA postfetch and postsave functions/handlers.
##########
def console_merger(localpath, remoteurl, page_data,
                   masters_to_merge=None, num_rows_to_merge=None):
  masters_to_merge = masters_to_merge or DEFAULT_MASTERS_TO_MERGE
  num_rows_to_merge = num_rows_to_merge or 25
  console_data = ConsoleData()
  surroundings = get_and_cache_pagedata('surroundings')
  merged_page = BeautifulSoup(surroundings['content'])
  merged_tag = merged_page.find('table', 'ConsoleData')
  if merged_tag is None:
    msg = 'console_merger("%s", "%s", "%s"): merged_tag cannot be None.' % (
          localpath, remoteurl, page_data)
    logging.error(msg)
    raise Exception(msg)
  latest_rev = int(get_and_cache_rowdata('latest_rev')['rev_number'])
  if not latest_rev:
    logging.error('console_merger(\'%s\', \'%s\', \'%s\'): cannot get latest '
                  'revision number.' % (
                      localpath, remoteurl, page_data))
    return
  fetch_timestamp = datetime.datetime.now()
  for master in masters_to_merge:
    # Fetch the summary one-box-per-builder for the master.
    # If we don't get it, something is wrong, skip the master entirely.
    master_summary = get_and_cache_pagedata('%s/console/summary' % master)
    if not master_summary['content']:
      continue
    console_data.SawMaster(master)
    # Get the categories for this builder. If the builder doesn't have any
    # categories, just use the default empty-string category.
    category_list = []
    master_categories = get_and_cache_pagedata('%s/console/categories' % master)
    if not master_categories['content']:
      category_list.append('')
    else:
      category_row = BeautifulSoup(master_categories['content'])
      category_list = [c.text for c in category_row.findAll('td', 'DevStatus')]
    # Get the corresponding summary box(es).
    summary_row = BeautifulSoup(master_summary['content'])
    summary_list = summary_row.findAll('table')
    for category, summary in zip(category_list, summary_list):
      console_data.AddCategory(category, summary)

    # Fetch all of the rows that we need.
    rows_fetched = 0
    revs_skipped = 0
    current_rev = latest_rev
    while rows_fetched < num_rows_to_merge and current_rev >= 0:
      # Don't get stuck looping backwards forever into data we don't have.
      # How hard we try scales with how many rows the person wants.
      if revs_skipped > max(num_rows_to_merge, 10):
        break
      row_data = get_and_cache_rowdata('%s/console/%s' % (master, current_rev))
      if not row_data:
        current_rev -= 1
        revs_skipped += 1
        continue
      console_data.AddRow(row_data)
      current_rev -= 1
      revs_skipped = 0
      rows_fetched += 1

  # Convert the merged content into console content.
  console_data.Finish()
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
  merged_console = merged_template.render(data=console_data)
  # For debugging:
  # logging.info('%r' % merged_console)
  # import code
  # code.interact(local=locals())

  # Place merged console at |merged_tag|'s location in |merged_page|, and put
  # the result in |merged_content|.
  merged_tag.replaceWith(merged_console)
  merged_content = utf8_convert(merged_page)
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
  merged_page = get_or_create_page(localpath, None, maxage=30)
  logging.info('console_merger: saving merged console')
  page_data = get_and_cache_pagedata(localpath)
  page_data['title'] = 'BuildBot: Chromium'
  page_data['offsite_base'] = 'http://build.chromium.org/p/chromium'
  page_data['body_class'] = 'interface'
  page_data['content'] = merged_content
  save_page(merged_page, localpath, fetch_timestamp, page_data)
  return


def console_handler(unquoted_localpath, remoteurl, page_data=None):
  page_data = page_data or {}
  content = page_data.get('content')
  if not content:
    logging.error('console_handler(\'%s\', \'%s\', \'%s\'): cannot get site '
                  'from local path' % (
                      unquoted_localpath, remoteurl, page_data))
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
    'sheriff_ios_europe',
    'sheriff_ios_us',
    'sheriff_memory',
    'sheriff_nacl',
    'sheriff_perf',
    'sheriff_v8',
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

  # TODO(hinoka): Enable these when the app is done.
  # Convert direct build.chromium.org links to local links.
  # content = re.sub("http://build.chromium.org/p/", "/buildbot/", content)
  # content = re.sub(r"/buildbot/(.*)/buildstatus\?builder=(.*)&number=(\d+)",
  #                  r"/buildbot/\1/builders/\2/builds/\3", content)

  # Disable the personalized for box for now.
  content = re.sub(r"<input id='namebox'[^>]+>", '', content)
  content = re.sub(r"<input.*onclick='reload_page\(\)'/>", '', content)

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


def get_position_number(commit_msg):
  # Cr-Commit-Position should exist at least once in the commit message, but can
  # exist more than once.  Reverts are examples of commits which can contain
  # multiple Cr-Commit-Position instances.  In those cases, only the last one
  # is correct, so split on the break tag and reverse the result to find the
  # last occurrence of Cr-Commit-Position.
  for line in reversed(commit_msg.split('<br />')):
    if line.startswith('Cr-Commit-Position: '):
      return filter(str.isdigit, str(line.split('@')[-1]))
  return '0'


# W0613:600,28:parse_master: Unused argument 'remoteurl'
# pylint: disable=W0613
def parse_master(localpath, remoteurl, page_data=None):
  """Part of the new pipeline to store individual rows rather than
  whole pages of html. Parses the master data into a set of rows,
  and writes them out to the datastore in an easily retrievable format.

  Doesn't modify page_data dict.
  """
  ts = datetime.datetime.now()
  page_data = page_data or {}
  content = page_data.get('content')
  if not content:
    return page_data
  content = content.decode('utf-8', 'replace')

  # Split page into surroundings (announce, legend, footer) and data (rows).
  surroundings = BeautifulSoup(content)
  data = surroundings.find('table', 'ConsoleData')
  if data is None:
    raise Exception('parse_master: data can not be None')
  new_data = Tag(surroundings, 'table', [('class', 'ConsoleData'),
                                         ('width', '96%')])
  data.replaceWith(new_data)

  surroundings_page = get_or_create_page('surroundings',
                                         None, maxage=30)
  surroundings_data = {}
  surroundings_data['title'] = 'Surroundings'
  surroundings_data['content'] = utf8_convert(surroundings)
  save_page(surroundings_page, 'surroundings', ts, surroundings_data)

  rows = data.findAll('tr', recursive=False)
  # The first table row can be special: the list of categories.
  categories = None
  # If the first row contains a DevStatus cell...
  if rows[0].find('td', 'DevStatus') != None:
    # ...extract it into the categories...
    categories = rows[0]
    # ...and get rid of the next (spacer) row too.
    rows = rows[2:]

  if categories:
    category_page = get_or_create_page(localpath + '/categories',
                                       None, maxage=30)
    category_data = {}
    category_data['title'] = 'Categories for ' + localpath
    category_data['content'] = utf8_convert(categories)
    save_page(category_page, localpath + '/categories', ts, category_data)

  # The next table row is special, it's the summary one-box-per-builder.
  summary = rows[0]
  rows = rows[1:]

  summary_page = get_or_create_page(localpath + '/summary', None, maxage=30)
  summary_data = {}
  summary_data['title'] = 'Summary for ' + localpath
  summary_data['content'] = utf8_convert(summary)
  save_page(summary_page, localpath + '/summary', ts, summary_data)

  curr_row = {}
  # Each table row is either a status row with a revision, name, and status,
  # a comment row with the commit message, a details row with flakiness info,
  # or a spacer row (in which case we finalize the row and save it).
  for row in rows:
    if row.find('td', 'DevComment'):
      curr_row['comment'] = ''.join(utf8_convert(tag).strip()
                                    for tag in row.td.contents)
    elif row.find('td', 'DevDetails'):
      curr_row['details'] = ''.join(utf8_convert(tag).strip()
                                    for tag in row.td.contents)
    elif row.find('td', 'DevStatus'):
      curr_row['rev'] = ''.join(utf8_convert(tag).strip()
                                for tag in row.find('td', 'DevRev').contents)
      curr_row['name'] = ''.join(utf8_convert(tag).strip()
                                 for tag in row.find('td', 'DevName').contents)
      curr_row['status'] = ''.join(utf8_convert(box.table).strip()
                                   for box in row.findAll('td', 'DevStatus'))
    else:
      if 'details' not in curr_row:
        curr_row['details'] = ''
      curr_row['fetch_timestamp'] = ts
      curr_row['rev_number'] = get_position_number(curr_row['comment'])
      save_row(curr_row, localpath + '/' + curr_row['rev_number'])
      curr_row = {}

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


##########
# Utility functions for blobstore and memcache.
##########
def get_data_from_cache(localpath):
  memcache_data = memcache.get(localpath)
  if not memcache_data:
    return None
  logging.debug('content for %s found in memcache' % localpath)
  return json.loads(memcache_data)


def dtdumper(obj):
  if hasattr(obj, 'isoformat'):
    return obj.isoformat()
  else:
    raise TypeError(repr(obj) + "is not JSON serializable")


def put_data_into_cache(localpath, data):
  memcache_data = json.dumps(data, default=dtdumper)
  if not memcache.set(key=localpath, value=memcache_data, time=2*60):
    logging.error('put_data_into_cache(\'%s\'): memcache.set() failed' % (
        localpath))


def write_blob(data, mime_type):
  """Saves a Unicode string as a new blob, returns the blob's key."""
  file_name = files.blobstore.create(mime_type=mime_type)
  data = data.encode('utf-8')
  with files.open(file_name, 'a') as blob_file:
    blob_file.write(data)
  files.finalize(file_name)
  return files.blobstore.get_blob_key(file_name)


def path_to_mime_type(path):
  return EXT_TO_MIME.get(os.path.splitext(path)[1], 'text/html')


EXT_TO_MIME = {
  '.css': 'text/css',
  '.js': 'text/javascript',
  '.json': 'application/json',
  '.html': 'text/html',
}


##########
# Functions for actually fetching original pages.
##########
def fetch_pages():
  """Starts a background fetch operation for pages that need it."""
  logging.debug('fetch_pages()')
  for url in URLS:
    deferred.defer(fetch_page, **url)


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


# List of URLs to fetch.
URLS = [
  # Console URLs.
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.chrome/console',
    'localpath': 'chromium.chrome/console',
    'postfetch': [console_handler, parse_master],
    'postsave': console_merger,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.chromiumos/console',
    'localpath': 'chromium.chromiumos/console',
    'postfetch': [console_handler, parse_master],
    'postsave': console_merger,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.linux/console',
    'localpath': 'chromium.linux/console',
    'postfetch': [console_handler, parse_master],
    'postsave': console_merger,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.mac/console',
    'localpath': 'chromium.mac/console',
    'postfetch': [console_handler, parse_master],
    'postsave': console_merger,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium/console',
    'localpath': 'chromium.main/console',
    'postfetch': [console_handler, parse_master],
    'postsave': console_merger,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.memory/console',
    'localpath': 'chromium.memory/console',
    'postfetch': [console_handler, parse_master],
    'postsave': console_merger,
    'maxage': 30,  # 30 secs
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.win/console',
    'localpath': 'chromium.win/console',
    'postfetch': [console_handler, parse_master],
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
    'remoteurl': 'http://build.chromium.org/p/chromium.linux/default.css',
    'localpath': 'chromium.linux/default.css',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.lkgr/default.css',
    'localpath': 'chromium.lkgr/default.css',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium.mac/default.css',
    'localpath': 'chromium.mac/default.css',
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
    'remoteurl': 'http://build.chromium.org/p/chromium.win/default.css',
    'localpath': 'chromium.win/default.css',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromebot/default.css',
    'localpath': 'chromebot/default.css',
    'maxage': 15*60,  # 15 mins
  },

  # Sheriff URLs.
  {
    'remoteurl': 'http://build.chromium.org/p/chromium/trooper.js',
    'localpath': 'chromium/trooper.js',
    'maxage': 15*60,  # 15 mins
  },
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
    'remoteurl': (
        'http://build.chromium.org/p/chromium/sheriff_android_gardeners.js'),
    'localpath': 'chromium/sheriff_android_gardeners.js',
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
    'remoteurl': 'http://build.chromium.org/p/chromium/sheriff_ios_europe.js',
    'localpath': 'chromium/sheriff_ios_europe.js',
    'maxage': 15*60,  # 15 mins
  },
  {
    'remoteurl': 'http://build.chromium.org/p/chromium/sheriff_ios_us.js',
    'localpath': 'chromium/sheriff_ios_us.js',
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
    'remoteurl': 'http://build.chromium.org/p/chromium/sheriff_v8.js',
    'localpath': 'chromium/sheriff_v8.js',
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
        ('http://build.chromium.org/p/chromium.linux/'
         'horizontal_one_box_per_builder'),
    'localpath': 'chromium.linux/horizontal_one_box_per_builder',
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
        ('http://build.chromium.org/p/chromium.mac/'
         'horizontal_one_box_per_builder'),
    'localpath': 'chromium.mac/horizontal_one_box_per_builder',
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
  {
    'remoteurl':
        ('http://build.chromium.org/p/chromium.win/'
         'horizontal_one_box_per_builder'),
    'localpath': 'chromium.win/horizontal_one_box_per_builder',
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

# # Trigger background process update.
# {
#     'remoteurl': 'http://chromium-build.appspot.com/backend/update'
]
