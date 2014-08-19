from datetime import datetime, timedelta
import json
import sqlite3
import time
import urllib
import urllib2

class RequestCache:
  def __init__(self, name):
    self._name = name
    self._db = sqlite3.connect(name)
    self._db.execute('''CREATE TABLE IF NOT EXISTS
                        store(url TEXT PRIMARY KEY, body TEXT,
                              status INTEGER, elapsed REAL)''')

  def get(self, url):
    c = self._db.execute('SELECT * FROM store WHERE url = ?', (url,))
    r = c.fetchone()
    if not r:
      return None
    return Response(r[0], r[1], r[2], timedelta(seconds=r[3]), True)

  def has(self, url):
    return self.get(url) != None

  def set(self, url, response):
    self._db.execute('INSERT OR REPLACE INTO store VALUES (?, ?, ?, ?)',
                     (url, response.text, response.status_code,
                      response.elapsed.total_seconds()))
    self._db.commit()

  def delete(self, url):
    self._db.execute('DELETE FROM store WHERE url = ?', (url,))

class Response:
  def __init__(self, url, text, status, elapsed, cached=False):
    self._url = url
    self._text = text
    self._status = status
    self._elapsed = elapsed
    self._cached = cached

  @property
  def url(self):
    return self._url

  @property
  def text(self):
    return self._text

  def json(self):
    return json.loads(self._text)

  @property
  def status_code(self):
    return self._status

  @property
  def elapsed(self):
    return self._elapsed

  @property
  def cached(self):
    return self._cached

class Fetcher:
  def __init__(self, cache):
    self._cache = cache

  def set_cache(self, cache):
    self._cache = cache

  @property
  def cache(self):
    return self._cache

  def _fetch(self, url): # pragma: no cover
    start_time = datetime.fromtimestamp(time.time())
    try:
      r = urllib2.urlopen(url)
    except urllib2.HTTPError, e:
      end_time = datetime.fromtimestamp(time.time())
      elapsed = end_time - start_time
      resp = Response(url, '', e.getcode(), elapsed)
      self._cache.set(url, resp)
      return resp
    status = r.getcode()
    body = r.read()
    end_time = datetime.fromtimestamp(time.time())
    elapsed = end_time - start_time
    resp = Response(url, body, status, elapsed)
    self._cache.set(url, resp)
    return resp

  def get(self, url, params=None):
    if params:
      if '?' not in url:
        url = url + '?'
      else:
        url = url + '&'
      url += urllib.urlencode(params)
    # hack: requests handles this properly by escaping spaces in the url, we do
    # not, but cheat enough to fetch builders with spaces in their names
    if (' ' in url):
      url = url.replace(' ', '%20')
    if (self._cache.has(url)):
      return self._cache.get(url)
    return self._fetch(url) # pragma: no cover

  # This is a class method so subclass instances can override it, so disable the
  # lint warning for it not using self.
  # pylint: disable=R0201
  def post(self, url, data): # pragma: no cover
    encoded_data = urllib.urlencode(data)
    r = urllib2.urlopen(url, encoded_data)
    return r

_fetcher = Fetcher(RequestCache('default_cache.db'))

def set_cache(name):
  _fetcher.set_cache(RequestCache(name))

def get(url, params=None):
  return _fetcher.get(url, params)

def post(url, data): # pragma: no cover
  return _fetcher.post(url, data)
