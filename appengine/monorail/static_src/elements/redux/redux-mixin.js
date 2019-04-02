// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {createMixin} from 'polymer-redux';
import {applyMiddleware, combineReducers, compose, createStore} from 'redux';
import thunk from 'redux-thunk';
import {createReducer, createRequestReducer} from './redux-helpers.js';
import * as project from './project.js';
import * as user from './user.js';

export const actionType = {
  // Misc global state.
  RESET_STATE: 'RESET_STATE',
  UPDATE_ISSUE_REF: 'UPDATE_ISSUE_REF',
  REPORT_DIRTY_FORM: 'REPORT_DIRTY_FORM',
  CLEAR_DIRTY_FORMS: 'CLEAR_DIRTY_FORMS',
  SET_FOCUS_ID: 'SET_FOCUS_ID',

  // AJAX request state.
  FETCH_ISSUE_START: 'FETCH_ISSUE_START',
  FETCH_ISSUE_SUCCESS: 'FETCH_ISSUE_SUCCESS',
  FETCH_ISSUE_FAILURE: 'FETCH_ISSUE_FAILURE',

  FETCH_ISSUE_HOTLISTS_START: 'FETCH_ISSUE_HOTLISTS_START',
  FETCH_ISSUE_HOTLISTS_SUCCESS: 'FETCH_ISSUE_HOTLISTS_SUCCESS',
  FETCH_ISSUE_HOTLISTS_FAILURE: 'FETCH_ISSUE_HOTLISTS_FAILURE',

  FETCH_ISSUE_PERMISSIONS_START: 'FETCH_ISSUE_PERMISSIONS_START',
  FETCH_ISSUE_PERMISSIONS_SUCCESS: 'FETCH_ISSUE_PERMISSIONS_SUCCESS',
  FETCH_ISSUE_PERMISSIONS_FAILURE: 'FETCH_ISSUE_PERMISSIONS_FAILURE',

  STAR_ISSUE_START: 'STAR_ISSUE_START',
  STAR_ISSUE_SUCCESS: 'STAR_ISSUE_SUCCESS',
  STAR_ISSUE_FAILURE: 'STAR_ISSUE_FAILURE',

  PRESUBMIT_ISSUE_START: 'PRESUBMIT_ISSUE_START',
  PRESUBMIT_ISSUE_SUCCESS: 'PRESUBMIT_ISSUE_SUCCESS',
  PRESUBMIT_ISSUE_FAILURE: 'PRESUBMIT_ISSUE_FAILURE',

  FETCH_IS_STARRED_START: 'FETCH_IS_STARRED_START',
  FETCH_IS_STARRED_SUCCESS: 'FETCH_IS_STARRED_SUCCESS',
  FETCH_IS_STARRED_FAILURE: 'FETCH_IS_STARRED_FAILURE',

  FETCH_COMMENTS_START: 'FETCH_COMMENTS_START',
  FETCH_COMMENTS_SUCCESS: 'FETCH_COMMENTS_SUCCESS',
  FETCH_COMMENTS_FAILURE: 'FETCH_COMMENTS_FAILURE',

  FETCH_COMMENT_REFERENCES_START: 'FETCH_COMMENT_REFERENCES_START',
  FETCH_COMMENT_REFERENCES_SUCCESS: 'FETCH_COMMENT_REFERENCES_SUCCESS',
  FETCH_COMMENT_REFERENCES_FAILURE: 'FETCH_COMMENT_REFERENCES_FAILURE',

  FETCH_RELATED_ISSUES_START:
    'FETCH_RELATED_ISSUES_START',
  FETCH_RELATED_ISSUES_SUCCESS:
    'FETCH_RELATED_ISSUES_SUCCESS',
  FETCH_RELATED_ISSUES_FAILURE:
    'FETCH_RELATED_ISSUES_FAILURE',

  CONVERT_ISSUE_START: 'CONVERT_ISSUE_START',
  CONVERT_ISSUE_SUCCESS: 'CONVERT_ISSUE_SUCCESS',
  CONVERT_ISSUE_FAILURE: 'CONVERT_ISSUE_FAILURE',

  UPDATE_ISSUE_START: 'UPDATE_ISSUE_START',
  UPDATE_ISSUE_SUCCESS: 'UPDATE_ISSUE_SUCCESS',
  UPDATE_ISSUE_FAILURE: 'UPDATE_ISSUE_FAILURE',

  UPDATE_APPROVAL_START: 'UPDATE_APPROVAL_START',
  UPDATE_APPROVAL_SUCCESS: 'UPDATE_APPROVAL_SUCCESS',
  UPDATE_APPROVAL_FAILURE: 'UPDATE_APPROVAL_FAILURE',
};

