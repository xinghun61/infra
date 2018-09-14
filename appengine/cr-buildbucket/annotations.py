# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions specific to annotation protobuf message.

TODO(nodir): delete this file. Instead accept buidbucket.v2.Build from kitchen.
"""

import urllib

from third_party import annotations_pb2

from proto import common_pb2
from proto import step_pb2
import logdog

# The character used to separate parent-child steps.
STEP_SEP = '|'

# Order for determining status of the parent step based on child steps. The
# status with smallest precedence is used for the parent step. See spec here:
# https://chromium.googlesource.com/infra/luci/luci-go/+/c7ef2b0/buildbucket/proto/step.proto#62
STATUS_PRECEDENCE = {
    common_pb2.CANCELED: 0,
    common_pb2.INFRA_FAILURE: 1,
    common_pb2.FAILURE: 2,
    common_pb2.SUCCESS: 3,
}


class StepParser(object):
  """Converts annotation_pb2.Step to step_pb2.Step.

  This is a Python port of
  https://chromium.googlesource.com/infra/luci/luci-go/+/82a12f6887aca7c425b26dd6b77329b41617627e/milo/buildsource/buildbot/buildstore/annotations.go
  """

  def __init__(self, default_logdog_host, default_logdog_prefix):
    self.default_logdog_host = default_logdog_host
    self.default_logdog_prefix = default_logdog_prefix

  def parse_step(self, ann_step, bb_substeps, name=None):
    """Converts an annotation_pb2.Step to a step_pb2.Step.

    Args:
      ann_step: Annotation step.
      bb_substeps: Buildbucket substeps of the current step.
      name: Overrides name specified in the ann_step.

    Returns:
      Parsed buildbucket step.
    """
    ret = step_pb2.Step(
        name=name or ann_step.name,
        status=self._parse_status(ann_step, bb_substeps),
    )

    # Compute start/end time.
    start_time_list = [ann_step.started] if ann_step.HasField('started') else []
    start_time_list += [
        s.start_time for s in bb_substeps if s.HasField('start_time')
    ]
    if start_time_list:
      ret.start_time.CopyFrom(
          min(start_time_list, key=lambda t: t.ToDatetime())
      )

    end_time_list = [ann_step.ended] if ann_step.HasField('ended') else []
    end_time_list += [s.end_time for s in bb_substeps if s.HasField('end_time')]
    if end_time_list:
      ret.end_time.CopyFrom(max(end_time_list, key=lambda t: t.ToDatetime()))

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
        for line in lines
    )
    ret.summary_markdown = '\n\n'.join(
        '\n'.join(lines) for lines in summary_paragraph_lines if lines
    )
    return ret

  def parse_substeps(
      self, ann_substeps, name_prefix='', ret_direct_substeps=None
  ):
    """Parses a list of annotation substeps to a list of v2 steps.

    Args:
      ann_substeps: List of annotations_pb2.Step entries.
      name_prefix: Prefix to be added to parsed step names.
      ret_direct_substeps: List, which will be populated with direct substeps.

    Returns:
      List of recursively parsed substeps (step_pb2.Step).
    """
    ret = []
    for substep in ann_substeps:
      if substep.HasField('step'):  # pragma: no branch
        # Process descendants first to collect direct substeps.
        direct_substeps = []
        prefixed_name = name_prefix + substep.step.name
        recursive_substeps = self.parse_substeps(
            substep.step.substep,
            name_prefix=prefixed_name + STEP_SEP,
            ret_direct_substeps=direct_substeps,
        )

        # Convert current step and update returned values.
        v2_step = self.parse_step(substep.step, direct_substeps, prefixed_name)
        ret.append(v2_step)
        ret.extend(recursive_substeps)
        if ret_direct_substeps is not None:
          ret_direct_substeps.append(v2_step)
    return ret

  def _parse_status(self, ann_step, bb_substeps):
    if ann_step.status == annotations_pb2.RUNNING:
      return common_pb2.STARTED

    if ann_step.status == annotations_pb2.SUCCESS:
      bb_status = common_pb2.SUCCESS
    elif ann_step.status == annotations_pb2.FAILURE:
      if ann_step.HasField('failure_details'):
        fail_type = ann_step.failure_details.type
        if fail_type == annotations_pb2.FailureDetails.GENERAL:
          bb_status = common_pb2.FAILURE
        elif fail_type == annotations_pb2.FailureDetails.CANCELLED:
          bb_status = common_pb2.CANCELED
        else:
          bb_status = common_pb2.INFRA_FAILURE
      else:
        bb_status = common_pb2.FAILURE
    else:  # pragma: no cover
      return common_pb2.STATUS_UNSPECIFIED

    # When parent step finishes running, compute its final status as worst
    # status, as determined by STATUS_PRECEDENCE dict above, among direct
    # children and its own status.
    for bb_substep in bb_substeps:
      if (bb_substep.status in STATUS_PRECEDENCE and  # pragma: no branch
          STATUS_PRECEDENCE[bb_substep.status] < STATUS_PRECEDENCE[bb_status]):
        bb_status = bb_substep.status

    return bb_status

  def _parse_links(self, ann_step):
    # Note: annotee never initializes annotations_pb2.Step.link
    all_links = []
    if ann_step.HasField('stdout_stream'):
      all_links.append(
          annotations_pb2.Link(
              label='stdout', logdog_stream=ann_step.stdout_stream
          )
      )
    if ann_step.HasField('stderr_stream'):
      all_links.append(
          annotations_pb2.Link(
              label='stderr', logdog_stream=ann_step.stderr_stream
          )
      )
    all_links += list(ann_step.other_links)

    lines = []  # lines in a markdown summary paragraph
    logs = []
    for link in all_links:
      if link.HasField('logdog_stream'):
        # This is the typical case.
        logs.append(
            step_pb2.Step.Log(
                name=link.label,
                url=self._logdog_stream_url(link.logdog_stream, view_url=False),
                view_url=self._logdog_stream_url(
                    link.logdog_stream, view_url=True
                ),
            )
        )
      elif link.url:
        lines.append('* [%s](%s)' % (link.label, link.url))
      else:  # pragma: no cover
        # Experience shows that all link we have in practice are either
        # urls or logdog streams.
        pass
    return lines, logs

  def _logdog_stream_url(self, logdog_stream, view_url):
    host = logdog_stream.server or self.default_logdog_host
    prefix = logdog_stream.prefix or self.default_logdog_prefix
    path = '%s/+/%s' % (prefix, logdog_stream.name)
    if view_url:
      return 'https://%s/v/?s=%s' % (host, urllib.quote(path, safe=''))
    return 'logdog://%s/%s' % (host, path)
