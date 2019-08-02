// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {combineReducers} from 'redux';
import {createSelector} from 'reselect';
import {createReducer, createRequestReducer} from './redux-helpers.js';
import {prpcClient} from 'prpc-client-instance.js';

// Actions
const FETCH_START = 'user/FETCH_START';
const FETCH_SUCCESS = 'user/FETCH_SUCCESS';
const FETCH_FAILURE = 'user/FETCH_FAILURE';

const FETCH_PROJECTS_START = 'user/FETCH_PROJECTS_START';
const FETCH_PROJECTS_SUCCESS = 'user/FETCH_PROJECTS_SUCCESS';
const FETCH_PROJECTS_FAILURE = 'user/FETCH_PROJECTS_FAILURE';

const FETCH_HOTLISTS_START = 'user/FETCH_HOTLISTS_START';
const FETCH_HOTLISTS_SUCCESS = 'user/FETCH_HOTLISTS_SUCCESS';
const FETCH_HOTLISTS_FAILURE = 'user/FETCH_HOTLISTS_FAILURE';

const FETCH_PREFS_START = 'user/FETCH_PREFS_START';
const FETCH_PREFS_SUCCESS = 'user/FETCH_PREFS_SUCCESS';
const FETCH_PREFS_FAILURE = 'user/FETCH_PREFS_FAILURE';

export const SET_PREFS_START = 'user/SET_PREFS_START';
export const SET_PREFS_SUCCESS = 'user/SET_PREFS_SUCCESS';
export const SET_PREFS_FAILURE = 'user/SET_PREFS_FAILURE';

/* State Shape
{
  currentUser: {
    ...user: Object,
    groups: Array,
    hotlists: Array,
    prefs: Object,
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
  projects: {},
  prefs: {},
  prefsLoaded: false,
};

export const currentUserReducer = createReducer(USER_DEFAULT, {
  [FETCH_SUCCESS]: (_user, action) => {
    return {
      ...USER_DEFAULT,
      ...action.user,
      groups: action.groups,
    };
  },
  [FETCH_PROJECTS_SUCCESS]: (user, action) => {
    return {...user, projects: action.projects};
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
  [SET_PREFS_SUCCESS]: (user, action) => {
    const newPrefs = action.newPrefs;
    const prefs = Object.assign({}, user.prefs);
    newPrefs.forEach(({name, value}) => {
      prefs[name] = value;
    });
    return {
      ...user,
      prefs,
    };
  },
});

const requestsReducer = combineReducers({
  // Request for getting backend metadata related to a user, such as
  // which groups they belong to and whether they're a site admin.
  fetch: createRequestReducer(FETCH_START, FETCH_SUCCESS, FETCH_FAILURE),
  // Requests for fetching projects a user is related to.
  fetchProjects: createRequestReducer(
    FETCH_PROJECTS_START, FETCH_PROJECTS_SUCCESS, FETCH_PROJECTS_FAILURE),
  // Request for getting a user's hotlists.
  fetchHotlists: createRequestReducer(
    FETCH_HOTLISTS_START, FETCH_HOTLISTS_SUCCESS, FETCH_HOTLISTS_FAILURE),
  // Request for getting a user's prefs.
  fetchPrefs: createRequestReducer(
    FETCH_PREFS_START, FETCH_PREFS_SUCCESS, FETCH_PREFS_FAILURE),
  // Request for setting a user's prefs.
  setPrefs: createRequestReducer(
    SET_PREFS_START, SET_PREFS_SUCCESS, SET_PREFS_FAILURE),
});

export const reducer = combineReducers({
  currentUser: currentUserReducer,
  requests: requestsReducer,
});

// Selectors
export const requests = (state) => state.user.requests;
export const user = (state) => state.user.currentUser;
export const prefs = createSelector(user, (user) => {
  const prefsMap = new Map();
  if (user) {
    Object.keys(user.prefs).forEach((key) => {
      prefsMap.set(key, user.prefs[key]);
    });
  }
  return prefsMap;
});

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
    dispatch(fetchProjects([{displayName}]));
    dispatch(fetchHotlists(displayName));
    dispatch(fetchPrefs());
  } catch (error) {
    dispatch({type: FETCH_FAILURE, error});
  };
};

export const fetchProjects = (userRefs) => async (dispatch) => {
  dispatch({type: FETCH_PROJECTS_START});
  try {
    const resp = await prpcClient.call(
      'monorail.Users', 'GetUsersProjects', {userRefs});

    // TODO(zhangtiff): Generalize this to work for multiple users. This will
    // require refactoring the reducer and store shape a bit.
    resp.usersProjects.forEach((proj) => delete proj.userRef);
    dispatch({type: FETCH_PROJECTS_SUCCESS, projects: resp.usersProjects[0]});
  } catch (error) {
    dispatch({type: FETCH_PROJECTS_FAILURE, error});
  }
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
    const prefs = {};
    (resp.prefs || []).forEach(({name, value}) => {
      prefs[name] = value;
    });
    dispatch({type: FETCH_PREFS_SUCCESS, prefs});
  } catch (error) {
    dispatch({type: FETCH_PREFS_FAILURE, error});
  };
};

/**
 * Action creator for setting a user's preferences.
 *
 * @param {Object} newPrefs
 * @param {boolean} saveChanges
 *
 * @return {undefined}
 */
export const setPrefs = (newPrefs, saveChanges = true) => async (dispatch) => {
  if (!saveChanges) {
    dispatch({type: SET_PREFS_SUCCESS, newPrefs});
    return;
  }

  dispatch({type: SET_PREFS_START});

  try {
    const message = {prefs: newPrefs};
    await prpcClient.call(
      'monorail.Users', 'SetUserPrefs', message);
    dispatch({type: SET_PREFS_SUCCESS, newPrefs});

    // Re-fetch the user's prefs after saving to prevent prefs from
    // getting out of sync.
    dispatch(fetchPrefs());
  } catch (error) {
    dispatch({type: SET_PREFS_ERROR, error});
  }
};
