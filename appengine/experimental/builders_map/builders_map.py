import collections
from google.appengine.ext import db
import json
import logging
import urllib
import urllib2
import webapp2


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
    MASTERS_URL = ('http://chrome-build-extract.appspot.com/get_masters?json=1')
    master_names = json.load(urllib2.urlopen(MASTERS_URL))['masters']

    builder_to_masters = collections.defaultdict(list)

    for master_name in master_names:
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

