import collections
from google.appengine.ext import db
import json
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
    MASTERS_URL = ('https://chrome-infra-stats.appspot.com/_ah/api/stats/v1'
                   '/masters')
    master_names = json.load(urllib2.urlopen(MASTERS_URL))['masters']

    builder_to_masters = collections.defaultdict(list)

    for master_name in master_names:
      url_pattern = 'https://chrome-build-extract.appspot.com/get_master/%s'
      master_url = url_pattern % master_name
      master_json = json.load(urllib2.urlopen(master_url))
      for builder_name in master_json['builders']:
        builder_to_masters[builder_name].append(master_name)
    b_map = Map(content = json.dumps(builder_to_masters),
                key_name = 'builder_to_master')
    b_map.put()


app = webapp2.WSGIApplication([
  ('/', MainPage),
  ('/tasks/builders_map', BuildersMap),
], debug=True)

