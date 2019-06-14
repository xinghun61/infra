// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {combineReducers} from 'redux';
import {createReducer} from './redux-helpers.js';

// Actions
const INCREMENT_NAVIGATION_COUNT = 'INCREMENT_NAVIGATION_COUNT';
const REPORT_DIRTY_FORM = 'REPORT_DIRTY_FORM';
const CLEAR_DIRTY_FORMS = 'CLEAR_DIRTY_FORMS';
const SET_FOCUS_ID = 'SET_FOCUS_ID';

/* State Shape
{
  navigationCount: Number,
  dirtyForms: Array,
  focusId: String,
}
*/

// Reducers
const navigationCountReducer = createReducer(0, {
  [INCREMENT_NAVIGATION_COUNT]: (state) => state + 1,
});

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

export const reducer = combineReducers({
  // Count of "page" navigations.
  navigationCount: navigationCountReducer,
  // Forms to be checked for user changes before leaving the page.
  dirtyForms: dirtyFormsReducer,
  // The ID of the element to be focused, as given by the hash part of the URL.
  focusId: focusIdReducer,
});

// Selectors
export const navigationCount = (state) => state.ui.navigationCount;
export const dirtyForms = (state) => state.ui.dirtyForms;
export const focusId = (state) => state.ui.focusId;

// Action Creators
export const incrementNavigationCount = () => {
  return {type: INCREMENT_NAVIGATION_COUNT};
};

export const reportDirtyForm = (name, isDirty) => {
  return {type: REPORT_DIRTY_FORM, name, isDirty};
};
export const clearDirtyForms = () => ({type: CLEAR_DIRTY_FORMS});

export const setFocusId = (focusId) => {
  return {type: SET_FOCUS_ID, focusId};
};
