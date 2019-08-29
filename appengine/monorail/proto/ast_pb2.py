# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Protocol buffers for user queries parsed into abstract syntax trees.

A user issue query can look like [Type=Defect owner:jrobbins "memory leak"].
In that simple form, all the individual search conditions are simply ANDed
together.  In the code, a list of conditions to be ANDed is called a
conjunction.

Monorail also supports a quick-or feature: [Type=Defect,Enhancement].  That
will match any issue that has labels Type-Defect or Type-Enhancement, or both.

Monorail supports a top-level "OR" keyword that can
be used to logically OR a series of conjunctions.  For example:
[Type=Defect stars>10 OR Type=Enhancement stars>50].

There are no parenthesis and no "AND" keyword.  So, the AST is always exactly
two levels:  the overall tree consistes of a list of conjunctions, and each
conjunction consists of a list of conditions.

A condition can look like [stars>10] or [summary:memory] or
[Type=Defect,Enhancement].  Each condition has a single comparison operator.
Most conditions refer to a single field definition, but in the case of
cross-project search a single condition can have a list of field definitions
from the different projects being searched.  Each condition can have a list
of constant values to compare against.  The values may be all strings or all
integers.

Some conditions are procesed by the SQL database and others by the GAE
search API.  All conditions are passed to each module and it is up to
the module to decide which conditions to handle and which to ignore.
"""

from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

from protorpc import messages

from proto import tracker_pb2


# This is a special field_name for a FieldDef that means to do a fulltext
# search for words that occur in any part of the issue.
ANY_FIELD = 'any_field'


class QueryOp(messages.Enum):
  """Enumeration of possible query condition operators."""
  EQ = 1
  NE = 2
  LT = 3
  GT = 4
  LE = 5
  GE = 6
  TEXT_HAS = 7
  NOT_TEXT_HAS = 8
  IS_DEFINED = 11
  IS_NOT_DEFINED = 12
  KEY_HAS = 13


class Condition(messages.Message):
  """Representation of one query condition.  E.g., [Type=Defect,Task]."""
  op = messages.EnumField(QueryOp, 1, required=True)
  field_defs = messages.MessageField(tracker_pb2.FieldDef, 2, repeated=True)
  str_values = messages.StringField(3, repeated=True)
  int_values = messages.IntegerField(4, repeated=True)
  # The suffix of a search field
  # eg. the 'approver' in 'UXReview-approver:user@mail.com'
  key_suffix = messages.StringField(5)
  # The name of the phase this field value should belong to.
  phase_name = messages.StringField(6)


class Conjunction(messages.Message):
  """A list of conditions that are implicitly ANDed together."""
  conds = messages.MessageField(Condition, 1, repeated=True)


class QueryAST(messages.Message):
  """Abstract syntax tree for the user's query."""
  conjunctions = messages.MessageField(Conjunction, 1, repeated=True)


def MakeCond(op, field_defs, str_values, int_values,
             key_suffix=None, phase_name=None):
  """Shorthand function to construct a Condition PB."""
  return Condition(
      op=op, field_defs=field_defs, str_values=str_values,
      int_values=int_values, key_suffix=key_suffix, phase_name=phase_name)
