import collections
from google.appengine.ext import db
import json
import logging
import urllib
import urllib2
import webapp2

MASTER_NAMES = [
  'chromium',
  'chromium.android',
  'chromium.chrome',
  'chromium.chromedriver',
  'chromium.chromiumos',
  'chromium.fyi',
  'chromium.gatekeeper',
  'chromium.goma',
  'chromium.gpu',
  'chromium.gpu.fyi',
  'chromium.infra',
  'chromium.infra.cron',
  'chromium.linux',
  'chromium.lkgr',
  'chromium.mac',
  'chromium.memory',
  'chromium.perf',
  'chromium.swarm',
  'chromium.tools.build',
  'chromium.webkit',
  'chromium.webrtc',
  'chromium.webrtc.fyi',
  'chromium.win',
  'chromiumos',
  'client.dart',
  'client.dart.fyi',
  'client.drmemory',
  'client.dynamorio',
  'client.libyuv',
  'client.mojo',
  'client.nacl',
  'client.nacl.ports',
  'client.nacl.sdk',
  'client.nacl.toolchain',
  'client.skia',
  'client.syzygy',
  'client.v8',
  'client.v8.branches',
  'client.v8.fyi',
  'client.webrtc',
  'client.webrtc.fyi',
  'tryserver.blink',
  'tryserver.chromium.android',
  'tryserver.chromium.linux',
  'tryserver.chromium.mac',
  'tryserver.chromium.perf',
  'tryserver.chromium.win',
  'tryserver.libyuv',
  'tryserver.nacl',
  'tryserver.v8',
  'tryserver.webrtc',
]


class Map(db.Model):
  content = db.TextProperty()

class MainPage(webapp2.RequestHandler):
  def get(self):
    self.response.headers['Content-Type'] = 'application/json'
    entity = Map.get_by_key_name('builder_to_master')
    if entity:
      self.response.write(entity.content)


class BuildersMap(webapp2.RequestHandler):
  def get(self):
    builder_to_masters = collections.defaultdict(list)
    for master_name in MASTER_NAMES:
      logging.info('Fetching builders for %s', master_name)
      url_pattern = 'https://chrome-build-extract.appspot.com/get_master/%s'
      master_url = url_pattern % master_name
      try:
        master_json = json.load(urllib2.urlopen(master_url))
        for builder_name in master_json['builders']:
          builder_to_masters[builder_name].append(master_name)
      except urllib2.HTTPError:
        logging.exception('Failed to fetch builders for %s', master_name)

    builders = {}
    for builder, masters in builder_to_masters.iteritems():
      for master in masters:
        bucket = 'master.' + master

        # If this builder is ready for LUCI, use the corresponding LUCI bucket
        # instead.
        luci_migration_url = (
            'https://luci-migration.appspot.com'
            '/masters/%s/builders/%s?format=json' % (
                urllib.quote(master), urllib.quote(builder)))
        try:
          builder_info = json.load(urllib2.urlopen(luci_migration_url))
          if builder_info['luci_is_prod']:
            bucket = builder_info['bucket']
        except urllib2.HTTPError as ex:
          if ex.code == 404:
            # This builder is not being tracked by LUCI
            pass
          else:
            logging.exception(
                'Failed to fetch LUCI migration state of %s/%s',
                master, builder)
            # Retry the entire task.
            raise

        builders.setdefault(
            builder, {}).setdefault('buckets', []).append(bucket)


    # TODO: rename datastore key to reflect reality.
    b_map = Map(content=json.dumps(builders), key_name='builder_to_master')
    b_map.put()


app = webapp2.WSGIApplication([
  ('/', MainPage),
  ('/tasks/builders_map', BuildersMap),
], debug=True)

