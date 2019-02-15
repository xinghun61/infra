// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {createMixin} from 'polymer-redux';
import {createStore} from 'redux';
import {autolink} from '../../autolink.js';

export const actionType = {
  // Misc global state.
  RESET_STATE: 'RESET_STATE',
  UPDATE_ISSUE_REF: 'UPDATE_ISSUE_REF',
  UPDATE_FORMS_TO_CHECK: 'UPDATE_FORMS_TO_CHECK',
  CLEAR_FORMS_TO_CHECK: 'CLEAR_FORMS_TO_CHECK',

  // AJAX request state.
  FETCH_PROJECT_CONFIG_START: 'FETCH_PROJECT_CONFIG_START',
  FETCH_PROJECT_CONFIG_SUCCESS: 'FETCH_PROJECT_CONFIG_SUCCESS',
  FETCH_PROJECT_CONFIG_FAILURE: 'FETCH_PROJECT_CONFIG_FAILURE',

  FETCH_USER_START: 'FETCH_USER_START',
  FETCH_USER_SUCCESS: 'FETCH_USER_SUCCESS',
  FETCH_USER_FAILURE: 'FETCH_USER_FAILURE',

  FETCH_USER_HOTLISTS_START: 'FETCH_USER_HOTLISTS_START',
  FETCH_USER_HOTLISTS_SUCCESS: 'FETCH_USER_HOTLISTS_SUCCESS',
  FETCH_USER_HOTLISTS_FAILURE: 'FETCH_USER_HOTLISTS_FAILURE',

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
  fetchUserHotlists: (dispatch, user) => {
    dispatch({type: actionType.FETCH_USER_HOTLISTS_START});

    const getUserHotlists = window.prpcClient.call(
      'monorail.Features', 'ListHotlistsByUser',
      {user: {displayName: user}});

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
};

export const initial = {
  user: null,
  userGroups: [],

  // TODO(zhangtiff): Combine these into viewedIssueRef for consistency.
  issueId: 0,
  projectName: '',

  projectConfig: {},
  issue: {},
  issueHotlists: [],
  userHotlists: [],
  comments: [],
  commentReferences: new Map(),
  blockerReferences: new Map(),
  isStarred: false,
  issuePermissions: [],

  // Fields to be checked for user changes before leaving the page.
  // TODO(ehmaldonado): Figure out a way to keep redux state serializable.
  formsToCheck: [],

  fetchingUser: false,
  fetchUserError: null,

  fetchingUserHotlists: false,
  fetchUserHotlistsError: null,

  issueLoaded: false,
  fetchingIssue: false,
  fetchIssueError: null,

  fetchingIssueHotlists: false,
  fetchIssueHotlistsError: null,

  fetchingIssuePermissions: false,
  fetchIssuePermissionsError: null,

  fetchingProjectConfig: false,
  fetchProjectConfigError: null,

  fetchingComments: false,
  fetchCommentsError: null,

  fetchingCommentReferences: false,
  fetchingCommentReferencesError: null,

  fetchingBlockerReferences: false,
  fetchingBlockerReferencesError: null,

  starringIssue: false,
  starIssueError: null,

  fetchingIsStarred: false,
  fetchIsStarredError: null,

  updatingIssue: false,
  updateIssueError: null,

  // Assumption: It's okay to prevent the user from sending multiple
  // approval update requests at once, even for different approvals.
  updatingApproval: false,
  updateApprovalError: null,
};

// Helpers for the reducers.
export const updateIssueApproval = (issue, approval) => {
  if (!issue.approvalValues) return issue;
  const newApprovals = issue.approvalValues.map((item, i) => {
    if (item.fieldRef.fieldName === approval.fieldRef.fieldName) {
      // PhaseRef isn't populated on the response so we want to make sure
      // it doesn't overwrite the original phaseRef with {}.
      const a = Object.assign({}, approval, {phaseRef: item.phaseRef});
      return a;
    }
    return item;
  });
  return Object.assign({}, issue, {approvalValues: newApprovals});
}

export const reducer = (state, action) => {
  switch (action.type) {
    case actionType.RESET_STATE:
      return Object.assign({}, initial);

    case actionType.UPDATE_ISSUE_REF:
      return Object.assign({}, state, {
        issueId: action.issueId || state.issueId,
        projectName: action.projectName || state.projectName,
      });

    case actionType.UPDATE_FORMS_TO_CHECK:
      return Object.assign({}, state, {
        formsToCheck: state.formsToCheck.concat([action.form])
      });

    case actionType.CLEAR_FORMS_TO_CHECK:
      return Object.assign({}, state, {formsToCheck: []});

    // Request for getting configuration settings for a project.
    case actionType.FETCH_PROJECT_CONFIG_START:
      return Object.assign({}, state, {
        fetchProjectConfigError: null,
        fetchingProjectConfig: true,
      });
    case actionType.FETCH_PROJECT_CONFIG_SUCCESS:
      return Object.assign({}, state, {
        projectConfig: action.projectConfig,
        fetchingProjectConfig: false,
      });
    case actionType.FETCH_PROJECT_CONFIG_FAILURE:
      return Object.assign({}, state, {
        fetchProjectConfigError: action.error,
        fetchingProjectConfig: false,
      });

    // Request for getting backend metadata related to a user, such as
    // which groups they belong to and whether they're a site admin.
    case actionType.FETCH_USER_START:
      return Object.assign({}, state, {
        fetchUserError: null,
        fetchingUser: true,
      });
    case actionType.FETCH_USER_SUCCESS:
      return Object.assign({}, state, {
        userGroups: action.groups,
        user: action.user,
        fetchingUser: false,
      });
    case actionType.FETCH_USER_FAILURE:
      return Object.assign({}, state, {
        fetchUserError: action.error,
        fetchingUser: false,
      });

    // Request for getting a user's hotlists.
    case actionType.FETCH_USER_HOTLISTS_START:
      return Object.assign({}, state, {
        fetchUserHotlistsError: null,
        fetchingUserHotlists: true,
      });
    case actionType.FETCH_USER_HOTLISTS_SUCCESS:
      return Object.assign({}, state, {
        userHotlists: action.hotlists,
        fetchingUserHotlists: false,
      });
    case actionType.FETCH_USER_HOTLISTS_FAILURE:
      return Object.assign({}, state, {
        fetchUserHotlistsError: action.error,
        fetchingUserHotlists: false,
      });

    // Request for getting an issue.
    case actionType.FETCH_ISSUE_START:
      return Object.assign({}, state, {
        fetchIssueError: null,
        fetchingIssue: true,
      });
    case actionType.FETCH_ISSUE_SUCCESS:
      return Object.assign({}, state, {
        issue: action.issue,
        issueLoaded: true,
        fetchingIssue: false,
      });
    case actionType.FETCH_ISSUE_FAILURE:
      return Object.assign({}, state, {
        fetchIssueError: action.error,
        fetchingIssue: false,
      });

    // Request for getting an issue's hotlists.
    case actionType.FETCH_ISSUE_HOTLISTS_START:
      return Object.assign({}, state, {
        fetchIssueHotlistsError: null,
        fetchingIssueHotlists: true,
      });
    case actionType.FETCH_ISSUE_HOTLISTS_SUCCESS:
      return Object.assign({}, state, {
        issueHotlists: action.hotlists,
        fetchingIssueHotlists: false,
      });
    case actionType.FETCH_ISSUE_HOTLISTS_FAILURE:
      return Object.assign({}, state, {
        fetchIssueHotlistsError: action.error,
        fetchingIssueHotlists: false,
      });

    // Request for getting issue permissions.
    case actionType.FETCH_ISSUE_PERMISSIONS_START:
      return Object.assign({}, state, {
        fetchIssuePermissionsError: null,
        fetchingIssuePermissions: true,
      });
    case actionType.FETCH_ISSUE_PERMISSIONS_SUCCESS:
      return Object.assign({}, state, {
        issuePermissions: action.permissions,
        fetchingIssuePermissions: false,
      });
    case actionType.FETCH_ISSUE_PERMISSIONS_FAILURE:
      return Object.assign({}, state, {
        fetchIssuePermissionsError: action.error,
        fetchingIssuePermissions: false,
      });

    // Request for starring an issue.
    case actionType.STAR_ISSUE_START:
      return Object.assign({}, state, {
        starIssueError: null,
        starringIssue: true,
      });
    case actionType.STAR_ISSUE_SUCCESS:
      return Object.assign({}, state, {
        issue: Object.assign({}, state.issue, {starCount: action.starCount}),
        isStarred: action.isStarred,
        starringIssue: false,
      });
    case actionType.STAR_ISSUE_FAILURE:
      return Object.assign({}, state, {
        starIssueError: action.error,
        starringIssue: false,
      });

    // Request for getting comments for an issue.
    case actionType.FETCH_COMMENTS_START:
      return Object.assign({}, state, {
        commentReferences: new Map(),
        fetchCommentsError: null,
        fetchingComments: true,
      });
    case actionType.FETCH_COMMENTS_SUCCESS:
      return Object.assign({}, state, {
        comments: action.comments,
        fetchingComments: false,
      });
    case actionType.FETCH_COMMENTS_FAILURE:
      return Object.assign({}, state, {
        fetchCommentsError: action.error,
        fetchingComments: false,
      });

     // Request for getting references in comment data for an issue.
    case actionType.FETCH_COMMENT_REFERENCES_START:
      return Object.assign({}, state, {
        fetchCommentReferencesError: null,
        fetchingCommentReferences: true,
      });
    case actionType.FETCH_COMMENT_REFERENCES_SUCCESS:
      return Object.assign({}, state, {
        commentReferences: action.commentReferences,
        fetchingCommentReferences: false,
      });
    case actionType.FETCH_COMMENT_REFERENCES_FAILURE:
      return Object.assign({}, state, {
        fetchCommentReferencesError: action.error,
        fetchingCommentReferences: false,
      });

    case actionType.FETCH_BLOCKER_REFERENCES_START:
      return Object.assign({}, state, {
        fetchBlockerReferencesError: null,
        fetchingBlockerReferences: true,
      });
    case actionType.FETCH_BLOCKER_REFERENCES_SUCCESS:
      return Object.assign({}, state, {
        blockerReferences: action.blockerReferences,
        fetchingBlockerReferences: false,
      });
    case actionType.FETCH_BLOCKER_REFERENCES_FAILURE:
      return Object.assign({}, state, {
        fetchBlockerReferencesError: action.error,
        fetchingBlockerReferences: false,
      });

    // Request for getting whether an issue is starred.
    case actionType.FETCH_IS_STARRED_START:
      return Object.assign({}, state, {
        fetchIsStarredError: null,
        fetchingIsStarred: true,
      });
    case actionType.FETCH_IS_STARRED_SUCCESS:
      return Object.assign({}, state, {
        isStarred: action.isStarred,
        fetchingIsStarred: false,
      });
    case actionType.FETCH_IS_STARRED_FAILURE:
      return Object.assign({}, state, {
        fetchIsStarredError: action.error,
        fetchingIsStarred: false,
      });

    // Request for updating an issue.
    case actionType.UPDATE_ISSUE_START:
      return Object.assign({}, state, {
        updatingIssue: true,
        updateIssueError: null,
      });
    case actionType.UPDATE_ISSUE_SUCCESS:
      return Object.assign({}, state, {
        issue: action.issue,
        updatingIssue: false,
      });
    case actionType.UPDATE_ISSUE_FAILURE:
      return Object.assign({}, state, {
        updateIssueError: action.error,
        updatingIssue: false,
      });

    // Request for updating an approval.
    case actionType.UPDATE_APPROVAL_START:
      return Object.assign({}, state, {
        updateApprovalError: null,
        updatingApproval: true,
      });
    case actionType.UPDATE_APPROVAL_SUCCESS:
      return Object.assign({}, state, {
        issue: updateIssueApproval(state.issue, action.approval),
        updatingApproval: false,
      });
    case actionType.UPDATE_APPROVAL_FAILURE:
      return Object.assign({}, state, {
        updateApprovalError: action.error,
        updatingApproval: false,
      });

    default:
      return state;
  }
};
export const store = createStore(reducer, initial,
  // For debugging with the Redux Devtools extension:
  // https://chrome.google.com/webstore/detail/redux-devtools/lmhkpmbekcpmknklioeibfkpmmfibljd/
  window.__REDUX_DEVTOOLS_EXTENSION__
    && window.__REDUX_DEVTOOLS_EXTENSION__()
);

export const ReduxMixin = createMixin(store);
