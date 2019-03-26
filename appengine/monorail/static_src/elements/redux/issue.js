// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {createSelector} from 'reselect';
import {autolink} from '../../autolink.js';
import {fieldTypes} from '../shared/field-types.js';
import {removePrefix} from '../shared/helpers.js';
import {issueRefToString} from '../shared/converters.js';
import {actionType} from './redux-mixin.js';
import * as project from './project.js';

// Actions

/* State Shape
*/

// Reducers

// Selectors
const RESTRICT_VIEW_PREFIX = 'restrict-view-';
const RESTRICT_EDIT_PREFIX = 'restrict-editissue-';
const RESTRICT_COMMENT_PREFIX = 'restrict-addissuecomment-';

// TODO(zhangtiff): Eventually Monorail's Redux state will store
// multiple issues, and this selector will have to find the viewed
// issue based on a viewed issue ref.
export const issue = (state) => state.issue;

export const fieldValues = createSelector(
  issue,
  (issue) => issue && issue.fieldValues
);

export const type = createSelector(
  fieldValues,
  (fieldValues) => {
    if (!fieldValues) return;
    const typeFieldValue = fieldValues.find(
      (f) => (f.fieldRef && f.fieldRef.fieldName === 'Type')
    );
    if (typeFieldValue) {
      return typeFieldValue.value;
    }
    return;
  }
);

export const restrictions = createSelector(
  issue,
  (issue) => {
    if (!issue || !issue.labelRefs) return {};

    const restrictions = {};

    issue.labelRefs.forEach((labelRef) => {
      const label = labelRef.label;
      const lowerCaseLabel = label.toLowerCase();

      if (lowerCaseLabel.startsWith(RESTRICT_VIEW_PREFIX)) {
        const permissionType = removePrefix(label, RESTRICT_VIEW_PREFIX);
        if (!('view' in restrictions)) {
          restrictions['view'] = [permissionType];
        } else {
          restrictions['view'].push(permissionType);
        }
      } else if (lowerCaseLabel.startsWith(RESTRICT_EDIT_PREFIX)) {
        const permissionType = removePrefix(label, RESTRICT_EDIT_PREFIX);
        if (!('edit' in restrictions)) {
          restrictions['edit'] = [permissionType];
        } else {
          restrictions['edit'].push(permissionType);
        }
      } else if (lowerCaseLabel.startsWith(RESTRICT_COMMENT_PREFIX)) {
        const permissionType = removePrefix(label, RESTRICT_COMMENT_PREFIX);
        if (!('comment' in restrictions)) {
          restrictions['comment'] = [permissionType];
        } else {
          restrictions['comment'].push(permissionType);
        }
      }
    });

    return restrictions;
  }
);

export const isRestricted = createSelector(
  restrictions,
  (restrictions) => {
    if (!restrictions) return false;
    return ('view' in restrictions && !!restrictions['view'].length) ||
      ('edit' in restrictions && !!restrictions['edit'].length) ||
      ('comment' in restrictions && !!restrictions['comment'].length);
  }
);

export const isOpen = createSelector(
  issue,
  (issue) => issue && issue.statusRef && issue.statusRef.meansOpen || false
);

const blockingIssueRefs = createSelector(
  issue,
  (issue) => issue && issue.blockingIssueRefs || []
);

const blockedOnIssueRefs = createSelector(
  issue,
  (issue) => issue && issue.blockedOnIssueRefs || []
);

export const relatedIssues = (state) => state.relatedIssues;

export const blockingIssues = createSelector(
  blockingIssueRefs, relatedIssues,
  (blockingRefs, relatedIssues) => blockingRefs.map((ref) => {
    const key = issueRefToString(ref);
    if (relatedIssues.has(key)) {
      return relatedIssues.get(key);
    }
    return ref;
  })
);

export const blockedOnIssues = createSelector(
  blockedOnIssueRefs, relatedIssues,
  (blockedOnRefs, relatedIssues) => blockedOnRefs.map((ref) => {
    const key = issueRefToString(ref);
    if (relatedIssues.has(key)) {
      return relatedIssues.get(key);
    }
    return ref;
  })
);

export const mergedInto = createSelector(
  issue, relatedIssues,
  (issue, relatedIssues) => issue && issue.mergedIntoRef
    && relatedIssues.get(issueRefToString(issue.mergedIntoRef))
);

export const sortedBlockedOn = createSelector(
  blockedOnIssues,
  (blockedOn) => blockedOn.sort((a, b) => {
    const aIsOpen = a.statusRef && a.statusRef.meansOpen ? 1 : 0;
    const bIsOpen = b.statusRef && b.statusRef.meansOpen ? 1 : 0;
    return bIsOpen - aIsOpen;
  })
);

