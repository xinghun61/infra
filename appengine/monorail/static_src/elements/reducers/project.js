// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {combineReducers} from 'redux';
import {createSelector} from 'reselect';
import {createReducer, createRequestReducer} from './redux-helpers.js';
import {fieldTypes} from 'elements/shared/issue-fields.js';
import {hasPrefix, removePrefix} from 'elements/shared/helpers.js';
import {fieldNameToLabelPrefix,
  labelNameToLabelPrefix} from 'elements/shared/converters.js';
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
  requests: {
    fetchConfig: Object,
    fetchTemplates: Object,
    fetchFields: Object,
  },
}
*/

// Reducers
const configReducer = createReducer({}, {
  [FETCH_CONFIG_SUCCESS]: (_state, action) => {
    return action.config;
  },
  [FETCH_FIELDS_LIST_SUCCESS]: (state, action) => {
    return {
      ...state,
      fieldDefs: action.fieldDefs,
    };
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

const requestsReducer = combineReducers({
  fetchConfig: createRequestReducer(
    FETCH_CONFIG_START, FETCH_CONFIG_SUCCESS, FETCH_CONFIG_FAILURE),
  fetchTemplates: createRequestReducer(
    FETCH_TEMPLATES_START, FETCH_TEMPLATES_SUCCESS, FETCH_TEMPLATES_FAILURE),
  fetchFields: createRequestReducer(
    FETCH_FIELDS_LIST_START,
    FETCH_FIELDS_LIST_SUCCESS,
    FETCH_FIELDS_LIST_FAILURE),
});

export const reducer = combineReducers({
  config: configReducer,
  presentationConfig: presentationConfigReducer,
  templates: templatesReducer,
  requests: requestsReducer,
});

// Selectors
export const project = (state) => state.project;
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

export const fieldDefMap = createSelector(
  fieldDefs, (fieldDefs) => {
    const map = new Map();
    fieldDefs.forEach((fd) => {
      map.set(fd.fieldRef.fieldName.toLowerCase(), fd);
    });
    return map;
  }
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

// Find the options that exist for a given label prefix.
export const labelPrefixOptions = createSelector(
  labelDefs, (labelDefs) => {
    const prefixMap = new Map();
    labelDefs.forEach((ld) => {
      const prefix = labelNameToLabelPrefix(ld.label).toLowerCase();

      if (prefixMap.has(prefix)) {
        prefixMap.get(prefix).push(ld.label);
      } else {
        prefixMap.set(prefix, [ld.label]);
      }
    });

    return prefixMap;
  }
);

// Some labels are implicitly used as custom fields in the grid and list view.
// Make this an Array to keep casing in tact.
export const labelPrefixFields = createSelector(
  labelPrefixOptions, (map) => {
    const prefixes = [];

    map.forEach((options) => {
      // Ignore label prefixes with only one value.
      if (options.length > 1) {
        // Pick the first label defined to set the casing for the prefix value.
        // This shouldn't be too important of a decision because most labels
        // with shared prefixes should use the same casing across labels.
        prefixes.push(labelNameToLabelPrefix(options[0]));
      }
    });

    return prefixes;
  }
);

// Wrap label prefixes in a Set for fast lookup.
export const labelPrefixSet = createSelector(
  labelPrefixFields, (fields) => new Set(fields.map(
    (field) => field.toLowerCase())),
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
  // TODO(zhangtiff): Split up GetConfig into multiple calls to
  // GetLabelOptions, ListComponents, etc.
  // dispatch(fetchFields(projectName));
  dispatch(fetchPresentationConfig(projectName));
  dispatch(fetchTemplates(projectName));
};

const fetchConfig = (projectName) => async (dispatch) => {
  dispatch({type: FETCH_CONFIG_START});

  const getConfig = prpcClient.call(
    'monorail.Projects', 'GetConfig', {projectName});

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

export const fetchFields = (projectName) => async (dispatch) => {
  dispatch({type: FETCH_FIELDS_LIST_START});

  try {
    const resp = await prpcClient.call(
      'monorail.Projects', 'ListFields', {
        projectName: projectName,
        includeUserChoices: true,
      }
    );
    const fieldDefs = (resp.fieldDefs || []);
    dispatch({type: FETCH_FIELDS_LIST_SUCCESS, fieldDefs});
  } catch (error) {
    dispatch({type: FETCH_FIELDS_LIST_FAILURE});
  }
};
