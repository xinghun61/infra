"""
A wrapper around list that caches additions or removals until they are
performed
"""


class ChangeTrackingList(list):
  def __init__(self, seq=()):
    list.__init__(self, seq)
    self.added = set()
    self.removed = set()

  def append(self, p_object):
    list.append(self, p_object)
    if p_object in self.removed:
      self.removed.remove(p_object)
    else:
      self.added.add(p_object)

  def remove(self, value):
    list.remove(self, value)

    if value in self.added:
      self.added.remove(value)
    else:
      self.removed.add(value)

  def isChanged(self):
    return (len(self.added) + len(self.removed)) > 0

  def reset(self):
    self.added.clear()
    self.removed.clear()
