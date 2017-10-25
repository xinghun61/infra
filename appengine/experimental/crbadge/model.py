from google.appengine.ext import ndb


class Badge(ndb.Model):
  badge_name = ndb.StringProperty(required=True)
  level_1 = ndb.IntegerProperty()
  level_2 = ndb.IntegerProperty()
  level_3 = ndb.IntegerProperty()
  # Show the value instead of the level.
  show_number = ndb.BooleanProperty()
  title = ndb.StringProperty()
  description = ndb.StringProperty()
  icon = ndb.StringProperty()


class UserData(ndb.Model):
  badge_name = ndb.StringProperty(required=True)
  email = ndb.StringProperty(required=True)
  value = ndb.IntegerProperty()
  visible = ndb.BooleanProperty()