// Helpers for the reducers.
const updateIssueApproval = (issue, approval) => {
  if (!issue.approvalValues) return issue;
  const newApprovals = issue.approvalValues.map((item, i) => {
    if (item.fieldRef.fieldName === approval.fieldRef.fieldName) {
      // PhaseRef isn't populated on the response so we want to make sure
      // it doesn't overwrite the original phaseRef with {}.
      const a = {...approval, phaseRef: item.phaseRef};
      return a;
    }
    return item;
  });
  return {...issue, approvalValues: newApprovals};
};

const localIdReducer = createReducer(0, {
  [actionType.UPDATE_ISSUE_REF]: (state, action) => action.localId || state,
});

const projectNameReducer = createReducer('', {
  [actionType.UPDATE_ISSUE_REF]: (state, action) => action.projectName || state,
});

const currentIssueReducer = createReducer({}, {
  [actionType.FETCH_ISSUE_SUCCESS]: (_state, action) => action.issue,
  [actionType.STAR_ISSUE_SUCCESS]: (state, action) => {
    return {...state, starCount: action.starCount};
  },
  [actionType.CONVERT_ISSUE_SUCCESS]: (_state, action) => action.issue,
  [actionType.UPDATE_ISSUE_SUCCESS]: (_state, action) => action.issue,
  [actionType.UPDATE_APPROVAL_SUCCESS]: (state, action) => {
    return updateIssueApproval(state, action.approval);
  },
});

const issueHotlistsReducer = createReducer([], {
  [actionType.FETCH_ISSUE_HOTLISTS_SUCCESS]: (_, action) => action.hotlists,
});

const commentsReducer = createReducer([], {
  [actionType.FETCH_COMMENTS_SUCCESS]: (_state, action) => action.comments,
});

const commentReferencesReducer = createReducer(new Map(), {
  [actionType.FETCH_COMMENTS_START]: (_state, _action) => new Map(),
  [actionType.FETCH_COMMENT_REFERENCES_SUCCESS]: (_state, action) => {
    return action.commentReferences;
  },
});

const relatedIssuesReducer = createReducer(new Map(), {
  [actionType.FETCH_RELATED_ISSUES_SUCCESS]: (_state, action) => {
    return action.relatedIssues;
  },
});

const isStarredReducer = createReducer(false, {
  [actionType.STAR_ISSUE_SUCCESS]: (state, _action) => !state,
  [actionType.FETCH_IS_STARRED_SUCCESS]: (_state, action) => !!action.isStarred,
});

const presubmitResponseReducer = createReducer({}, {
  [actionType.PRESUBMIT_ISSUE_SUCCESS]: (state, action) => {
    return action.presubmitResponse;
  },
});

const issuePermissionsReducer = createReducer([], {
  [actionType.FETCH_ISSUE_PERMISSIONS_SUCCESS]: (_state, action) => {
    return action.permissions;
  },
});

const dirtyFormsReducer = createReducer([], {
  [actionType.REPORT_DIRTY_FORM]: (state, action) => {
    const newState = [...state];
    const index = state.indexOf(action.name);
    if (action.isDirty && index === -1) {
      newState.push(action.name);
    } else if (!action.isDirty && index !== -1) {
      newState.splice(index, 1);
    }
    return newState;
  },
  [actionType.CLEAR_DIRTY_FORMS]: () => [],
});

const focusIdReducer = createReducer(null, {
  [actionType.SET_FOCUS_ID]: (_state, action) => action.focusId,
});

