# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from components import utils

import metrics


class NumberSequence(ndb.Model):
  """A named number sequence.

  Entity key:
    ID is the name of the sequence.
    NumberSequence has no parent.
  """
  # Next number in the sequence.
  next_number = ndb.IntegerProperty(default=1, indexed=False)


@ndb.tasklet
def generate_async(seq_name, count):
  """Generates sequence numbers.

  Supports up to 5 QPS. If we need more, we will need to implement something
  more advanced.

  Args:
    name: name of the sequence.
    count: number of sequence numbers to allocate.

  Returns:
    The generated number. For a returned number i, numbers [i, i+count) can be
    used by the caller.
  """
  @ndb.transactional_tasklet
  def txn():
    seq = (
      (yield NumberSequence.get_by_id_async(seq_name))
      or NumberSequence(id=seq_name))
    result = seq.next_number
    seq.next_number += count
    yield seq.put_async()
    raise ndb.Return(result)

  started = utils.utcnow()
  number = yield txn()
  ellapsed_ms = (utils.utcnow() - started).total_seconds() * 1000
  if ellapsed_ms > 1000:  # pragma: no cover
    logging.error(
        'sequence number generation took > 1s\n'
        'it took %dms\n'
        'sequence: %s',
        ellapsed_ms, seq_name)
  else:
    logging.info('sequence number generation took %dms', ellapsed_ms)
  metrics.SEQUENCE_NUMBER_GEN_DURATION_MS.add(
      ellapsed_ms, fields={'sequence': seq_name})
  raise ndb.Return(number)


@ndb.transactional
def set_next(seq_name, next_number):
  """Sets the next number to generate.

  Args:
    name: name of the sequence.
    next_number: the next number. Cannot be less than the number
      that would be generated otherwise.

  Raises:
    ValueError if the supplied number is too small.
  """
  assert isinstance(next_number, int)
  seq = NumberSequence.get_by_id(seq_name) or NumberSequence(id=seq_name)
  if next_number == seq.next_number:
    return
  elif next_number < seq.next_number:
    raise ValueError('next number must be at least %d' % seq.next_number)
  seq.next_number = next_number
  seq.put()


@ndb.transactional_tasklet
def try_return_async(seq_name, number):
  """Attempts to return the generated number back to the sequence.

  Returns False if the number wasn't returned and cannot be reused by someone
  else.
  """
  seq = yield NumberSequence.get_by_id_async(seq_name)
  if not seq:
    # If there is not sequence entity, the number can be used by someone else.
    raise ndb.Return(True)
  if seq.next_number != number + 1:
    raise ndb.Return(False)
  seq.next_number = number
  yield seq.put_async()
  raise ndb.Return(True)
