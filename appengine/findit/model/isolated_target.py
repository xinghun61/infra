# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class IsolatedTarget(ndb.Model):
  """Represents a test target that has been isolated by a builder.

  The isolated hash of a given target can't be used as the key for this model
  because different builds may produce the same isolated target, e.g. if no
  changes happen to the files that produce the target happen between such builds
  and due to incremental compilation even the timestamps do not change.

  A combination of the build id and the target is used as the key since there is
  no duplicate target in the same build.
  """

  # Luci project, such as 'chromium'.
  luci_project = ndb.StringProperty(required=True)

  # Buildbucket bucket. Note that this is expected to be the suffix to
  # 'luci.<project>' e.g. For 'luci.chromium.ci' this is expected to be 'ci'.
  bucket = ndb.StringProperty(required=True)

  # For querying by master, important for pre-luci builds
  master_name = ndb.StringProperty(required=True)

  # Name of the builder name whose build configuration the isolated build
  # matches. (It does not have to match the actual builder that compiled it,
  # such as when the findit_variable builder compiles targets during tryjob).
  # e.g. 'Linux Builder', use parent_buildername when appropriate.
  builder_name = ndb.StringProperty(required=True)

  # The host for the git repo. e.g. 'chromium.googlesource.com'.
  gitiles_host = ndb.StringProperty(required=True)

  # The git project e.g. 'chromium/src'. Note that this excludes .git.
  gitiles_project = ndb.StringProperty(required=True)

  # The ref that the ci builder builds from. e.g. 'refs/heads/master'.
  gitiles_ref = ndb.StringProperty(required=True)

  # The buildbucket id of the build, if available.
  build_id = ndb.IntegerProperty(indexed=False)

  # The compile target as named in the output of the
  # isolating step. e.g. 'browser_tests'
  target_name = ndb.StringProperty(required=True)

  # An integer representing the number component of the commit position string.
  # e.g. 557975 for 'refs/heads/master@{#557975}'.
  commit_position = ndb.IntegerProperty(required=True)

  # The gerrit patch in host/issue/patchset format
  # e.g. 'chromium-review.googlesource.com/1065898/2'.
  # For builds without patch this is expected to be empty.
  gerrit_patch = ndb.StringProperty(indexed=False)

  # The hash of the isolated target.
  isolated_hash = ndb.StringProperty()

  @ndb.ComputedProperty
  def has_patch(self):
    """Whether the target was built with a patch.

    This is to distinguish possible multiple isolates from a tryjob or cq run.
    """
    return bool(self.gerrit_patch)

  def GetIsolatedHash(self):
    # This fallback is to be able to retrieve old entries (pre Sept. 2018) that
    # were wrongly keyed with the isolated hash alone.
    return self.isolated_hash or self.key.pairs()[0][1]

  @property
  def build_url(self):
    return 'https://ci.chromium.org/b/{}'.format(self.build_id)

  @classmethod
  def _CreateKey(cls, build_id, target_name):
    return ndb.Key(cls, '/'.join([str(build_id), target_name]))

  @classmethod
  def Create(cls, build_id, luci_project, bucket, master_name, builder_name,
             gitiles_host, gitiles_project, gitiles_ref, gerrit_patch,
             target_name, isolated_hash, commit_position):
    return cls(
        key=cls._CreateKey(build_id, target_name),
        build_id=build_id,
        luci_project=luci_project,
        bucket=bucket,
        master_name=master_name,
        builder_name=builder_name,
        gitiles_host=gitiles_host,
        gitiles_project=gitiles_project,
        gitiles_ref=gitiles_ref,
        gerrit_patch=gerrit_patch,
        target_name=target_name,
        commit_position=commit_position,
        isolated_hash=isolated_hash,
    )

  @classmethod
  def FindIsolateBeforeCommitPositionByBucket(cls,
                                              luci_project,
                                              bucket,
                                              builder_name,
                                              gitiles_host,
                                              gitiles_project,
                                              gitiles_ref,
                                              target_name,
                                              commit_position,
                                              limit=1):
    """Gets isolates with the matching config built at previous revisions.

    The reulsts will exclude the revision given.
    """
    return cls.query(
        cls.has_patch == False, cls.luci_project == luci_project,
        cls.bucket == bucket, cls.builder_name == builder_name,
        cls.gitiles_host == gitiles_host,
        cls.gitiles_project == gitiles_project, cls.gitiles_ref == gitiles_ref,
        cls.target_name == target_name, cls.commit_position <
        commit_position).order(-cls.commit_position).fetch(limit=limit)

  @classmethod
  def FindIsolateBeforeCommitPositionByMaster(cls,
                                              master_name,
                                              builder_name,
                                              gitiles_host,
                                              gitiles_project,
                                              gitiles_ref,
                                              target_name,
                                              commit_position,
                                              limit=1):
    """Same as FindIsolateBeforeCommitPosition, but with master_name.

    The results will exclude the revision given and uses master_name instead of
    project + bucket.
    """
    return cls.query(
        cls.has_patch == False, cls.master_name == master_name,
        cls.builder_name == builder_name, cls.gitiles_host == gitiles_host,
        cls.gitiles_project == gitiles_project, cls.gitiles_ref == gitiles_ref,
        cls.target_name == target_name, cls.commit_position <
        commit_position).order(-cls.commit_position).fetch(limit=limit)

  @classmethod
  def FindIsolateAtOrAfterCommitPositionByBucket(cls,
                                                 luci_project,
                                                 bucket,
                                                 builder_name,
                                                 gitiles_host,
                                                 gitiles_project,
                                                 gitiles_ref,
                                                 target_name,
                                                 commit_position,
                                                 limit=1):
    """Gets isolates with the matching config built at or after the revision.

    The results may include the commit postion given.
    """
    return cls.query(cls.has_patch == False, cls.luci_project == luci_project,
                     cls.bucket == bucket, cls.builder_name == builder_name,
                     cls.gitiles_host == gitiles_host,
                     cls.gitiles_project == gitiles_project,
                     cls.gitiles_ref == gitiles_ref,
                     cls.target_name == target_name,
                     cls.commit_position >= commit_position).order(
                         cls.commit_position).fetch(limit=limit)

  @classmethod
  def FindIsolateAtOrAfterCommitPositionByMaster(cls,
                                                 master_name,
                                                 builder_name,
                                                 gitiles_host,
                                                 gitiles_project,
                                                 gitiles_ref,
                                                 target_name,
                                                 commit_position,
                                                 limit=1):
    """Same as FindIsolateAtOrAfterCommitPosition, but with master_name.

    The results may include the commit position given and uses master_name
    instead of project + bucket.
    """
    return cls.query(
        cls.has_patch == False, cls.master_name == master_name,
        cls.builder_name == builder_name, cls.gitiles_host == gitiles_host,
        cls.gitiles_project == gitiles_project, cls.gitiles_ref == gitiles_ref,
        cls.target_name == target_name,
        cls.commit_position >= commit_position).order(
            cls.commit_position).fetch(limit=limit)