// values (from issue.fieldValues) is an array with one entry per value.
// We want to turn this into a map of fieldNames -> values.
export const fieldValueMap = createSelector(
  fieldValues,
  (fieldValues) => {
    if (!fieldValues) return new Map();
    const acc = new Map();
    for (const v of fieldValues) {
      if (!v || !v.fieldRef || !v.fieldRef.fieldName || !v.value) continue;
      let key = [v.fieldRef.fieldName];
      if (v.phaseRef && v.phaseRef.phaseName) {
        key.push(v.phaseRef.phaseName);
      }
      key = key.join(' ');
      if (acc.has(key)) {
        acc.get(key).push(v.value);
      } else {
        acc.set(key, [v.value]);
      }
    }
    return acc;
  }
);

// Get the list of full componentDefs for the viewed issue.
export const components = createSelector(
  issue,
  project.componentsMap,
  (issue, components) => {
    if (!issue || !issue.componentRefs) return [];
    return issue.componentRefs.map((comp) => components.get(comp.path));
  }
);

export const fieldDefs = createSelector(
  project.fieldDefs,
  type,
  (fieldDefs, type) => {
    if (!fieldDefs) return [];
    type = type || '';
    return fieldDefs.filter((f) => {
      // Skip approval type and phase fields here.
      if (f.fieldRef.approvalName
          || f.fieldRef.type === fieldTypes.APPROVAL_TYPE
          || f.isPhaseField) {
        return false;
      }

      // If this fieldDef belongs to only one type, filter out the field if
      // that type isn't the specified type.
      if (f.applicableType && type.toLowerCase()
          !== f.applicableType.toLowerCase()) {
        return false;
      }

      return true;
    });
  }
);

// Action Creators
export const fetchCommentReferences = (comments, projectName) => {
  return async (dispatch) => {
    dispatch({type: actionType.FETCH_COMMENT_REFERENCES_START});

    try {
      const refs = await autolink.getReferencedArtifacts(comments, projectName);
      const commentRefs = new Map();
      refs.forEach(({componentName, existingRefs}) => {
        commentRefs.set(componentName, existingRefs);
      });
      dispatch({
        type: actionType.FETCH_COMMENT_REFERENCES_SUCCESS,
        commentReferences: commentRefs,
      });
    } catch (error) {
      dispatch({
        type: actionType.FETCH_COMMENT_REFERENCES_FAILURE,
        error,
      });
    }
  };
};

// TODO(zhangtiff): Figure out if we can reduce request/response sizes by
// diffing issues to fetch against issues we already know about to avoid
// fetching duplicate info.
export const fetchRelatedIssues = (issue) => async (dispatch) => {
  if (!issue) return;
  dispatch({type: actionType.FETCH_RELATED_ISSUES_START});

  const refsToFetch = (issue.blockedOnIssueRefs || []).concat(
    issue.blockingIssueRefs || []);
  if (issue.mergedIntoIssueRef) {
    refsToFetch.push(issue.mergedIntoIssueRef);
  }

  const message = {
    issueRefs: refsToFetch,
  };
  try {
    const resp = await window.prpcClient.call(
      'monorail.Issues', 'ListReferencedIssues', message);

    const relatedIssues = new Map();

    const openIssues = resp.openRefs || [];
    const closedIssues = resp.closedRefs || [];
    openIssues.forEach((issue) => {
      issue.statusRef.meansOpen = true;
      relatedIssues.set(issueRefToString(issue), issue);
    });
    closedIssues.forEach((issue) => {
      issue.statusRef.meansOpen = false;
      relatedIssues.set(issueRefToString(issue), issue);
    });
    dispatch({
      type: actionType.FETCH_RELATED_ISSUES_SUCCESS,
      relatedIssues: relatedIssues,
    });
  } catch (error) {
    dispatch({
      type: actionType.FETCH_RELATED_ISSUES_FAILURE,
      error,
    });
  };
};

export const fetchIssuePageData = (message) => async (dispatch) => {
  dispatch(actionCreator.fetchComments(message));
  dispatch(actionCreator.fetchIssue(message));
  dispatch(actionCreator.fetchIssuePermissions(message));
  dispatch(actionCreator.fetchIsStarred(message));
};

export const fetch = (message) => async (dispatch) => {
  dispatch({type: actionType.FETCH_ISSUE_START});

  try {
    const resp = await window.prpcClient.call(
      'monorail.Issues', 'GetIssue', message
    );

    dispatch({
      type: actionType.FETCH_ISSUE_SUCCESS,
      issue: resp.issue,
    });

    dispatch(fetchPermissions(message));
    if (!resp.issue.isDeleted) {
      dispatch(fetchRelatedIssues(resp.issue));
      dispatch(fetchHotlists(message.issueRef));
    }
  } catch (error) {
    dispatch({
      type: actionType.FETCH_ISSUE_FAILURE,
      error,
    });
  }
};

export const fetchHotlists = (issue) => async (dispatch) => {
  dispatch({type: actionType.FETCH_ISSUE_HOTLISTS_START});

  try {
    const resp = await window.prpcClient.call(
      'monorail.Features', 'ListHotlistsByIssue', {issue});

    const hotlists = (resp.hotlists || []);
    hotlists.sort((hotlistA, hotlistB) => {
      return hotlistA.name.localeCompare(hotlistB.name);
    });
    dispatch({
      type: actionType.FETCH_ISSUE_HOTLISTS_SUCCESS,
      hotlists,
    });
  } catch (error) {
    dispatch({
      type: actionType.FETCH_ISSUE_HOTLISTS_FAILURE,
      error,
    });
  };
};

