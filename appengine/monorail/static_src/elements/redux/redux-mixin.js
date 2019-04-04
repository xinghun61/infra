// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {createMixin} from 'polymer-redux';
import {applyMiddleware, combineReducers, compose, createStore} from 'redux';
import thunk from 'redux-thunk';
import {createReducer} from './redux-helpers.js';
import * as issue from './issue.js';
import * as project from './project.js';
import * as user from './user.js';

// Actions
const RESET_STATE = 'RESET_STATE';
const REPORT_DIRTY_FORM = 'REPORT_DIRTY_FORM';
const CLEAR_DIRTY_FORMS = 'CLEAR_DIRTY_FORMS';
const SET_FOCUS_ID = 'SET_FOCUS_ID';

/* State Shape
{
  issue: Object,
  project: Object,
  user: Object,

  dirtyForms: Array,
  focusId: String,
}
*/

// Reducers
const dirtyFormsReducer = createReducer([], {
  [REPORT_DIRTY_FORM]: (state, action) => {
    const newState = [...state];
    const index = state.indexOf(action.name);
    if (action.isDirty && index === -1) {
      newState.push(action.name);
    } else if (!action.isDirty && index !== -1) {
      newState.splice(index, 1);
    }
    return newState;
  },
  [CLEAR_DIRTY_FORMS]: () => [],
});

const focusIdReducer = createReducer(null, {
  [SET_FOCUS_ID]: (_state, action) => action.focusId,
});

const reducer = combineReducers({
  issue: issue.reducer,
  project: project.reducer,
  user: user.reducer,

  // Forms to be checked for user changes before leaving the page.
  dirtyForms: dirtyFormsReducer,

  // The ID of the element to be focused, as given by the hash part of the URL.
  focusId: focusIdReducer,
});

function rootReducer(state, action) {
  if (action.type == RESET_STATE) {
    state = undefined;
  }
  return reducer(state, action);
}

// Selectors

// Action Creators
export const resetState = () => ({type: RESET_STATE});

export const reportDirtyForm = (name, isDirty) => {
  return {type: REPORT_DIRTY_FORM, name, isDirty};
};
export const clearDirtyForms = () => ({type: CLEAR_DIRTY_FORMS});
export const setFocusId = (focusId) => {
  return {type: SET_FOCUS_ID, focusId};
};

// Store

// For debugging with the Redux Devtools extension:
// https://chrome.google.com/webstore/detail/redux-devtools/lmhkpmbekcpmknklioeibfkpmmfibljd/
const composeEnhancers = window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__ || compose;
export const store = createStore(rootReducer, composeEnhancers(
  applyMiddleware(thunk)
));

export const ReduxMixin = createMixin(store);
