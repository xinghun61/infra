# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime, timedelta

from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop
from protorpc import messages


class BuildStatus(messages.Enum):
  SCHEDULED = 1
  BUILDING = 2
  SUCCESS = 3
  FAILURE = 4
  EXCEPTION = 5  # Infrastructure failure.


class BuildProperties(ndb.Expando):
  """Arbitrary build properties, a key-value pair map.

  Attributes:
    builder_name (string): special property, that is used for build grouping
      during rendering.
  """
  builder_name = ndb.StringProperty()


class Build(ndb.Model):
  """Describes a build.

  The only Build entity in its entity group.

  Attributes:
    tag (string): a generic way to distinguish builds. Different build tags have
      different permissions.
    properties (BuildProperties): key-value pair map.
      builder_name: a special property used for grouping builds when rendering.
    status (BuildStatus): status of the build
    url (str): a URL to a build-system-specific build, viewable by a human.
    available_since (datetime): the earliest time the build can be leased.
      The moment the build is leased, |available_since| is set to
      (utcnow + lease_duration). On build creation, is set to utcnow.
  """

  tag = ndb.StringProperty(required=True)
  properties = ndb.StructuredProperty(BuildProperties)
  status = msgprop.EnumProperty(BuildStatus,  default=BuildStatus.SCHEDULED)
  url = ndb.StringProperty()
  available_since = ndb.DateTimeProperty(required=True, auto_now_add=True)

  @property
  def builder_name(self):
    return self.properties.builder_name if self.properties else None

  def set_status(self, value):
    """Changes build status and notifies interested parties."""
    if self.status == value:
      return
    self.status = value
    # TODO(nodir): uncomment when model/log.py is added
    # if value == BuildStatus.BUILDING:
    #   BuildStarted().add_to(self)
    # elif value in (BuildStatus.SUCCESS, BuildStatus.FAILURE):
    #  BuildCompleted().add_to(self)

  def modify_lease(self, lease_seconds):
    """Changes build's lease, updates |available_since|."""
    self.available_since = datetime.utcnow() + timedelta(seconds=lease_seconds)

  @property
  def key_string(self):
    """Returns an opaque key string."""
    return self.key.urlsafe() if self.key else None

  @classmethod
  def parse_key_string(cls, key_string):
    """Parses an opaque key string."""
    return ndb.Key(urlsafe=key_string)

  @classmethod
  def lease(cls, lease_seconds, max_tasks, tags):
    """Leases builds.

    Args:
      lease_seconds (int): lease duration. After lease expires, the Build can be
        leased again.
      max_tasks (int): maximum number of builds to return.
      tags (list of string): lease only builds with any of |tags|.

    Returns:
      A list of Builds.
    """
    q = cls.query(
        cls.status.IN([BuildStatus.SCHEDULED, BuildStatus.BUILDING]),
        cls.tag.IN(tags),
        cls.available_since <= datetime.utcnow()
    )

    @ndb.transactional
    def lease_build(build):
      if build.status not in (BuildStatus.SCHEDULED, BuildStatus.BUILDING):
        return False
      if build.available_since > datetime.utcnow():
        return False
      build.modify_lease(lease_seconds)
      build.put()
      return True

    builds = []
    for b in q.fetch(max_tasks):
      if lease_build(b):
        builds.append(b)
    return builds

  @ndb.transactional
  def unlease(self):
    """Removes build lease."""
    self.modify_lease(0)
    self.put()