export const fetchPermissions = (message) => async (dispatch) => {
  dispatch({type: actionType.FETCH_ISSUE_PERMISSIONS_START});

  try {
    const resp = await window.prpcClient.call(
      'monorail.Issues', 'ListIssuePermissions', message
    );

    dispatch({
      type: actionType.FETCH_ISSUE_PERMISSIONS_SUCCESS,
      permissions: resp.permissions,
    });
  } catch (error) {
    dispatch({
      type: actionType.FETCH_ISSUE_PERMISSIONS_FAILURE,
      error,
    });
  };
};

export const fetchComments = (message) => async (dispatch) => {
  dispatch({type: actionType.FETCH_COMMENTS_START});

  try {
    const resp = await window.prpcClient.call(
      'monorail.Issues', 'ListComments', message
    );

    dispatch({
      type: actionType.FETCH_COMMENTS_SUCCESS,
      comments: resp.comments,
    });
    dispatch(fetchCommentReferences(
      resp.comments, message.issueRef.projectName));
  } catch (error) {
    dispatch({
      type: actionType.FETCH_COMMENTS_FAILURE,
      error,
    });
  };
};

export const fetchIsStarred = (message) => async (dispatch) => {
  dispatch({type: actionType.FETCH_IS_STARRED_START});

  try {
    const resp = await window.prpcClient.call(
      'monorail.Issues', 'IsIssueStarred', message
    );

    dispatch({
      type: actionType.FETCH_IS_STARRED_SUCCESS,
      isStarred: resp.isStarred,
    });
  } catch (error) {
    dispatch({
      type: actionType.FETCH_IS_STARRED_FAILURE,
      error,
    });
  };
};

export const star = (issueRef, starred) => async (dispatch) => {
  dispatch({type: actionType.STAR_ISSUE_START});

  const message = {issueRef, starred};

  try {
    const resp = await window.prpcClient.call(
      'monorail.Issues', 'StarIssue', message
    );

    dispatch({
      type: actionType.STAR_ISSUE_SUCCESS,
      starCount: resp.starCount,
      isStarred: starred,
    });
  } catch (error) {
    dispatch({
      type: actionType.STAR_ISSUE_FAILURE,
      error,
    });
  }
};

export const presubmit = (message) => async (dispatch) => {
  dispatch({type: actionType.PRESUBMIT_ISSUE_START});

  try {
    const resp = await window.prpcClient.call(
      'monorail.Issues', 'PresubmitIssue', message);

    dispatch({
      type: actionType.PRESUBMIT_ISSUE_SUCCESS,
      presubmitResponse: resp,
    });
  } catch (error) {
    dispatch({
      type: actionType.PRESUBMIT_ISSUE_FAILURE,
      error: error,
    });
  }
};

export const updateApproval = (message) => async (dispatch) => {
  dispatch({type: actionType.UPDATE_APPROVAL_START});

  try {
    const resp = await window.prpcClient.call(
      'monorail.Issues', 'UpdateApproval', message);

    dispatch({
      type: actionType.UPDATE_APPROVAL_SUCCESS,
      approval: resp.approval,
    });
    const baseMessage = {
      issueRef: message.issueRef,
    };
    dispatch(fetch(baseMessage));
    dispatch(fetchComments(baseMessage));
  } catch (error) {
    dispatch({
      type: actionType.UPDATE_APPROVAL_FAILURE,
      error: error,
    });
  };
};

export const update = (message) => async (dispatch) => {
  dispatch({type: actionType.UPDATE_ISSUE_START});

  try {
    const resp = await window.prpcClient.call(
      'monorail.Issues', 'UpdateIssue', message);

    dispatch({
      type: actionType.UPDATE_ISSUE_SUCCESS,
      issue: resp.issue,
    });
    const fetchCommentsMessage = {
      issueRef: message.issueRef,
    };
    dispatch(fetchComments(fetchCommentsMessage));
    dispatch(fetchRelatedIssues(resp.issue));
  } catch (error) {
    dispatch({
      type: actionType.UPDATE_ISSUE_FAILURE,
      error: error,
    });
  };
};

export const convert = (message) => async (dispatch) => {
  dispatch({type: actionType.CONVERT_ISSUE_START});

  try {
    const resp = await window.prpcClient.call(
      'monorail.Issues', 'ConvertIssueApprovalsTemplate', message);

    dispatch({
      type: actionType.CONVERT_ISSUE_SUCCESS,
      issue: resp.issue,
    });
    const fetchCommentsMessage = {
      issueRef: message.issueRef,
    };
    dispatch(fetchComments(fetchCommentsMessage));
  } catch (error) {
    dispatch({
      type: actionType.CONVERT_ISSUE_FAILURE,
      error: error,
    });
  };
};
