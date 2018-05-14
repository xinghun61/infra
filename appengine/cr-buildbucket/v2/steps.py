# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides a converter from annotations_pb2.Step to step_pb2.Step.

This is a Python port of
https://chromium.googlesource.com/infra/luci/luci-go/+/82a12f6887aca7c425b26dd6b77329b41617627e/milo/buildsource/buildbot/buildstore/annotations.go
"""

import urllib
import urlparse

from third_party import annotations_pb2

from proto import common_pb2
from proto import step_pb2

# The character used to separate parent-child steps.
STEP_SEP = '|'


def parse_steps(build_ann):
  """Returns a list of step_pb2.Step parsed from a model.BuildAnnotation."""
  ann_step = annotations_pb2.Step()
  ann_step.ParseFromString(build_ann.annotation_binary)
  host, project, prefix, _ = parse_logdog_url(build_ann.annotation_url)
  converter = AnnotationConverter(
      default_logdog_host=host,
      default_logdog_prefix='%s/%s' % (project, prefix),
  )
  return converter.parse_substeps(ann_step.substep)


def parse_logdog_url(url):
  # LogDog URL example:
  #   'logdog://logs.chromium.org/chromium/'
  #   'buildbucket/cr-buildbucket.appspot.com/8953190917205316816/+/annotations'
  u = urlparse.urlparse(url)
  full_path = u.path.strip('/').split('/')
  if (u.scheme != 'logdog' or u.params or u.query or u.fragment or
      len(full_path) < 4 or '+' not in full_path):
    raise ValueError('invalid logdog URL %r' % url)
  project = full_path[0]
  plus_pos = full_path.index('+')
  stream_prefix = '/'.join(full_path[1:plus_pos])
  stream_name = '/'.join(full_path[plus_pos + 1:])
  return u.netloc, project, stream_prefix, stream_name


class AnnotationConverter(object):
  """Converts annotation_pb2.Step to step_pb2.Step."""

  def __init__(self, default_logdog_host, default_logdog_prefix):
    self.default_logdog_host = default_logdog_host
    self.default_logdog_prefix = default_logdog_prefix

  def parse_step(self, ann_step):
    """Converts an annotation_pb2.Step to a step_pb2.Step.

    Ignores substeps.
    """
    ret = step_pb2.Step(
        name=ann_step.name,
        status=self._parse_status(ann_step),
    )
    if ann_step.HasField('started'):
      ret.start_time.CopyFrom(ann_step.started)
    if ann_step.HasField('ended'):
      ret.end_time.CopyFrom(ann_step.ended)

    # list of summary paragraphs.
    # each element is a list of paragraph lines
    summary_paragraph_lines = []
    if ann_step.failure_details.text:
      summary_paragraph_lines.append([ann_step.failure_details.text])

    # Parse links.
    link_lines, logs = self._parse_links(ann_step)
    summary_paragraph_lines.append(link_lines)
    ret.logs.extend(logs)

    # Parse step text.
    # Although annotation.proto says each line in step_text is a consecutive
    # line and should not contain newlines, in practice they are in HTML format
    # may have <br>s, Buildbot joins them with " " and treats the result
    # as safe HTML.
    # https://cs.chromium.org/chromium/build/third_party/buildbot_8_4p1/buildbot/status/web/build.py?sq=package:chromium&rcl=83e20043dedd1db6977c6aa818e66c1f82ff31e1&l=130
    # Preserve this semantics (except, it is not safe).
    # HTML is valid Markdown, so use it as is.
    if ann_step.text:
      summary_paragraph_lines.append([' '.join(ann_step.text)])

    # Compile collected summary.
    assert all(isinstance(lines, list) for lines in summary_paragraph_lines)
    assert all(
        isinstance(line, basestring)
        for lines in summary_paragraph_lines
        for line in lines)
    ret.summary_markdown = '\n\n'.join(
        '\n'.join(lines) for lines in summary_paragraph_lines if lines)
    return ret

  def parse_substeps(self, ann_substeps, name_prefix=''):
    """Parses a list of annotation substeps to a list of v2 steps.

    Returned list includes substeps, recursively.
    """
    ret = []
    for substep in ann_substeps:
      if substep.HasField('step'):  # pragma: no branch
        v2_step = self.parse_step(substep.step)
        v2_step.name = name_prefix + v2_step.name
        ret.append(v2_step)
        ret.extend(
            self.parse_substeps(
                substep.step.substep, name_prefix=v2_step.name + STEP_SEP))
    return ret

  def _parse_status(self, ann_step):
    if ann_step.status == annotations_pb2.RUNNING:
      return common_pb2.STARTED

    if ann_step.status == annotations_pb2.SUCCESS:
      return common_pb2.SUCCESS

    if ann_step.status == annotations_pb2.FAILURE:
      if ann_step.HasField('failure_details'):
        fd = ann_step.failure_details
        if fd.type != annotations_pb2.FailureDetails.GENERAL:
          return common_pb2.INFRA_FAILURE
      return common_pb2.FAILURE

    return common_pb2.STATUS_UNSPECIFIED  # pragma: no cover

  def _parse_links(self, ann_step):
    # Note: annotee never initializes annotations_pb2.Step.link
    all_links = []
    if ann_step.HasField('stdout_stream'):
      all_links.append(
          annotations_pb2.Link(
              label='stdout', logdog_stream=ann_step.stdout_stream))
    if ann_step.HasField('stderr_stream'):
      all_links.append(
          annotations_pb2.Link(
              label='stderr', logdog_stream=ann_step.stderr_stream))
    all_links += list(ann_step.other_links)

    lines = []  # lines in a markdown summary paragraph
    logs = []
    for link in all_links:
      if link.HasField('logdog_stream'):
        # This is the typical case.
        logs.append(
            step_pb2.Step.Log(
                name=link.label,
                view_url=self._logdog_stream_view_url(link.logdog_stream)))
      elif link.url:
        lines.append('* [%s](%s)' % (link.label, link.url))
      else:  # pragma: no cover
        # Experience shows that all link we have in practice are either
        # urls or logdog streams.
        pass
    return lines, logs

  def _logdog_stream_view_url(self, logdog_stream):
    host = logdog_stream.server or self.default_logdog_host
    prefix = logdog_stream.prefix or self.default_logdog_prefix
    path = '%s/+/%s' % (prefix, logdog_stream.name)
    return 'https://%s/v/?s=%s' % (host, urllib.quote(path, safe=''))
