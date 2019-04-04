// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {combineReducers} from 'redux';
import {createSelector} from 'reselect';
import {createReducer, createRequestReducer} from './redux-helpers.js';

// Actions
const FETCH_CONFIG_START = 'project/FETCH_CONFIG_START';
const FETCH_CONFIG_SUCCESS = 'project/FETCH_CONFIG_SUCCESS';
const FETCH_CONFIG_FAILURE = 'project/FETCH_CONFIG_FAILURE';

const FETCH_TEMPLATES_START = 'project/FETCH_TEMPLATES_START';
const FETCH_TEMPLATES_SUCCESS = 'project/FETCH_TEMPLATES_SUCCESS';
const FETCH_TEMPLATES_FAILURE = 'project/FETCH_TEMPLATES_FAILURE';

/* State Shape
{
  config: Object,
  templates: Array,
  requests: {
    fetchConfig: Object,
    fetchTemplates: Object,
  },
}
*/

// Reducers
const configReducer = createReducer({}, {
  [FETCH_CONFIG_SUCCESS]: (_state, action) => {
    return action.config;
  },
});

const templatesReducer = createReducer([], {
  [FETCH_TEMPLATES_SUCCESS]: (_state, action) => {
    return action.projectTemplates.templates;
  },
});

const requestsReducer = combineReducers({
  fetchConfig: createRequestReducer(
    FETCH_CONFIG_START, FETCH_CONFIG_SUCCESS, FETCH_CONFIG_FAILURE),
  fetchTemplates: createRequestReducer(
    FETCH_TEMPLATES_START, FETCH_TEMPLATES_SUCCESS, FETCH_TEMPLATES_FAILURE),
});

export const reducer = combineReducers({
  config: configReducer,
  templates: templatesReducer,
  requests: requestsReducer,
});

// Selectors
export const project = (state) => state.project;
export const config = createSelector(project, (project) => project.config);

// Look up components by path.
export const componentsMap = createSelector(
  config,
  (config) => {
    if (!config || !config.componentDefs) return new Map();
    const acc = new Map();
    for (const v of config.componentDefs) {
      acc.set(v.path, v);
    }
    return acc;
  }
);

export const fieldDefs = createSelector(
  config, (config) => config && config.fieldDefs);

export const fieldDefsForPhases = createSelector(
  fieldDefs,
  (fieldDefs) => {
    if (!fieldDefs) return [];
    return fieldDefs.filter((f) => f.isPhaseField);
  }
);

export const fieldDefsByApprovalName = createSelector(
  fieldDefs,
  (fieldDefs) => {
    if (!fieldDefs) return new Map();
    const acc = new Map();
    for (const fd of fieldDefs) {
      if (fd.fieldRef && fd.fieldRef.approvalName) {
        if (acc.has(fd.fieldRef.approvalName)) {
          acc.get(fd.fieldRef.approvalName).push(fd);
        } else {
          acc.set(fd.fieldRef.approvalName, [fd]);
        }
      }
    }
    return acc;
  }
);

export const fetchingConfig = (state) => {
  return state.project.requests.fetchConfig.requesting;
};

// Action Creators
export const fetch = (projectName) => async (dispatch) => {
  dispatch(fetchConfig(projectName));
  dispatch(fetchTemplates(projectName));
};

const fetchConfig = (projectName) => async (dispatch) => {
  dispatch({type: FETCH_CONFIG_START});

  const getConfig = window.prpcClient.call(
    'monorail.Projects', 'GetConfig', {projectName});

  // TODO(zhangtiff): Remove this once we properly stub out prpc calls.
  if (!getConfig) return;

  try {
    const resp = await getConfig;
    dispatch({type: FETCH_CONFIG_SUCCESS, config: resp});
  } catch (error) {
    dispatch({type: FETCH_CONFIG_FAILURE, error});
  }
};

const fetchTemplates = (projectName) => async (dispatch) => {
  dispatch({type: FETCH_TEMPLATES_START});

  const listTemplates = window.prpcClient.call(
    'monorail.Projects', 'ListProjectTemplates', {projectName});

  // TODO(zhangtiff): Remove (see above TODO).
  if (!listTemplates) return;

  try {
    const resp = await listTemplates;
    dispatch({type: FETCH_TEMPLATES_SUCCESS, projectTemplates: resp});
  } catch (error) {
    dispatch({type: FETCH_TEMPLATES_FAILURE, error});
  }
};
