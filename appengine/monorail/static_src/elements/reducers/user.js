// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {combineReducers} from 'redux';
import {createReducer, createRequestReducer} from './redux-helpers.js';
import {prpcClient} from 'prpc-client-instance.js';

// Actions
const FETCH_START = 'user/FETCH_START';
const FETCH_SUCCESS = 'user/FETCH_SUCCESS';
const FETCH_FAILURE = 'user/FETCH_FAILURE';

const FETCH_HOTLISTS_START = 'user/FETCH_HOTLISTS_START';
const FETCH_HOTLISTS_SUCCESS = 'user/FETCH_HOTLISTS_SUCCESS';
const FETCH_HOTLISTS_FAILURE = 'user/FETCH_HOTLISTS_FAILURE';

const FETCH_PREFS_START = 'user/FETCH_PREFS_START';
const FETCH_PREFS_SUCCESS = 'user/FETCH_PREFS_SUCCESS';
const FETCH_PREFS_FAILURE = 'user/FETCH_PREFS_FAILURE';

/* State Shape
{
  currentUser: {
    ...user: Object,
    groups: Array,
    hotlists: Array,
    prefs: Map,
  },
  requests: {
    fetch: Object,
    fetchHotlists: Object,
    fetchPrefs: Object,
  },
}
*/

// Reducers
const USER_DEFAULT = {
  groups: [],
  hotlists: [],
  prefs: new Map(),
  prefsLoaded: false,
};

const currentUserReducer = createReducer(USER_DEFAULT, {
  [FETCH_SUCCESS]: (_user, action) => {
    return {
      ...action.user,
      groups: action.groups,
      hotlists: [],
      prefs: new Map(),
    };
  },
  [FETCH_HOTLISTS_SUCCESS]: (user, action) => {
    return {...user, hotlists: action.hotlists};
  },
  [FETCH_PREFS_SUCCESS]: (user, action) => {
    return {
      ...user,
      prefs: action.prefs,
      prefsLoaded: true,
    };
  },
});

const requestsReducer = combineReducers({
  // Request for getting backend metadata related to a user, such as
  // which groups they belong to and whether they're a site admin.
  fetch: createRequestReducer(FETCH_START, FETCH_SUCCESS, FETCH_FAILURE),
  // Request for getting a user's hotlists.
  fetchHotlists: createRequestReducer(
    FETCH_HOTLISTS_START, FETCH_HOTLISTS_SUCCESS, FETCH_HOTLISTS_FAILURE),
  // Request for getting a user's prefs.
  fetchPrefs: createRequestReducer(
    FETCH_PREFS_START, FETCH_PREFS_SUCCESS, FETCH_PREFS_FAILURE),
});

export const reducer = combineReducers({
  currentUser: currentUserReducer,
  requests: requestsReducer,
});

// Selectors
export const user = (state) => state.user.currentUser;

// Action Creators
export const fetch = (displayName) => async (dispatch) => {
  dispatch({type: FETCH_START});

  const message = {
    userRef: {displayName},
  };

  try {
    const resp = await Promise.all([
      prpcClient.call(
        'monorail.Users', 'GetUser', message),
      prpcClient.call(
        'monorail.Users', 'GetMemberships', message),
    ]);

    dispatch({
      type: FETCH_SUCCESS,
      user: resp[0],
      groups: resp[1].groupRefs || [],
    });
    dispatch(fetchHotlists(displayName));
    dispatch(fetchPrefs());
  } catch (error) {
    dispatch({type: FETCH_FAILURE, error});
  };
};

export const fetchHotlists = (displayName) => async (dispatch) => {
  dispatch({type: FETCH_HOTLISTS_START});

  try {
    const resp = await prpcClient.call(
      'monorail.Features', 'ListHotlistsByUser', {user: {displayName}});

    const hotlists = resp.hotlists || [];
    hotlists.sort((hotlistA, hotlistB) => {
      return hotlistA.name.localeCompare(hotlistB.name);
    });
    dispatch({type: FETCH_HOTLISTS_SUCCESS, hotlists});
  } catch (error) {
    dispatch({type: FETCH_HOTLISTS_FAILURE, error});
  };
};

export const fetchPrefs = () => async (dispatch) => {
  dispatch({type: FETCH_PREFS_START});

  try {
    const resp = await prpcClient.call(
      'monorail.Users', 'GetUserPrefs', {});

    const prefs = new Map((resp.prefs || []).map((pref) => {
      return [pref.name, pref.value];
    }));
    dispatch({type: FETCH_PREFS_SUCCESS, prefs});
  } catch (error) {
    dispatch({type: FETCH_PREFS_FAILURE, error});
  };
};

export const setPrefs = (newPrefs) => ({
  type: FETCH_PREFS_SUCCESS,
  prefs: newPrefs,
});
