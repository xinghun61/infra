# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Implements ML-style pattern matching to easily construct state machines.

This module allows one to declare a state space and attach actions to specific
points (states) within that state space. As state spaces can become quite large
(the space is the cartesian product of all values for each dimension), an ML
-type pattern matching scheme is used.

The add_match() instance decorator takes kwargs that correspond to dimensions.
The match will match any value for dimensions not specified (subject to
exclusions).  add_match() stacks with itself so multiple matches can apply to
the same action. Actions are functions which return arbitrary lists; these are
often command-line invocations with extra information added in a subsequent
processing pass.

The MatchList ensures all possible states are covered by an action and that no
state has more than one action assigned to it.

In addition to handling state matching and action selection, MatchList also
provides a 'detector registry.' Detectors interpret raw data from the world and
return a value for a dimension. Their main purpose is to separate OS-derived
information from business logic to make the business logic easily testable.

Here is a trivial usage example:

----------

STATESPACE = {
  'pilot': [  # 'pilot' is a dimension of the statespace.
    'not_present',  # 'not_present' is a value of the 'pilot' dimension.
    'present',
  ],
  'fuel': [
    'ample_fuel',
    'no_fuel',
  ]
}

takeoff_check = MatchList(STATESPACE)

@takeoff_check.add_match(
  pilot='pilot_present',
  fuel='ample_fuel')
def _takeoff():
  return ['schedule plane for takeoff')  # Later processing adds in which plane.

@takeoff_check.add_match(
  pilot='not_present')
@takeoff_check.add_match(
  fuel='no_fuel')
def _abort_takeoff():
  return ['call for help']

@takeoff_check.add_detector('pilot')
def _pilot_checker(evidence):
  if evidence.get('plane_seems_piloty'):
    return 'present'
  return 'not_present'

@takeoff_check.add_detector('fuel')
def _fuel_checker(evidence):
  if evidence.get('fuel') > 60:
    return 'ample_fuel',
  return 'no_fuel'

# You can check_and_print_if_error() to debug why a MatchList isn't properly
# constructed.
takeoff_check.check_and_print_if_error()

execution_list = takeoff_check.execution_list({
  'plane_seems_piloty': True,
  'fuel': 80,
})

# execution_list now contains the state, action name, and execution list
# inferred from the evidence.