const requestsReducer = combineReducers({
  // Request for getting an issue.
  fetchIssue: createRequestReducer(
    actionType.FETCH_ISSUE_START,
    actionType.FETCH_ISSUE_SUCCESS,
    actionType.FETCH_ISSUE_FAILURE),
  // Request for getting an issue's hotlists.
  fetchIssueHotlists: createRequestReducer(
    actionType.FETCH_ISSUE_HOTLISTS_START,
    actionType.FETCH_ISSUE_HOTLISTS_SUCCESS,
    actionType.FETCH_ISSUE_HOTLISTS_FAILURE),
  // Request for getting issue permissions.
  fetchIssuePermissions: createRequestReducer(
    actionType.FETCH_ISSUE_PERMISSIONS_START,
    actionType.FETCH_ISSUE_PERMISSIONS_SUCCESS,
    actionType.FETCH_ISSUE_PERMISSIONS_FAILURE),
  // Request for starring an issue.
  starIssue: createRequestReducer(
    actionType.STAR_ISSUE_START,
    actionType.STAR_ISSUE_SUCCESS,
    actionType.STAR_ISSUE_FAILURE),
  // Request for checking an issue before submitting.
  presubmitIssue: createRequestReducer(
    actionType.PRESUBMIT_ISSUE_START,
    actionType.PRESUBMIT_ISSUE_SUCCESS,
    actionType.PRESUBMIT_ISSUE_FAILURE),
  // Request for getting comments for an issue.
  fetchComments: createRequestReducer(
    actionType.FETCH_COMMENTS_START,
    actionType.FETCH_COMMENTS_SUCCESS,
    actionType.FETCH_COMMENTS_FAILURE),
  // Request for getting references in comment data for an issue.
  fetchCommentReferences: createRequestReducer(
    actionType.FETCH_COMMENT_REFERENCES_START,
    actionType.FETCH_COMMENT_REFERENCES_SUCCESS,
    actionType.FETCH_COMMENT_REFERENCES_FAILURE),
  fetchRelatedIssues: createRequestReducer(
    actionType.FETCH_RELATED_ISSUES_START,
    actionType.FETCH_RELATED_ISSUES_SUCCESS,
    actionType.FETCH_RELATED_ISSUES_FAILURE),
  // Request for getting whether an issue is starred.
  fetchIsStarred: createRequestReducer(
    actionType.FETCH_IS_STARRED_START,
    actionType.FETCH_IS_STARRED_SUCCESS,
    actionType.FETCH_IS_STARRED_FAILURE),
  // Request for converting an issue.
  convertIssue: createRequestReducer(
    actionType.CONVERT_ISSUE_START,
    actionType.CONVERT_ISSUE_SUCCESS,
    actionType.CONVERT_ISSUE_FAILURE),
  // Request for updating an issue.
  updateIssue: createRequestReducer(
    actionType.UPDATE_ISSUE_START,
    actionType.UPDATE_ISSUE_SUCCESS,
    actionType.UPDATE_ISSUE_FAILURE),
  // Request for updating an approval.
  // Assumption: It's okay to prevent the user from sending multiple
  // approval update requests at once, even for different approvals.
  updateApproval: createRequestReducer(
    actionType.UPDATE_APPROVAL_START,
    actionType.UPDATE_APPROVAL_SUCCESS,
    actionType.UPDATE_APPROVAL_FAILURE),
});

const reducer = combineReducers({
  project: project.reducer,
  user: user.reducer,

  issueRef: combineReducers({
    localId: localIdReducer,
    projectName: projectNameReducer,
  }),

  issue: combineReducers({
    currentIssue: currentIssueReducer,
    issueHotlists: issueHotlistsReducer,
    comments: commentsReducer,
    commentReferences: commentReferencesReducer,
    relatedIssues: relatedIssuesReducer,
    isStarred: isStarredReducer,
    issuePermissions: issuePermissionsReducer,
    presubmitResponse: presubmitResponseReducer,
  }),

  // Forms to be checked for user changes before leaving the page.
  dirtyForms: dirtyFormsReducer,

  // The ID of the element to be focused, as given by the hash part of the URL.
  focusId: focusIdReducer,

  requests: requestsReducer,
});

function rootReducer(state, action) {
  if (action.type == actionType.RESET_STATE) {
    state = undefined;
  }
  return reducer(state, action);
}

// For debugging with the Redux Devtools extension:
// https://chrome.google.com/webstore/detail/redux-devtools/lmhkpmbekcpmknklioeibfkpmmfibljd/
const composeEnhancers = window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__ || compose;
export const store = createStore(rootReducer, composeEnhancers(
  applyMiddleware(thunk)
));

export const ReduxMixin = createMixin(store);
