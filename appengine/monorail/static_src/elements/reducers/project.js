// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {combineReducers} from 'redux';
import {createSelector} from 'reselect';
import {createReducer, createRequestReducer} from './redux-helpers.js';
import {fieldTypes} from 'elements/shared/field-types.js';
import {hasPrefix, removePrefix} from 'elements/shared/helpers.js';
import {fieldNameToLabelPrefix} from 'elements/shared/converters.js';
import {prpcClient} from 'prpc-client-instance.js';

// Actions
const FETCH_CONFIG_START = 'project/FETCH_CONFIG_START';
const FETCH_CONFIG_SUCCESS = 'project/FETCH_CONFIG_SUCCESS';
const FETCH_CONFIG_FAILURE = 'project/FETCH_CONFIG_FAILURE';

const FETCH_PRESENTATION_CONFIG_START =
  'project/FETCH_PRESENTATION_CONFIG_START';
const FETCH_PRESENTATION_CONFIG_SUCCESS =
  'project/FETCH_PRESENTATION_CONFIG_SUCCESS';
const FETCH_PRESENTATION_CONFIG_FAILURE =
  'project/FETCH_PRESENTATION_CONFIG_FAILURE';

const FETCH_TEMPLATES_START = 'project/FETCH_TEMPLATES_START';
const FETCH_TEMPLATES_SUCCESS = 'project/FETCH_TEMPLATES_SUCCESS';
const FETCH_TEMPLATES_FAILURE = 'project/FETCH_TEMPLATES_FAILURE';

const FETCH_FIELDS_LIST_START = 'project/FETCH_FIELDS_LIST_START';
const FETCH_FIELDS_LIST_SUCCESS = 'project/FETCH_FIELDS_LIST_SUCCESS';
const FETCH_FIELDS_LIST_FAILURE = 'project/FECTH_FIELDS_LIST_FAILURE';

/* State Shape
{
  config: Object,
  presentationConfig: Object,
  templates: Array,
  fieldsList: Array,
  requests: {
    fetchConfig: Object,
    fetchTemplates: Object,
    fetchFieldsList: Object,
  },
}
*/

// Reducers
const configReducer = createReducer({}, {
  [FETCH_CONFIG_SUCCESS]: (_state, action) => {
    return action.config;
  },
});

const presentationConfigReducer = createReducer({}, {
  [FETCH_PRESENTATION_CONFIG_SUCCESS]: (_state, action) => {
    return action.presentationConfig;
  },
});

const templatesReducer = createReducer([], {
  [FETCH_TEMPLATES_SUCCESS]: (_state, action) => {
    return action.projectTemplates.templates;
  },
});

const fieldsListReducer = createReducer([], {
  [FETCH_FIELDS_LIST_SUCCESS]: (_state, action) => action.fieldsList,
});

const requestsReducer = combineReducers({
  fetchConfig: createRequestReducer(
    FETCH_CONFIG_START, FETCH_CONFIG_SUCCESS, FETCH_CONFIG_FAILURE),
  fetchTemplates: createRequestReducer(
    FETCH_TEMPLATES_START, FETCH_TEMPLATES_SUCCESS, FETCH_TEMPLATES_FAILURE),
  fetchFieldsList: createRequestReducer(
    FETCH_FIELDS_LIST_START,
    FETCH_FIELDS_LIST_SUCCESS,
    FETCH_FIELDS_LIST_FAILURE),
});

export const reducer = combineReducers({
  config: configReducer,
  presentationConfig: presentationConfigReducer,
  templates: templatesReducer,
  requests: requestsReducer,
  fieldsList: fieldsListReducer,
});

// Selectors
export const project = (state) => state.project;
export const fieldsList = (state) => state.project.fieldsList;
export const config = createSelector(project, (project) => project.config);
export const presentationConfig = (state) => state.project.presentationConfig;

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
  config, (config) => ((config && config.fieldDefs) || [])
);

export const labelDefs = createSelector(
  config, (config) => ((config && config.labelDefs) || [])
);

// labelDefs stored in an easily findable format with label names as keys.
export const labelDefMap = createSelector(
  labelDefs, (labelDefs) => {
    const map = new Map();
    labelDefs.forEach((ld) => {
      map.set(ld.label.toLowerCase(), ld);
    });
    return map;
  }
);


export const enumFieldDefs = createSelector(
  fieldDefs,
  (fieldDefs) => {
    return fieldDefs.filter(
      (fd) => fd.fieldRef.type === fieldTypes.ENUM_TYPE);
  }
);

export const optionsPerEnumField = createSelector(
  enumFieldDefs,
  labelDefs,
  (fieldDefs, labelDefs) => {
    const map = new Map(fieldDefs.map(
      (fd) => [fd.fieldRef.fieldName.toLowerCase(), []]));
    labelDefs.forEach((ld) => {
      const labelName = ld.label;

      const fd = fieldDefs.find((fd) => hasPrefix(
        labelName, fieldNameToLabelPrefix(fd.fieldRef.fieldName)));
      if (fd) {
        const key = fd.fieldRef.fieldName.toLowerCase();
        map.get(key).push({
          ...ld,
          optionName: removePrefix(labelName,
            fieldNameToLabelPrefix(fd.fieldRef.fieldName)),
        });
      }
    });
    return map;
  }
);

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
  dispatch(fetchPresentationConfig(projectName));
  dispatch(fetchTemplates(projectName));
};

const fetchConfig = (projectName) => async (dispatch) => {
  dispatch({type: FETCH_CONFIG_START});

  const getConfig = prpcClient.call(
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

export const fetchPresentationConfig = (projectName) => async (dispatch) => {
  dispatch({type: FETCH_PRESENTATION_CONFIG_START});

  try {
    const presentationConfig = await prpcClient.call(
      'monorail.Projects', 'GetPresentationConfig', {projectName});
    dispatch({type: FETCH_PRESENTATION_CONFIG_SUCCESS, presentationConfig});
  } catch (error) {
    dispatch({type: FETCH_PRESENTATION_CONFIG_FAILURE, error});
  }
};

const fetchTemplates = (projectName) => async (dispatch) => {
  dispatch({type: FETCH_TEMPLATES_START});

  const listTemplates = prpcClient.call(
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

export const fetchFieldsList = (projectName) => async (dispatch) => {
  dispatch({type: FETCH_FIELDS_LIST_START});

  try {
    const resp = await prpcClient.call(
      'monorail.Projects', 'ListFields', {
        projectName: projectName,
        includeUserChoices: true,
      }
    );
    const fieldsList = (resp.fieldDefs || []);
    dispatch({type: FETCH_FIELDS_LIST_SUCCESS, fieldsList});
  } catch (error) {
    dispatch({type: FETCH_FIELDS_LIST_FAILURE});
  }
};