----------
"""

import functools
import itertools

from infra.libs.decorators.decorators import instance_decorator


def check_before_executing(f):
  """Decorator to verify the MatchList is correctly constructed."""
  @functools.wraps(f)
  def wrapper(self, *args, **kwargs):
    if not self._checked:
      assert self.is_correct, (
          'The MatchList is incorrectly constructed. '
          'Run check_and_print_if_error() for details.')
    return f(self, *args, **kwargs)
  return wrapper


class MatchList(object):
  def __init__(self, statespace):
    self.statespace = statespace
    self.matchers = []
    self.detectors = {}
    self._checked = None

  def _verify_match_kwargs(self, match_kwargs, exclusions):
    """Check that the match_kwargs and exclusions are sane."""
    for k in match_kwargs:
      assert k in self.statespace, (
          '%s is not a valid dimension to match against' % k)
    for k, v in match_kwargs.iteritems():
      assert v in self.statespace[k], (
          '%s is not a valid value for dimension %s' % (v, k))
    if exclusions:
      for k in match_kwargs:
        assert k in self.statespace, (
            '%s is not a valid dimension to exclude on' % k)
      for k, v in exclusions.iteritems():
        for w in v:
          assert w in self.statespace[k], (
              '%s is not a valid value for dimension %s' % (w, k))

  @instance_decorator
  def add_match(self, f, exclusions=None, **match_kwargs):
    """A decorator to match an action with one or many dimensions.

    add_match is applied to functions (actions) and is the core of the
    MatchList. It stacks with itself, allowing complicated match specifications
    to correspond to a single action.

    f is the function being decorated which returns an arbitrary list of
      action items to execute. How that list is interpreted and acted on is up
      to the calling application.

    exclusions is a dict of lists. Each key in the dict corresponds to a
               dimension, and each list is a value of that dimension. The
               match will not fire for *any* of the values for each dimension.
               Primarily this is used to conveniently write compact matches for
               dimensions with a high cardinality.

    match_kwargs' keys are dimensions, and its values are a single value for
                  each dimension. All values are matched for dimensions not
                  specified, excluding any listed in the exclusions list.
                  If match_kwargs is empty, the match matches nothing.

    Example:

    @my_matchlist.add_match(
        banana='present',
        hunger='hungry',
        exclusions={'clothing': ['naked', 'spacesuit']})
    def _eat_banana():
      return ['peel', 'eat', 'compost peel']

    This matches when the banana dimension is 'present' AND the hunger dimension
    is 'hungry' AND the clothing dimension is NOT 'naked' OR 'spacesuit'. As
    clothing may possiby have many states, this obviates the need to write a
    seperate match for each value of clothing that does match.
    """
    assert not self._checked, 'can\'t add after matchlist has been checked'

    if not match_kwargs:  # Do nothing if no match_kwargs.
      return f

    self._verify_match_kwargs(match_kwargs, exclusions)
    self.matchers.append((match_kwargs, exclusions, f))
    return f

  def _lookup(self, state):
    """Match a state to an action.

    If a MatchList is overspecified, it may return multiple actions. An
    underspecified MatchList may return no actions.
    """
    assert sorted(state.keys()) == sorted(self.statespace.keys()), (
        'state was not fully specified')
    matches = set()
    for matcher, exclusions, f in self.matchers:
      # Note that we iterate through matcher's iteritems(), which may only be a
      # subset of dimensions. This lets us 'ignore' dimensions that the match
      # doesn't specify.
      if all(state[k] == v for k, v in matcher.iteritems()):
        if exclusions and any(
            v in exclusions.get(k, []) for k, v in state.iteritems()):
          continue
        matches.add(f)
    return matches

  def _get_all_states(self):
    # Cartesian product of all values across all dimensions. This is a sequence
    # of every possible state in the statespace.
    all_possible_state_values = itertools.product(*self.statespace.itervalues())

    # Add back in the key names to get the state in dict form.
    return [dict(zip(self.statespace.keys(), state))
            for state in all_possible_state_values]

  def _get_matches(self):
    matches = []  # [(state_dict, action_fn), ...]

    all_possible_states = self._get_all_states()
    for state_dict in all_possible_states:
      state_matches = self._lookup(state_dict)
      matches.append((state_dict, state_matches.pop()))
    return matches

  def _get_aberrations(self):
    empties = []  # [state_dict, ...]
    dupes = []    # [(state_dict, [action_fn, action_fn2]), ...]

    all_possible_states = self._get_all_states()
    for state_dict in all_possible_states:
      state_matches = self._lookup(state_dict)
      if not state_matches:
        empties.append(state_dict)
      elif len(state_matches) > 1:
        dupes.append((state_dict, state_matches))

    not_detected = [k for k in self.statespace if k not in self.detectors]
    return dupes, empties, not_detected

  @property
  def is_correct(self):
    if self._checked is None:
      dupes, empties, not_detected = self._get_aberrations()
      self._checked = not (dupes or empties or not_detected)
    return self._checked

  @instance_decorator
  def add_detector(self, f, key):
    """Register a detector function for a specific dimension.

    f is the function to be decorated. It should take evidence provided by an
      application-specific evidence collection function and return a value for
      the specified dimension.

    dimension is the dimension to detect a value for.

    Example:

    @my_matchlist.add_detector('dogs'):
    def _check_for_dogs(evidence):
      dog_count = len(evidence.get('dog_count', []))
      if dog_count > 1:
        return 'many_dogs'
      elif dog_count == 1:
        return 'one_dog'
      return 'no_dogs'
    """

    assert not self._checked, 'can\'t add after matchlist has been verified'
    assert key in self.statespace, 'invalid dimension: %s' % key
    assert key not in self.detectors, 'already added detector for %s' % key
    self.detectors[key] = f
    return f

  def check_and_print_if_error(self):  # pragma: no cover
    """A friendly frontend to is_correct with helpful messages for humans."""
    dupes, empties, not_detected = self._get_aberrations()
    if dupes:
      print 'duplicate entries for:'
      for dup, matches in dupes:
        print '  %s: %s' % (dup, [f.func_name for f in matches])
    if empties:
      print 'empty entries for:'
      for empty in empties:
        print '  ' + str(empty)
    if not_detected:
      print 'dimensions not detected:'
      for n_d in not_detected:
        print '  ' + str(n_d)
    return self.is_correct

  @check_before_executing
  def print_all_states(self):  # pragma: no cover
    """Enumerates all states and their actions. Good for debugging or --help."""
    all_matches = self._get_matches()
    print 'all matches'
    for state, f in all_matches:
      print '  %s: %s' % (state, f.func_name)

  @check_before_executing
  def get_state(self, evidence):
    """Given evidence, return a state.

    evidence is a dict which is provided by the calling application and provided
             all detectors.
    """
    state = dict((k, self.detectors[k](evidence)) for k in self.statespace)
    for dim, value in state.iteritems():
      assert value in self.statespace[dim]
    return state

  @check_before_executing
  def execution_list(self, evidence):
    """Given evidence, return a state, match name, and an action item list.

    evidence is a dict which is provided by the calling application and provided
             all detectors.
    """
    state = self.get_state(evidence)
    func = self._lookup(state).pop()
    return (state, func.func_name, func())
