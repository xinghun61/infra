# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common backend for Chrome UI Catalog.

The Chrome UI Catalog back end accesses screenshots and associated data.
"""

import getpass
import httplib
import json
import os
import urllib
import webapp2


def _get_user_email():
  return getpass.getuser()


def _get_screenshots(request):
  # For speed this caches the most recent set of screenshot descriptions.
  app = webapp2.get_app()
  screenshot_source = urllib.unquote(request.get('screenshot_source'))
  old_screenshot_source = app.config.get('screenshot_source')
  if screenshot_source != old_screenshot_source:
    app.config['screenshot_source'] = screenshot_source
    screenshot_loader = app.config.get('screenshot_loader')
    app.config['screenshots'] = list(enumerate(screenshot_loader.get_data(
        screenshot_source)))
  return app.config.get('screenshots', [])


class ScreenshotListServer(webapp2.RequestHandler):
  """Server for fetching lists of screenshots."""

  def get(self):
    """Fetch a filtered list of screenshots."""
    filters = set(json.loads(self.request.GET['filters']).iteritems())
    tags = set(self.request.GET.getall('userTags'))
    try:
      screenshots = [
          (i, s) for i, s in _get_screenshots(self.request) if
          filters.issubset(
              s['filters'].iteritems()) and tags.issubset(s['tags'])
      ]
    except ScreenshotLoader.ScreenshotLoaderException:
      self.abort(httplib.NOT_FOUND, detail='Screenshot description not found')

    self.response.headers['Content-Type'] = 'application/json'
    reply = [{
        'key': str(i),
        'label': s.get('filters').get('Screenshot Name')
    } for i, s in screenshots]
    self.response.out.write(json.dumps(reply))


class ImageServer(webapp2.RequestHandler):
  """Sceenshot image fetcher."""

  def get(self, shotkey):
    """Fetch an image for a screenshot.

    Args:
      shotkey: the key of the screenshot

    Returns:
      The response containing the image, or a redirect to the image.
    """
    try:
      _, screenshot = _get_screenshots(self.request)[int(shotkey)]
    except ScreenshotLoader.ScreenshotLoaderException:
      self.abort(httplib.NOT_FOUND, detail='Screenshot description not found')
    if screenshot is None:
      self.abort(httplib.NOT_FOUND)
    # Access to the images differs depending whether the tests were run on a bot
    # or locally. If it was run remotely the directory structure is lost when
    # the images are saved, but the image_link will be valid. If they were run
    # locally then the directory structure and hence the location will be valid.
    # The image_link url can't be used in the local case, since it will be a
    # file link, and browsers, for security reasons, restricts access to file
    # links.
    if screenshot['image_link'].startswith('https://'):
      return self.redirect(screenshot['image_link'].encode('ascii', 'ignore'),
                           permanent=True)
    self.response.headers['Content-Type'] = 'image/jpeg'
    with open(screenshot['location'], 'rb') as image:
      return webapp2.Response(image.read())


class DataServer(webapp2.RequestHandler):
  """Screenshot data fetcher."""

  def get(self, shotkey):
    """Fetch the filters and metadata for a screenshot.

    Args:
      shotkey: the key of the screenshot
    """
    if shotkey == 'undefined':
      return
    _, screenshot = _get_screenshots(self.request)[int(shotkey)]
    if screenshot is None:
      self.abort(httplib.NOT_FOUND)
    self.response.headers['Content-Type'] = 'application/json'
    self.response.out.write(
        json.dumps({
            'metadata': screenshot['metadata'],
            'filters': screenshot['filters'],
            'userTags': screenshot['tags']
        }))


class SelectorList(webapp2.RequestHandler):
  """Class respond to service/selector_list requests."""

  def get(self):
    """Get the complete list of filter names, filter values, and tags."""
    filter_dict = {}
    tag_set = set()
    try:
      for _, screenshot in _get_screenshots(self.request):
        for f in screenshot['filters']:
          if f not in filter_dict:
            filter_dict[f] = []
          value = screenshot['filters'][f]
          if value not in filter_dict[f]:
            filter_dict[f].append(value)
        for t in screenshot['tags']:
          tag_set.add(t)
    except ScreenshotLoader.ScreenshotLoaderException:
      self.abort(httplib.NOT_FOUND, detail='Screenshot description not found')
    self.response.headers['Content-Type'] = 'application/json'
    self.response.out.write(
        json.dumps({
            'filters': filter_dict,
            'userTags': sorted(tag_set)
        }))


class ScreenshotLoader(object):
  """Class to fetch the screenshot data."""

  def get_data(self, data_location):
    """Read the (JSON) screenshots description.

    Args:
      data_location: the path or URL of the screenshot description.

    Returns:
      A list of screenshot descriptions.
    """
    pass

  @staticmethod
  def _read_descriptions(data_location, descriptions):
    """Read the JSON screenshot descriptions into an internal structure.

    Args:
      data_location: the path or URL of the screenshot description.
      descriptions: the JSON descriptions as a string.

    Returns:
      A list of screenshot descriptions.
    """
    data = []
    for new_data in json.loads(descriptions):
      if sorted(new_data.keys()) != ['filters', 'image_link', 'location',
                                     'metadata', 'tags']:
        print '%s is not a valid screenshot description' % data_location
        print 'keys', sorted(new_data.keys())
        continue
      new_data['location'] = os.path.join(
          os.path.dirname(data_location), new_data['location'])
      data.append(new_data)
    return data

  class ScreenshotLoaderException(Exception):
    pass


routes_list = [
    ('/service/selector_list', SelectorList),
    ('/service/(?P<shotkey>[^/]*)/image', ImageServer),
    ('/service/(?P<shotkey>[^/]*)/data', DataServer),
    ('/service/screenshot_list', ScreenshotListServer),
    # TODO(aberent): Re-enable comments once we have worked out how to store
    # then and resolved possible privacy concerns.
    # ('/service/(?P<shotkey>[^/]*)/comment/(?P<commentkey>[^/]*)',
    #     CommentServer),
    # ('/service/(?P<shotkey>[^/]*)/comments', CommentListServer)
]
