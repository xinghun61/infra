// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {combineReducers} from 'redux';
import {createSelector} from 'reselect';
import {createReducer, createRequestReducer} from './redux-helpers.js';
import {prpcClient} from 'prpc-client-instance.js';
import {objectToMap} from 'shared/helpers.js';
import {userRefToId, userToUserRef} from 'shared/converters.js';
import loadGapi, {fetchGapiEmail} from 'shared/gapi-loader.js';

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

const GAPI_LOGIN_START = 'GAPI_LOGIN_START';
export const GAPI_LOGIN_SUCCESS = 'GAPI_LOGIN_SUCCESS';
const GAPI_LOGIN_FAILURE = 'GAPI_LOGIN_FAILURE';

const GAPI_LOGOUT_START = 'GAPI_LOGOUT_START';
export const GAPI_LOGOUT_SUCCESS = 'GAPI_LOGOUT_SUCCESS';
const GAPI_LOGOUT_FAILURE = 'GAPI_LOGOUT_FAILURE';

/* State Shape
{
  currentUser: {
    ...user: Object,
    groups: Array,
    hotlists: Array,
    prefs: Object,
    gapiEmail: String,
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

const gapiEmailReducer = (user, action) => {
  return {
    ...user,
    gapiEmail: action.email || '',
  };
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
  [GAPI_LOGIN_SUCCESS]: gapiEmailReducer,
  [GAPI_LOGOUT_SUCCESS]: gapiEmailReducer,
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
// TODO(zhangtiff): Replace custom logic to check if the user is logged in
// across the frontend.
export const isLoggedIn = createSelector(user, (user) => user && user.userId);
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

/**
 * Action creator to initiate the gapi.js login flow.
 *
 * @return {Promise} Resolved only when gapi.js login succeeds.
 */
export const initGapiLogin = () => (dispatch) => {
  dispatch({type: GAPI_LOGIN_START});

  return new Promise(async (resolve) => {
    try {
      await loadGapi();
      gapi.auth2.getAuthInstance().signIn().then(async () => {
        const email = await fetchGapiEmail();
        dispatch({type: GAPI_LOGIN_SUCCESS, email: email});
        resolve();
      });
    } catch (error) {
      // TODO(jeffcarp): Pop up a message that signIn failed.
      dispatch({type: GAPI_LOGIN_FAILURE, error});
    }
  });
};

/**
 * Action creator to log the user out of gapi.js
 *
 * @return {undefined}
 */
export const initGapiLogout = () => async (dispatch) => {
  dispatch({type: GAPI_LOGOUT_START});

  try {
    await loadGapi();
    gapi.auth2.getAuthInstance().signOut().then(() => {
      dispatch({type: GAPI_LOGOUT_SUCCESS, email: ''});
    });
  } catch (error) {
    // TODO(jeffcarp): Pop up a message that signOut failed.
    dispatch({type: GAPI_LOGOUT_FAILURE, error});
  }
};
