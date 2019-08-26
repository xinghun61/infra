// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {combineReducers} from 'redux';
import {createSelector} from 'reselect';
import {createReducer, createRequestReducer} from './redux-helpers.js';
import {prpcClient} from 'prpc-client-instance.js';
import {objectToMap} from 'shared/helpers.js';
import {userRefToId, userToUserRef} from 'shared/converters.js';

// Actions
const FETCH_START = 'user/FETCH_START';
const FETCH_SUCCESS = 'user/FETCH_SUCCESS';
const FETCH_FAILURE = 'user/FETCH_FAILURE';

export const FETCH_PROJECTS_START = 'user/FETCH_PROJECTS_START';
export const FETCH_PROJECTS_SUCCESS = 'user/FETCH_PROJECTS_SUCCESS';
export const FETCH_PROJECTS_FAILURE = 'user/FETCH_PROJECTS_FAILURE';

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

export const usersByIdReducer = createReducer({}, {
  [FETCH_PROJECTS_SUCCESS]: (state, action) => {
    const newState = {...state};

    action.usersProjects.forEach((userProjects) => {
      const {userRef, ownerOf = [], memberOf = [], contributorTo = [],
        starredProjects = []} = userProjects;

      const userId = userRefToId(userRef);

      newState[userId] = {
        ...newState[userId],
        projects: {
          ownerOf,
          memberOf,
          contributorTo,
          starredProjects,
        },
      };
    });

    return newState;
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
  usersById: usersByIdReducer,
  requests: requestsReducer,
});

// Selectors
export const requests = (state) => state.user.requests;
export const user = (state) => state.user.currentUser || {};
export const userRef = createSelector(user, (user) => userToUserRef(user));
export const prefs = createSelector(user, (user) => objectToMap(user.prefs));

const _usersById = (state) => state.user.usersById || {};
export const usersById = createSelector(_usersById,
    (usersById) => objectToMap(usersById));

export const projectsPerUser = createSelector(usersById, (usersById) => {
  const map = new Map();
  for (const [key, value] of usersById.entries()) {
    if (value.projects) {
      map.set(key, value.projects);
    }
  }
  return map;
});

// Projects for just the current user.
export const projects = createSelector(projectsPerUser, userRef,
    (projectsMap, userRef) => projectsMap.get(userRefToId(userRef)) || {});

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

    const user = resp[0];

    dispatch({
      type: FETCH_SUCCESS,
      user,
      groups: resp[1].groupRefs || [],
    });

    const userRef = userToUserRef(user);

    dispatch(fetchProjects([userRef]));
    dispatch(fetchHotlists(userRef));
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
    dispatch({type: FETCH_PROJECTS_SUCCESS, usersProjects: resp.usersProjects});
  } catch (error) {
    dispatch({type: FETCH_PROJECTS_FAILURE, error});
  }
};

export const fetchHotlists = (userRef) => async (dispatch) => {
  dispatch({type: FETCH_HOTLISTS_START});

  try {
    const resp = await prpcClient.call(
        'monorail.Features', 'ListHotlistsByUser', {user: userRef});

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
