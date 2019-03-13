// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {createMixin} from 'polymer-redux';
import {combineReducers, createStore} from 'redux';
import {autolink} from '../../autolink.js';

export const actionType = {
  // Misc global state.
  RESET_STATE: 'RESET_STATE',
  UPDATE_ISSUE_REF: 'UPDATE_ISSUE_REF',
  UPDATE_FORMS_TO_CHECK: 'UPDATE_FORMS_TO_CHECK',
  CLEAR_FORMS_TO_CHECK: 'CLEAR_FORMS_TO_CHECK',
  SET_FOCUS_ID: 'SET_FOCUS_ID',

  // AJAX request state.
  FETCH_PROJECT_CONFIG_START: 'FETCH_PROJECT_CONFIG_START',
  FETCH_PROJECT_CONFIG_SUCCESS: 'FETCH_PROJECT_CONFIG_SUCCESS',
  FETCH_PROJECT_CONFIG_FAILURE: 'FETCH_PROJECT_CONFIG_FAILURE',

  FETCH_PROJECT_TEMPLATES_START: 'FETCH_PROJECT_TEMPLATES_START',
  FETCH_PROJECT_TEMPLATES_SUCCESS: 'FETCH_PROJECT_TEMPLATES_SUCCESS',
  FETCH_PROJECT_TEMPLATES_FAILURE: 'FETCH_PROJECT_TEMPLATES_FAILURE',

  FETCH_USER_START: 'FETCH_USER_START',
  FETCH_USER_SUCCESS: 'FETCH_USER_SUCCESS',
  FETCH_USER_FAILURE: 'FETCH_USER_FAILURE',

  FETCH_USER_HOTLISTS_START: 'FETCH_USER_HOTLISTS_START',
  FETCH_USER_HOTLISTS_SUCCESS: 'FETCH_USER_HOTLISTS_SUCCESS',
  FETCH_USER_HOTLISTS_FAILURE: 'FETCH_USER_HOTLISTS_FAILURE',

  FETCH_USER_PREFS_START: 'FETCH_USER_PREFS_START',
  FETCH_USER_PREFS_SUCCESS: 'FETCH_USER_PREFS_SUCCESS',
  FETCH_USER_PREFS_FAILURE: 'FETCH_USER_PREFS_FAILURE',

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

  FETCH_IS_STARRED_START: 'FETCH_IS_STARRED_START',
  FETCH_IS_STARRED_SUCCESS: 'FETCH_IS_STARRED_SUCCESS',
  FETCH_IS_STARRED_FAILURE: 'FETCH_IS_STARRED_FAILURE',

  FETCH_COMMENTS_START: 'FETCH_COMMENTS_START',
  FETCH_COMMENTS_SUCCESS: 'FETCH_COMMENTS_SUCCESS',
  FETCH_COMMENTS_FAILURE: 'FETCH_COMMENTS_FAILURE',

  FETCH_COMMENT_REFERENCES_START: 'FETCH_COMMENT_REFERENCES_START',
  FETCH_COMMENT_REFERENCES_SUCCESS: 'FETCH_COMMENT_REFERENCES_SUCCESS',
  FETCH_COMMENT_REFERENCES_FAILURE: 'FETCH_COMMENT_REFERENCES_FAILURE',

  FETCH_BLOCKER_REFERENCES_START: 'FETCH_BLOCKER_REFERENCES_START',
  FETCH_BLOCKER_REFERENCES_SUCCESS: 'FETCH_BLOCKER_REFERENCES_SUCCESS',
  FETCH_BLOCKER_REFERENCES_FAILURE: 'FETCH_BLOCKER_REFERENCES_FAILURE',

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

export const actionCreator = {
  fetchCommentReferences: (dispatch, comments, projectName) => {
    dispatch({type: actionType.FETCH_COMMENT_REFERENCES_START});

    autolink.getReferencedArtifacts(comments, projectName).then(
      (refs) => {
        const commentRefs = new Map();
        refs.forEach(({componentName, existingRefs}) => {
          commentRefs.set(componentName, existingRefs);
        });
        dispatch({
          type: actionType.FETCH_COMMENT_REFERENCES_SUCCESS,
          commentReferences: commentRefs,
        });
    }, (error) => {
      dispatch({
        type: actionType.FETCH_COMMENT_REFERENCES_FAILURE,
        error,
      });
    });
  },
  // TODO(zhangtiff): Figure out if we can reduce request/response sizes by
  // diffing issues to fetch against issues we already know about to avoid
  // fetching duplicate info.
  fetchBlockerReferences: (dispatch, issue) => {
    if (!issue) return;
    dispatch({type: actionType.FETCH_BLOCKER_REFERENCES_START});

    const refsToFetch = (issue.blockedOnIssueRefs || []).concat(
        issue.blockingIssueRefs || []);
    if (issue.mergedIntoIssueRef) {
      refsToFetch.push(issue.mergedIntoIssueRef);
    }

    const message = {
      issueRefs: refsToFetch,
    };
    const listReferencedIssues =  window.prpcClient.call(
        'monorail.Issues', 'ListReferencedIssues', message);

    listReferencedIssues.then((resp) => {
      let blockerReferences = new Map();

      const openIssues = resp.openRefs || [];
      const closedIssues = resp.closedRefs || [];
      openIssues.forEach((issue) => {
        blockerReferences.set(
          `${issue.projectName}:${issue.localId}`, {
            issue: issue,
            isClosed: false,
          });
      });
      closedIssues.forEach((issue) => {
        blockerReferences.set(
          `${issue.projectName}:${issue.localId}`, {
            issue: issue,
            isClosed: true,
          });
      });
      dispatch({
        type: actionType.FETCH_BLOCKER_REFERENCES_SUCCESS,
        blockerReferences: blockerReferences,
      });
    }, (error) => {
      dispatch({
        type: actionType.FETCH_BLOCKER_REFERENCES_FAILURE,
        error,
      });
    });
  },
  fetchIssue: (dispatch, message) => {
    dispatch({type: actionType.FETCH_ISSUE_START});

    const getIssue = window.prpcClient.call(
      'monorail.Issues', 'GetIssue', message
    );

    getIssue.then((resp) => {
      dispatch({
        type: actionType.FETCH_ISSUE_SUCCESS,
        issue: resp.issue,
      });

      actionCreator.fetchIssuePermissions(dispatch, message);
      if (!resp.issue.isDeleted) {
        actionCreator.fetchBlockerReferences(dispatch, resp.issue);
        actionCreator.fetchIssueHotlists(dispatch, message.issueRef);
      }
    }, (error) => {
      dispatch({
        type: actionType.FETCH_ISSUE_FAILURE,
        error,
      });
    });
  },
  fetchIssueHotlists: (dispatch, issue) => {
    dispatch({type: actionType.FETCH_ISSUE_HOTLISTS_START});

    const getIssueHotlists = window.prpcClient.call(
      'monorail.Features', 'ListHotlistsByIssue', {issue});

    getIssueHotlists.then((resp) => {
      const hotlists = (resp.hotlists || []);
      hotlists.sort((hotlistA, hotlistB) => {
        return hotlistA.name.localeCompare(hotlistB.name);
      });
      dispatch({
        type: actionType.FETCH_ISSUE_HOTLISTS_SUCCESS,
        hotlists,
      });
    }, (error) => {
      dispatch({
        type: actionType.FETCH_ISSUE_HOTLISTS_FAILURE,
        error,
      });
    });
  },
  fetchUser: (dispatch, displayName) => {
    dispatch({type: actionType.FETCH_USER_START});

    const message = {
      userRef: {displayName},
    };

    const allPromises = [
      window.prpcClient.call(
        'monorail.Users', 'GetUser', message),
      window.prpcClient.call(
        'monorail.Users', 'GetMemberships', message),
    ];

    Promise.all(allPromises).then((resp) => {
      dispatch({
        type: actionType.FETCH_USER_SUCCESS,
        user: resp[0],
        groups: resp[1].groupRefs,
      });
      actionCreator.fetchUserHotlists(dispatch, displayName);
      actionCreator.fetchUserPrefs(dispatch);
    }, (error) => {
      dispatch({
        type: actionType.FETCH_USER_FAILURE,
        error,
      });
    });
  },
  fetchUserHotlists: (dispatch, displayName) => {
    dispatch({type: actionType.FETCH_USER_HOTLISTS_START});

    const getUserHotlists = window.prpcClient.call(
      'monorail.Features', 'ListHotlistsByUser', {user: {displayName}});

    getUserHotlists.then((resp) => {
      const hotlists = (resp.hotlists || []);
      hotlists.sort((hotlistA, hotlistB) => {
        return hotlistA.name.localeCompare(hotlistB.name);
      });
      dispatch({
        type: actionType.FETCH_USER_HOTLISTS_SUCCESS,
        hotlists,
      });
    }, (error) => {
      dispatch({
        type: actionType.FETCH_USER_HOTLISTS_FAILURE,
        error,
      });
    });
  },
  fetchUserPrefs: (dispatch) => {
    dispatch({type: actionType.FETCH_USER_PREFS_START});

    const getUserPrefs = window.prpcClient.call(
      'monorail.Users', 'GetUserPrefs', {});

    getUserPrefs.then((resp) => {
      const prefs = new Map((resp.prefs || []).map((pref) => {
        return [pref.name, pref.value];
      }));
      dispatch({
        type: actionType.FETCH_USER_PREFS_SUCCESS,
        prefs,
      });
    }, (error) => {
      dispatch({
        type: actionType.FETCH_USER_PREFS_FAILURE,
        error,
      });
    });
  },
  fetchIssuePermissions: (dispatch, message) => {
    dispatch({type: actionType.FETCH_ISSUE_PERMISSIONS_START});

    const getIssuePermissions = window.prpcClient.call(
      'monorail.Issues', 'ListIssuePermissions', message
    );

    getIssuePermissions.then((resp) => {
      dispatch({
        type: actionType.FETCH_ISSUE_PERMISSIONS_SUCCESS,
        permissions: resp.permissions,
      });
    }, (error) => {
      dispatch({
        type: actionType.FETCH_ISSUE_PERMISSIONS_FAILURE,
        error,
      });
    });
  },
  fetchComments: (dispatch, message) => {
    dispatch({type: actionType.FETCH_COMMENTS_START});

    const getComments = window.prpcClient.call(
      'monorail.Issues', 'ListComments', message
    );

    getComments.then((resp) => {
      dispatch({
        type: actionType.FETCH_COMMENTS_SUCCESS,
        comments: resp.comments,
      });
      actionCreator.fetchCommentReferences(
          dispatch, resp.comments, message.issueRef.projectName);
    }, (error) => {
      dispatch({
        type: actionType.FETCH_COMMENTS_FAILURE,
        error,
      });
    });
  },
  fetchIsStarred: (dispatch, message) => {
    dispatch({type: actionType.FETCH_IS_STARRED_START});

    const getIsStarred = window.prpcClient.call(
      'monorail.Issues', 'IsIssueStarred', message
    );

    getIsStarred.then((resp) => {
      dispatch({
        type: actionType.FETCH_IS_STARRED_SUCCESS,
        isStarred: resp.isStarred,
      });
    }, (error) => {
      dispatch({
        type: actionType.FETCH_IS_STARRED_FAILURE,
        error,
      });
    });
  },
  updateApproval: (dispatch, message) => {
    dispatch({type: actionType.UPDATE_APPROVAL_START});

    window.prpcClient.call(
      'monorail.Issues', 'UpdateApproval', message
    ).then((resp) => {
      dispatch({
        type: actionType.UPDATE_APPROVAL_SUCCESS,
        approval: resp.approval,
      });
      const baseMessage = {
        issueRef: message.issueRef,
      };
      actionCreator.fetchIssue(dispatch, baseMessage);
      actionCreator.fetchComments(dispatch, baseMessage);
    }, (error) => {
      dispatch({
        type: actionType.UPDATE_APPROVAL_FAILURE,
        error: error,
      });
    });
  },
  updateIssue: (dispatch, message) => {
    dispatch({type: actionType.UPDATE_ISSUE_START});

    window.prpcClient.call(
      'monorail.Issues', 'UpdateIssue', message
    ).then((resp) => {
      dispatch({
        type: actionType.UPDATE_ISSUE_SUCCESS,
        issue: resp.issue,
      });
      const fetchCommentsMessage = {
        issueRef: message.issueRef,
      };
      actionCreator.fetchComments(dispatch, fetchCommentsMessage);
      actionCreator.fetchBlockerReferences(dispatch, resp.issue);
    }, (error) => {
      dispatch({
        type: actionType.UPDATE_ISSUE_FAILURE,
        error: error,
      });
    });
  },
  convertIssue: (dispatch, message) => {
    dispatch({type: actionType.CONVERT_ISSUE_START});

    window.prpcClient.call(
        'monorail.Issues', 'ConvertIssueApprovalsTemplate', message
    ).then((resp) => {
      dispatch({
        type: actionType.CONVERT_ISSUE_SUCCESS,
        issue: resp.issue,
      });
      const fetchCommentsMessage = {
        issueRef: message.issueRef,
      };
      actionCreator.fetchComments(dispatch, fetchCommentsMessage);
    }, (error) => {
      dispatch({
        type: actionType.CONVERT_ISSUE_FAILURE,
        error: error,
      });
    });
  },
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
}

function createReducer(initialState, handlers) {
  return function reducer(state = initialState, action) {
    if (handlers.hasOwnProperty(action.type)) {
      return handlers[action.type](state, action);
    } else {
      return state;
    }
  }
}

function createRequestReducer(start, success, failure) {
  return createReducer({requesting: false, error: null}, {
    [start]: (_state, _action) => ({
      requesting: true,
      error: null,
    }),
    [success]: (_state, _action) =>({
      requesting: false,
      error: null,
    }),
    [failure]: (_state, action) => ({
      requesting: false,
      error: action.error,
    }),
  });
}

const userReducer = createReducer(null, {
  [actionType.FETCH_USER_SUCCESS]: (_state, action) => action.user,
});

const userGroupsReducer = createReducer([], {
  [actionType.FETCH_USER_SUCCESS]: (_state, action) => action.groups || [],
});

const issueIdReducer = createReducer(0, {
  [actionType.UPDATE_ISSUE_REF]: (state, action) => action.issueId || state,
});

const projectNameReducer = createReducer('', {
  [actionType.UPDATE_ISSUE_REF]: (state, action) => action.projectName || state,
});

const projectConfigReducer = createReducer({}, {
  [actionType.FETCH_PROJECT_CONFIG_SUCCESS]: (_state, action) => {
    return action.projectConfig;
  },
});

const projectTemplatesReducer = createReducer([], {
  [actionType.FETCH_PROJECT_TEMPLATES_SUCCESS]: (_state, action) => {
    return action.projectTemplates.templates;
  },
});

const issueReducer = createReducer({}, {
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

const issueLoadedReducer = createReducer(false, {
  [actionType.FETCH_ISSUE_SUCCESS]: (_state, _action) => true,
});

const issueHotlistsReducer = createReducer([], {
  [actionType.FETCH_ISSUE_HOTLISTS_SUCCESS]: (_, action) => action.hotlists,
});

const userHotlistsReducer = createReducer([], {
  [actionType.FETCH_USER_HOTLISTS_SUCCESS]: (_, action) => action.hotlists,
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

const blockerReferencesReducer = createReducer(new Map(), {
  [actionType.FETCH_BLOCKER_REFERENCES_SUCCESS]: (_state, action) => {
    return action.blockerReferences;
  },
});

const isStarredReducer = createReducer(false, {
  [actionType.STAR_ISSUE_SUCCESS]: (state, _action) => !state,
  [actionType.FETCH_IS_STARRED_SUCCESS]: (_state, action) => !!action.isStarred,
});

const issuePermissionsReducer = createReducer([], {
  [actionType.FETCH_ISSUE_PERMISSIONS_SUCCESS]: (_state, action) => {
    return action.permissions;
  },
});

const formsToCheckReducer = createReducer([], {
  [actionType.UPDATE_FORMS_TO_CHECK]: (state, action) => {
    return [...state, action.form];
  },
  [actionType.CLEAR_FORMS_TO_CHECK]: () => [],
});

const focusIdReducer = createReducer(null, {
  [actionType.SET_FOCUS_ID]: (_state, action) => action.focusId,
});

const prefsReducer = createReducer(null, {
  [actionType.FETCH_USER_PREFS_SUCCESS]: (_state, action) => action.prefs,
});

const requestsReducer = combineReducers({
  // Request for getting configuration settings for a project.
  fetchProjectConfig: createRequestReducer(
    actionType.FETCH_PROJECT_CONFIG_START,
    actionType.FETCH_PROJECT_CONFIG_SUCCESS,
    actionType.FETCH_PROJECT_CONFIG_FAILURE),
  // Request for getting templates for a project.
  fetchProjectTemplates: createRequestReducer(
    actionType.FETCH_PROJECT_TEMPLATES_START,
    actionType.FETCH_PROJECT_TEMPLATES_SUCCESS,
    actionType.FETCH_PROJECT_TEMPLATES_FAILURE),
  // Request for getting backend metadata related to a user, such as
  // which groups they belong to and whether they're a site admin.
  fetchUser: createRequestReducer(
    actionType.FETCH_USER_START,
    actionType.FETCH_USER_SUCCESS,
    actionType.FETCH_USER_FAILURE),
  // Request for getting a user's hotlists.
  fetchUserHotlists: createRequestReducer(
    actionType.FETCH_USER_HOTLISTS_START,
    actionType.FETCH_USER_HOTLISTS_SUCCESS,
    actionType.FETCH_USER_HOTLISTS_FAILURE),
  // Request for getting a user's prefs.
  fetchUserPrefs: createRequestReducer(
    actionType.FETCH_USER_PREFS_START,
    actionType.FETCH_USER_PREFS_SUCCESS,
    actionType.FETCH_USER_PREFS_FAILURE),
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
  fetchBlockerReferences: createRequestReducer(
    actionType.FETCH_BLOCKER_REFERENCES_START,
    actionType.FETCH_BLOCKER_REFERENCES_SUCCESS,
    actionType.FETCH_BLOCKER_REFERENCES_FAILURE),
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
  user: userReducer,
  userGroups: userGroupsReducer,

  // TODO(zhangtiff): Combine these into viewedIssueRef for consistency.
  issueId: issueIdReducer,
  projectName: projectNameReducer,

  projectConfig: projectConfigReducer,
  projectTemplates: projectTemplatesReducer,
  issue: issueReducer,
  issueLoaded: issueLoadedReducer,
  issueHotlists: issueHotlistsReducer,
  userHotlists: userHotlistsReducer,
  comments: commentsReducer,
  commentReferences: commentReferencesReducer,
  blockerReferences: blockerReferencesReducer,
  isStarred: isStarredReducer,
  issuePermissions: issuePermissionsReducer,

  // Fields to be checked for user changes before leaving the page.
  // TODO(ehmaldonado): Figure out a way to keep redux state serializable.
  formsToCheck: formsToCheckReducer,

  // The ID of the element to be focused, as given by the hash part of the URL.
  focusId: focusIdReducer,
  prefs: prefsReducer,

  requests: requestsReducer,
});

function rootReducer(state, action) {
  if (action.type == actionType.RESET_STATE) {
    state = undefined;
  }
  return reducer(state, action);
}

export const store = createStore(rootReducer, undefined,
  // For debugging with the Redux Devtools extension:
  // https://chrome.google.com/webstore/detail/redux-devtools/lmhkpmbekcpmknklioeibfkpmmfibljd/
  window.__REDUX_DEVTOOLS_EXTENSION__
    && window.__REDUX_DEVTOOLS_EXTENSION__()
);

export const ReduxMixin = createMixin(store);
