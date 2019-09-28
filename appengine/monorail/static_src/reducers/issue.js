// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {combineReducers} from 'redux';
import {createSelector} from 'reselect';
import {autolink} from 'autolink.js';
import {fieldTypes, extractTypeForIssue,
  fieldValuesToMap} from 'shared/issue-fields.js';
import {removePrefix, objectToMap} from 'shared/helpers.js';
import {issueRefToString} from 'shared/converters.js';
import {fromShortlink} from 'shared/federated.js';
import {createReducer, createRequestReducer,
  createKeyedRequestReducer} from './redux-helpers.js';
import * as project from './project.js';
import * as user from './user.js';
import {fieldValueMapKey} from 'shared/metadata-helpers.js';
import {prpcClient} from 'prpc-client-instance.js';
import loadGapi, {fetchGapiEmail} from 'shared/gapi-loader.js';

// Actions
const SET_ISSUE_REF = 'SET_ISSUE_REF';

export const FETCH_START = 'FETCH_START';
export const FETCH_SUCCESS = 'FETCH_SUCCESS';
export const FETCH_FAILURE = 'FETCH_FAILURE';

const FETCH_HOTLISTS_START = 'FETCH_HOTLISTS_START';
const FETCH_HOTLISTS_SUCCESS = 'FETCH_HOTLISTS_SUCCESS';
const FETCH_HOTLISTS_FAILURE = 'FETCH_HOTLISTS_FAILURE';

const FETCH_ISSUE_LIST_START = 'FETCH_ISSUE_LIST_START';
const FETCH_ISSUE_LIST_UPDATE = 'FETCH_ISSUE_LIST_UPDATE';
const FETCH_ISSUE_LIST_SUCCESS = 'FETCH_ISSUE_LIST_SUCCESS';
const FETCH_ISSUE_LIST_FAILURE = 'FETCH_ISSUE_LIST_FAILURE';

const FETCH_PERMISSIONS_START = 'FETCH_PERMISSIONS_START';
const FETCH_PERMISSIONS_SUCCESS = 'FETCH_PERMISSIONS_SUCCESS';
const FETCH_PERMISSIONS_FAILURE = 'FETCH_PERMISSIONS_FAILURE';

export const STAR_START = 'STAR_START';
export const STAR_SUCCESS = 'STAR_SUCCESS';
const STAR_FAILURE = 'STAR_FAILURE';

const PRESUBMIT_START = 'PRESUBMIT_START';
const PRESUBMIT_SUCCESS = 'PRESUBMIT_SUCCESS';
const PRESUBMIT_FAILURE = 'PRESUBMIT_FAILURE';

const PREDICT_COMPONENT_START = 'PREDICT_COMPONENT_START';
const PREDICT_COMPONENT_SUCCESS = 'PREDICT_COMPONENT_SUCCESS';
const PREDICT_COMPONENT_FAILURE = 'PREDICT_COMPONENT_FAILURE';

export const FETCH_IS_STARRED_START = 'FETCH_IS_STARRED_START';
export const FETCH_IS_STARRED_SUCCESS = 'FETCH_IS_STARRED_SUCCESS';
const FETCH_IS_STARRED_FAILURE = 'FETCH_IS_STARRED_FAILURE';

const FETCH_ISSUES_STARRED_START = 'FETCH_ISSUES_STARRED_START';
export const FETCH_ISSUES_STARRED_SUCCESS = 'FETCH_ISSUES_STARRED_SUCCESS';
const FETCH_ISSUES_STARRED_FAILURE = 'FETCH_ISSUES_STARRED_FAILURE';

const FETCH_COMMENTS_START = 'FETCH_COMMENTS_START';
export const FETCH_COMMENTS_SUCCESS = 'FETCH_COMMENTS_SUCCESS';
const FETCH_COMMENTS_FAILURE = 'FETCH_COMMENTS_FAILURE';

const FETCH_COMMENT_REFERENCES_START = 'FETCH_COMMENT_REFERENCES_START';
const FETCH_COMMENT_REFERENCES_SUCCESS = 'FETCH_COMMENT_REFERENCES_SUCCESS';
const FETCH_COMMENT_REFERENCES_FAILURE = 'FETCH_COMMENT_REFERENCES_FAILURE';

const FETCH_REFERENCED_USERS_START = 'FETCH_REFERENCED_USERS_START';
const FETCH_REFERENCED_USERS_SUCCESS = 'FETCH_REFERENCED_USERS_SUCCESS';
const FETCH_REFERENCED_USERS_FAILURE = 'FETCH_REFERENCED_USERS_FAILURE';

const FETCH_RELATED_ISSUES_START = 'FETCH_RELATED_ISSUES_START';
const FETCH_RELATED_ISSUES_SUCCESS = 'FETCH_RELATED_ISSUES_SUCCESS';
const FETCH_RELATED_ISSUES_FAILURE = 'FETCH_RELATED_ISSUES_FAILURE';

const CONVERT_START = 'CONVERT_START';
const CONVERT_SUCCESS = 'CONVERT_SUCCESS';
const CONVERT_FAILURE = 'CONVERT_FAILURE';

const UPDATE_START = 'UPDATE_START';
const UPDATE_SUCCESS = 'UPDATE_SUCCESS';
const UPDATE_FAILURE = 'UPDATE_FAILURE';

const UPDATE_APPROVAL_START = 'UPDATE_APPROVAL_START';
const UPDATE_APPROVAL_SUCCESS = 'UPDATE_APPROVAL_SUCCESS';
const UPDATE_APPROVAL_FAILURE = 'UPDATE_APPROVAL_FAILURE';

/* State Shape
{
  issueRef: {
    localId: Number,
    projectName: String,
  },

  currentIssue: Object,

  hotlists: Array,
  issueList: {
    issues: Array,
    progress: Number,
    totalResults: Number,
  }
  comments: Array,
  commentReferences: Object,
  relatedIssues: Object,
  referencedUsers: Array,
  starredIssues: Object,
  permissions: Array,
  presubmitResponse: Object,
  predictedComponent: String,

  requests: {
    fetch: Object,
    fetchHotlists: Object,
    fetchIssueList: Object,
    fetchPermissions: Object,
    star: Object,
    presubmit: Object,
    predictComponent: Object,
    fetchComments: Object,
    fetchCommentReferences: Object,
    fetchRelatedIssues: Object,
    fetchStarredIssues: Object,
    fetchStarredIssues: Object,
    convert: Object,
    update: Object,
    updateApproval: Object,
  },
}
*/

// Helpers for the reducers.
const updateApprovalValues = (issue, approval) => {
  if (!issue.approvalValues) return issue;
  const newApprovals = issue.approvalValues.map((item, i) => {
    if (item.fieldRef.fieldName === approval.fieldRef.fieldName) {
      // PhaseRef isn't populated on the response so we want to make sure
      // it doesn't overwrite the original phaseRef with {}.
      return {...approval, phaseRef: item.phaseRef};
    }
    return item;
  });
  return {...issue, approvalValues: newApprovals};
};

// Reducers
const localIdReducer = createReducer(0, {
  [SET_ISSUE_REF]: (state, action) => action.localId || state,
});

const projectNameReducer = createReducer('', {
  [SET_ISSUE_REF]: (state, action) => action.projectName || state,
});

const currentIssueReducer = createReducer({}, {
  [FETCH_SUCCESS]: (_state, action) => action.issue,
  [STAR_SUCCESS]: (state, action) => {
    return {...state, starCount: action.starCount};
  },
  [CONVERT_SUCCESS]: (_state, action) => action.issue,
  [UPDATE_SUCCESS]: (_state, action) => action.issue,
  [UPDATE_APPROVAL_SUCCESS]: (state, action) => {
    return updateApprovalValues(state, action.approval);
  },
});

const hotlistsReducer = createReducer([], {
  [FETCH_HOTLISTS_SUCCESS]: (_, action) => action.hotlists,
});

const issueListReducer = createReducer([], {
  [FETCH_ISSUE_LIST_SUCCESS]: (_state, action) => action.issueList,
  [FETCH_ISSUE_LIST_UPDATE]: (_state, action) => action.issueList,
});

const commentsReducer = createReducer([], {
  [FETCH_COMMENTS_SUCCESS]: (_state, action) => action.comments,
});

const commentReferencesReducer = createReducer({}, {
  [FETCH_COMMENTS_START]: (_state, _action) => ({}),
  [FETCH_COMMENT_REFERENCES_SUCCESS]: (_state, action) => {
    return action.commentReferences;
  },
});

const relatedIssuesReducer = createReducer({}, {
  [FETCH_RELATED_ISSUES_SUCCESS]: (_state, action) => action.relatedIssues,
});

const referencedUsersReducer = createReducer({}, {
  [FETCH_REFERENCED_USERS_SUCCESS]: (_state, action) => action.referencedUsers,
});

export const starredIssuesReducer = createReducer({}, {
  [STAR_SUCCESS]: (state, action) => {
    return {...state, [action.ref]: action.starred};
  },
  [FETCH_ISSUES_STARRED_SUCCESS]: (_state, action) => {
    return action.starredIssues.reduce((obj, ref) => ({
      ...obj, [ref]: true}), {});
  },
  [FETCH_IS_STARRED_SUCCESS]: (state, action) => {
    const ref = issueRefToString(action.ref.issueRef);
    return {...state, [ref]: action.starred};
  },
});

const presubmitResponseReducer = createReducer({}, {
  [PRESUBMIT_SUCCESS]: (_state, action) => action.presubmitResponse,
});

const predictedComponentReducer = createReducer('', {
  [PREDICT_COMPONENT_SUCCESS]: (_state, action) => action.component,
});

const permissionsReducer = createReducer([], {
  [FETCH_PERMISSIONS_SUCCESS]: (_state, action) => action.permissions,
});

const requestsReducer = combineReducers({
  fetch: createRequestReducer(
      FETCH_START, FETCH_SUCCESS, FETCH_FAILURE),
  fetchHotlists: createRequestReducer(
      FETCH_HOTLISTS_START, FETCH_HOTLISTS_SUCCESS, FETCH_HOTLISTS_FAILURE),
  fetchIssueList: createRequestReducer(
      FETCH_ISSUE_LIST_START,
      FETCH_ISSUE_LIST_SUCCESS,
      FETCH_ISSUE_LIST_FAILURE),
  fetchPermissions: createRequestReducer(
      FETCH_PERMISSIONS_START,
      FETCH_PERMISSIONS_SUCCESS,
      FETCH_PERMISSIONS_FAILURE),
  starringIssues: createKeyedRequestReducer(
      STAR_START, STAR_SUCCESS, STAR_FAILURE),
  presubmit: createRequestReducer(
      PRESUBMIT_START, PRESUBMIT_SUCCESS, PRESUBMIT_FAILURE),
  predictComponent: createRequestReducer(
      PREDICT_COMPONENT_START,
      PREDICT_COMPONENT_SUCCESS,
      PREDICT_COMPONENT_FAILURE),
  fetchComments: createRequestReducer(
      FETCH_COMMENTS_START, FETCH_COMMENTS_SUCCESS, FETCH_COMMENTS_FAILURE),
  fetchCommentReferences: createRequestReducer(
      FETCH_COMMENT_REFERENCES_START,
      FETCH_COMMENT_REFERENCES_SUCCESS,
      FETCH_COMMENT_REFERENCES_FAILURE),
  fetchRelatedIssues: createRequestReducer(
      FETCH_RELATED_ISSUES_START,
      FETCH_RELATED_ISSUES_SUCCESS,
      FETCH_RELATED_ISSUES_FAILURE),
  fetchReferencedUsers: createRequestReducer(
      FETCH_REFERENCED_USERS_START,
      FETCH_REFERENCED_USERS_SUCCESS,
      FETCH_REFERENCED_USERS_FAILURE),
  fetchIsStarred: createRequestReducer(
      FETCH_IS_STARRED_START, FETCH_IS_STARRED_SUCCESS,
      FETCH_IS_STARRED_FAILURE),
  fetchStarredIssues: createRequestReducer(
      FETCH_ISSUES_STARRED_START, FETCH_ISSUES_STARRED_SUCCESS,
      FETCH_ISSUES_STARRED_FAILURE
  ),
  convert: createRequestReducer(
      CONVERT_START, CONVERT_SUCCESS, CONVERT_FAILURE),
  update: createRequestReducer(
      UPDATE_START, UPDATE_SUCCESS, UPDATE_FAILURE),
  // Assumption: It's okay to prevent the user from sending multiple
  // approval update requests at once, even for different approvals.
  updateApproval: createRequestReducer(
      UPDATE_APPROVAL_START, UPDATE_APPROVAL_SUCCESS, UPDATE_APPROVAL_FAILURE),
});

export const reducer = combineReducers({
  issueRef: combineReducers({
    localId: localIdReducer,
    projectName: projectNameReducer,
  }),

  currentIssue: currentIssueReducer,

  hotlists: hotlistsReducer,
  issueList: issueListReducer,
  comments: commentsReducer,
  commentReferences: commentReferencesReducer,
  relatedIssues: relatedIssuesReducer,
  referencedUsers: referencedUsersReducer,
  starredIssues: starredIssuesReducer,
  permissions: permissionsReducer,
  presubmitResponse: presubmitResponseReducer,
  predictedComponent: predictedComponentReducer,

  requests: requestsReducer,
});

// Selectors
const RESTRICT_VIEW_PREFIX = 'restrict-view-';
const RESTRICT_EDIT_PREFIX = 'restrict-editissue-';
const RESTRICT_COMMENT_PREFIX = 'restrict-addissuecomment-';

export const issueRef = (state) => state.issue.issueRef;

// TODO(zhangtiff): Eventually Monorail's Redux state will store
// multiple issues, and this selector will have to find the viewed
// issue based on a viewed issue ref.
export const issue = (state) => state.issue.currentIssue;

export const comments = (state) => state.issue.comments;
export const commentsLoaded = (state) => state.issue.commentsLoaded;

const _commentReferences = (state) => state.issue.commentReferences;
export const commentReferences = createSelector(_commentReferences,
    (commentReferences) => objectToMap(commentReferences));

export const hotlists = (state) => state.issue.hotlists;
export const issueList = (state) => state.issue.issueList.issues;
export const totalIssues = (state) => state.issue.issueList.totalResults;
export const issueListProgress = (state) => state.issue.issueList.progress;
export const issueListPhaseNames = createSelector(issueList, (issueList) => {
  const phaseNamesSet = new Set();
  if (issueList) {
    issueList.forEach(({phases}) => {
      if (phases) {
        phases.forEach(({phaseRef: {phaseName}}) => {
          phaseNamesSet.add(phaseName.toLowerCase());
        });
      }
    });
  }
  return Array.from(phaseNamesSet);
});


export const issueLoaded = (state) => state.issue.issueLoaded;
export const permissions = (state) => state.issue.permissions;
export const presubmitResponse = (state) => state.issue.presubmitResponse;
export const predictedComponent = (state) => state.issue.predictedComponent;

const _relatedIssues = (state) => state.issue.relatedIssues || {};
export const relatedIssues = createSelector(_relatedIssues,
    (relatedIssues) => objectToMap(relatedIssues));

const _referencedUsers = (state) => state.issue.referencedUsers || {};
export const referencedUsers = createSelector(_referencedUsers,
    (referencedUsers) => objectToMap(referencedUsers));

export const isStarred = (state) => state.issue.isStarred;
export const _starredIssues = (state) => state.issue.starredIssues;

export const requests = (state) => state.issue.requests;

// Returns a Map of in flight StarIssues requests, keyed by issueRef.
export const starringIssues = createSelector(requests, (requests) =>
  objectToMap(requests.starringIssues));

export const starredIssues = createSelector(
    _starredIssues,
    (starredIssues) => {
      const stars = new Set();
      for (const [ref, starred] of Object.entries(starredIssues)) {
        if (starred) stars.add(ref);
      }
      return stars;
    }
);

// TODO(zhangtiff): Split up either comments or approvals into their own "duck".
export const commentsByApprovalName = createSelector(
    comments,
    (comments) => {
      const map = new Map();
      comments.forEach((comment) => {
        const key = (comment.approvalRef && comment.approvalRef.fieldName) || '';
        if (map.has(key)) {
          map.get(key).push(comment);
        } else {
          map.set(key, [comment]);
        }
      });
      return map;
    }
);

export const fieldValues = createSelector(
    issue,
    (issue) => issue && issue.fieldValues
);

export const labelRefs = createSelector(
    issue,
    (issue) => issue && issue.labelRefs
);

export const type = createSelector(
    fieldValues,
    labelRefs,
    (fieldValues, labelRefs) => extractTypeForIssue(fieldValues, labelRefs)
);

export const restrictions = createSelector(
    labelRefs,
    (labelRefs) => {
      if (!labelRefs) return {};

      const restrictions = {};

      labelRefs.forEach((labelRef) => {
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

export const isOpen = createSelector(
    issue,
    (issue) => issue && issue.statusRef && issue.statusRef.meansOpen || false);

// Returns a function that, given an issue and its related issues,
// returns a combined list of issue ref strings including related issues,
// blocking or blocked on issues, and federated references.
const mapRefsWithRelated = (blocking) => {
  return (issue, relatedIssues) => {
    let refs = [];
    if (blocking) {
      if (issue.blockingIssueRefs) {
        refs = refs.concat(issue.blockingIssueRefs);
      }
      if (issue.danglingBlockingRefs) {
        refs = refs.concat(issue.danglingBlockingRefs);
      }
    } else {
      if (issue.blockedOnIssueRefs) {
        refs = refs.concat(issue.blockedOnIssueRefs);
      }
      if (issue.danglingBlockedOnRefs) {
        refs = refs.concat(issue.danglingBlockedOnRefs);
      }
    }

    // Note: relatedIssues is a Redux generated key for issues, not part of the
    // pRPC Issue object.
    if (issue.relatedIssues) {
      refs = refs.concat(issue.relatedIssues);
    }
    return refs.map((ref) => {
      const key = issueRefToString(ref);
      if (relatedIssues.has(key)) {
        return relatedIssues.get(key);
      }
      return ref;
    });
  };
};

export const blockingIssues = createSelector(
    issue, relatedIssues,
    mapRefsWithRelated(true)
);

export const blockedOnIssues = createSelector(
    issue, relatedIssues,
    mapRefsWithRelated(false)
);

export const mergedInto = createSelector(
    issue, relatedIssues,
    (issue, relatedIssues) => {
      if (!issue || !issue.mergedIntoIssueRef) return {};
      const key = issueRefToString(issue.mergedIntoIssueRef);
      if (relatedIssues && relatedIssues.has(key)) {
        return relatedIssues.get(key);
      }
      return issue.mergedIntoIssueRef;
    }
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
    (fieldValues) => fieldValuesToMap(fieldValues)
);

// Get the list of full componentDefs for the viewed issue.
export const components = createSelector(
    issue,
    project.componentsMap,
    (issue, components) => {
      if (!issue || !issue.componentRefs) return [];
      return issue.componentRefs.map(
          (comp) => components.get(comp.path) || comp);
    }
);

// Get custom fields that apply to a specific issue.
export const fieldDefs = createSelector(
    project.fieldDefs,
    type,
    fieldValueMap,
    (fieldDefs, type, fieldValues) => {
      if (!fieldDefs) return [];
      type = type || '';
      return fieldDefs.filter((f) => {
        const fieldValueKey = fieldValueMapKey(f.fieldRef.fieldName,
            f.phaseRef && f.phaseRef.phaseName);
        if (fieldValues && fieldValues.has(fieldValueKey)) {
        // Regardless of other checks, include a particular field def if the
        // issue has a value defined.
          return true;
        }
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
export const setIssueRef = (localId, projectName) => {
  return {type: SET_ISSUE_REF, localId, projectName};
};

export const fetchCommentReferences = (comments, projectName) => {
  return async (dispatch) => {
    dispatch({type: FETCH_COMMENT_REFERENCES_START});

    try {
      const refs = await autolink.getReferencedArtifacts(comments, projectName);
      const commentRefs = {};
      refs.forEach(({componentName, existingRefs}) => {
        commentRefs[componentName] = existingRefs;
      });
      dispatch({
        type: FETCH_COMMENT_REFERENCES_SUCCESS,
        commentReferences: commentRefs,
      });
    } catch (error) {
      dispatch({type: FETCH_COMMENT_REFERENCES_FAILURE, error});
    }
  };
};

export const fetchReferencedUsers = (issue) => async (dispatch) => {
  if (!issue) return;
  dispatch({type: FETCH_REFERENCED_USERS_START});

  // TODO(zhangtiff): Make this function account for custom fields
  // of type user.
  const userRefs = [...(issue.ccRefs || [])];
  if (issue.ownerRef) {
    userRefs.push(issue.ownerRef);
  }
  (issue.approvalValues || []).forEach((approval) => {
    userRefs.push(...(approval.approverRefs || []));
    if (approval.setterRef) {
      userRefs.push(approval.setterRef);
    }
  });

  try {
    const resp = await prpcClient.call(
        'monorail.Users', 'ListReferencedUsers', {userRefs});

    const referencedUsers = {};
    (resp.users || []).forEach((user) => {
      referencedUsers[user.displayName] = user;
    });
    dispatch({type: FETCH_REFERENCED_USERS_SUCCESS, referencedUsers});
  } catch (error) {
    dispatch({type: FETCH_REFERENCED_USERS_FAILURE, error});
  }
};

export const fetchFederatedReferenceStatuses = (issue) => async (dispatch) => {
  // Concat all potential fedrefs together, convert from shortlink to classes,
  // then fire off a request to fetch the status of each.
  const fedRefs = []
      .concat(issue.danglingBlockingRefs || [])
      .concat(issue.danglingBlockedOnRefs || [])
      .concat(issue.mergedIntoIssueRef ? [issue.mergedIntoIssueRef] : [])
      .filter((ref) => ref && ref.extIdentifier)
      .map((ref) => fromShortlink(ref.extIdentifier))
      .filter((fedRef) => fedRef);

  // If no FedRefs, return empty Map.
  if (fedRefs.length === 0) {
    return new Map();
  }

  // Load email separately since it might have changed.
  await loadGapi();
  const email = await fetchGapiEmail();

  // If already logged in, dispatch login success event.
  dispatch({
    type: user.GAPI_LOGIN_SUCCESS,
    email: email,
  });

  const fedRefPromises = fedRefs.map((fedRef) => fedRef.isOpen());
  const results = await Promise.all(fedRefPromises);

  // Create a map of {extIdentifier -> isOpen}.
  const shortlinkToStatus = new Map(results.map((result, i) => {
    return [fedRefs[i].shortlink, result];
  }));

  // TODO(jeffcarp): Expand this to return issue summary as well,
  // update reducer to assign appropriately.
  return shortlinkToStatus;
};

// TODO(zhangtiff): Figure out if we can reduce request/response sizes by
// diffing issues to fetch against issues we already know about to avoid
// fetching duplicate info.
export const fetchRelatedIssues = (issue) => async (dispatch) => {
  if (!issue) return;
  dispatch({type: FETCH_RELATED_ISSUES_START});

  const refsToFetch = (issue.blockedOnIssueRefs || []).concat(
      issue.blockingIssueRefs || []);
  // Add mergedinto ref, exclude FedRefs which are fetched separately.
  if (issue.mergedIntoIssueRef && !issue.mergedIntoIssueRef.extIdentifier) {
    refsToFetch.push(issue.mergedIntoIssueRef);
  }

  const message = {
    issueRefs: refsToFetch,
  };
  try {
    // TODO(jeffcarp): Split into 2 action creators, resolve separately.
    const [resp, fedRefStatuses] = await Promise.all([
      prpcClient.call('monorail.Issues', 'ListReferencedIssues', message),
      dispatch(fetchFederatedReferenceStatuses(issue)),
    ]);

    const relatedIssues = {};

    const openIssues = resp.openRefs || [];
    const closedIssues = resp.closedRefs || [];
    openIssues.forEach((issue) => {
      issue.statusRef.meansOpen = true;
      relatedIssues[issueRefToString(issue)] = issue;
    });
    closedIssues.forEach((issue) => {
      issue.statusRef.meansOpen = false;
      relatedIssues[issueRefToString(issue)] = issue;
    });

    fedRefStatuses.forEach((isOpen, shortlink) => {
      relatedIssues[shortlink] = {
        extIdentifier: shortlink,
        statusRef: {meansOpen: isOpen},
      };
    });

    dispatch({
      type: FETCH_RELATED_ISSUES_SUCCESS,
      relatedIssues: relatedIssues,
    });
  } catch (error) {
    dispatch({type: FETCH_RELATED_ISSUES_FAILURE, error});
  };
};

export const fetchIssuePageData = (message) => async (dispatch) => {
  dispatch(fetchComments(message));
  dispatch(fetch(message));
  dispatch(fetchPermissions(message));
  dispatch(fetchIsStarred(message));
};

export const fetch = (message) => async (dispatch) => {
  dispatch({type: FETCH_START});

  try {
    const resp = await prpcClient.call(
        'monorail.Issues', 'GetIssue', message
    );
    const movedToRef = resp.movedToRef;
    const issue = {...resp.issue};
    if (movedToRef) {
      issue.movedToRef = movedToRef;
    }

    dispatch({type: FETCH_SUCCESS, issue});

    if (!issue.isDeleted && !movedToRef) {
      dispatch(fetchRelatedIssues(issue));
      dispatch(fetchHotlists(message.issueRef));
      dispatch(fetchReferencedUsers(issue));
      dispatch(user.fetchProjects([issue.reporterRef]));
    }
  } catch (error) {
    dispatch({type: FETCH_FAILURE, error});
  }
};

export const fetchHotlists = (issue) => async (dispatch) => {
  dispatch({type: FETCH_HOTLISTS_START});

  try {
    const resp = await prpcClient.call(
        'monorail.Features', 'ListHotlistsByIssue', {issue});

    const hotlists = (resp.hotlists || []);
    hotlists.sort((hotlistA, hotlistB) => {
      return hotlistA.name.localeCompare(hotlistB.name);
    });
    dispatch({type: FETCH_HOTLISTS_SUCCESS, hotlists});
  } catch (error) {
    dispatch({type: FETCH_HOTLISTS_FAILURE, error});
  };
};

export const fetchIssueList =
  (params, projectName, pagination = {}, maxCalls = 1) => async (dispatch) => {
    let issueList = {};
    const promises = [];
    const issuesByRequest = [];
    let issueLimit;
    let totalIssues;
    let totalCalls;
    const itemsPerCall = (pagination.maxItems || 1000);

    const can = Number.parseInt(params.can) || undefined;

    dispatch({type: FETCH_ISSUE_LIST_START});

    // initial api call made to determine total number of issues matching
    // the query.
    try {
      // TODO(zhangtiff): Refactor this action creator when adding issue
      // list pagination.
      const resp = await prpcClient.call(
          'monorail.Issues', 'ListIssues', {
            query: params.q,
            cannedQuery: can,
            projectNames: [projectName],
            pagination: pagination,
            groupBySpec: params.groupby,
            sortSpec: params.sort,
          });

      issueList = (resp || {});
      issuesByRequest[0] = issueList.issues;
      issueLimit = issueList.totalResults;

      // determine correct issues to load and number of calls to be made.
      if (issueLimit > (itemsPerCall * maxCalls)) {
        totalIssues = itemsPerCall * maxCalls;
        totalCalls = maxCalls - 1;
      } else {
        totalIssues = issueLimit;
        totalCalls = Math.ceil(issueLimit / itemsPerCall) - 1;
      }

      if (totalIssues) {
        issueList.progress =
          issueList.issues.length / totalIssues;
      } else {
        issueList.progress = 1;
      }

      dispatch({type: FETCH_ISSUE_LIST_UPDATE, issueList});

      // remaining api calls are made.
      for (let i = 1; i <= totalCalls; i++) {
        promises[i - 1] = (async () => {
          const resp = await prpcClient.call(
              'monorail.Issues', 'ListIssues', {
                query: params.q,
                cannedQuery: can,
                projectNames: [projectName],
                pagination: {start: i * itemsPerCall, maxItems: itemsPerCall},
                groupBySpec: params.groupby,
                sortSpec: params.sort,
              });
          issuesByRequest[i] = (resp.issues || []);
          // sort the issues in the correct order.
          issueList.issues = [];
          issuesByRequest.forEach((issue) => {
            issueList.issues = issueList.issues.concat(issue);
          });
          issueList.progress =
            issueList.issues.length / totalIssues;
          dispatch({type: FETCH_ISSUE_LIST_UPDATE, issueList});
        })();
      }

      await Promise.all(promises);

      dispatch({type: FETCH_ISSUE_LIST_SUCCESS, issueList});
    } catch (error) {
      dispatch({type: FETCH_ISSUE_LIST_FAILURE, error});
    };
  };

export const fetchPermissions = (message) => async (dispatch) => {
  dispatch({type: FETCH_PERMISSIONS_START});

  try {
    const resp = await prpcClient.call(
        'monorail.Issues', 'ListIssuePermissions', message
    );

    dispatch({type: FETCH_PERMISSIONS_SUCCESS, permissions: resp.permissions});
  } catch (error) {
    dispatch({type: FETCH_PERMISSIONS_FAILURE, error});
  };
};

export const fetchComments = (message) => async (dispatch) => {
  dispatch({type: FETCH_COMMENTS_START});

  try {
    const resp = await prpcClient.call(
        'monorail.Issues', 'ListComments', message);

    dispatch({type: FETCH_COMMENTS_SUCCESS, comments: resp.comments});
    dispatch(fetchCommentReferences(
        resp.comments, message.issueRef.projectName));

    const commenterRefs = (resp.comments || []).map(
        (comment) => comment.commenter);
    dispatch(user.fetchProjects(commenterRefs));
  } catch (error) {
    dispatch({type: FETCH_COMMENTS_FAILURE, error});
  };
};

export const fetchIsStarred = (message) => async (dispatch) => {
  dispatch({type: FETCH_IS_STARRED_START});
  try {
    const resp = await prpcClient.call(
        'monorail.Issues', 'IsIssueStarred', message
    );

    dispatch({
      type: FETCH_IS_STARRED_SUCCESS,
      starred: resp.isStarred,
      ref: message,
    });
  } catch (error) {
    dispatch({type: FETCH_IS_STARRED_FAILURE, error});
  };
};

export const fetchStarredIssues = () => async (dispatch) => {
  dispatch({type: FETCH_ISSUES_STARRED_START});

  try {
    const resp = await prpcClient.call(
        'monorail.Issues', 'ListStarredIssues', {}
    );
    const issueIds = (resp.starredIssueRefs || []).map(
        (ref) => issueRefToString(ref));
    dispatch({type: FETCH_ISSUES_STARRED_SUCCESS, starredIssues: issueIds});
  } catch (error) {
    dispatch({type: FETCH_ISSUES_STARRED_FAILURE, error});
  };
};

export const star = (issueRef, starred) => async (dispatch) => {
  const requestKey = issueRefToString(issueRef);

  dispatch({type: STAR_START, requestKey});
  const message = {issueRef, starred};

  try {
    const resp = await prpcClient.call(
        'monorail.Issues', 'StarIssue', message
    );
    const ref = issueRefToString(issueRef);

    dispatch({
      type: STAR_SUCCESS,
      starCount: resp.starCount,
      ref: ref,
      starred: starred,
      requestKey,
    });
  } catch (error) {
    dispatch({type: STAR_FAILURE, error, requestKey});
  }
};

export const presubmit = (message) => async (dispatch) => {
  dispatch({type: PRESUBMIT_START});

  try {
    const resp = await prpcClient.call(
        'monorail.Issues', 'PresubmitIssue', message);

    dispatch({type: PRESUBMIT_SUCCESS, presubmitResponse: resp});
  } catch (error) {
    dispatch({type: PRESUBMIT_FAILURE, error: error});
  }
};

export const predictComponent = (projectName, text) => async (dispatch) => {
  dispatch({type: PREDICT_COMPONENT_START});

  const message = {
    projectName,
    text,
  };

  try {
    const response = await prpcClient.call(
        'monorail.Features', 'PredictComponent', message);
    const component = response.componentRef && response.componentRef.path ?
      response.componentRef.path : '';
    dispatch({type: PREDICT_COMPONENT_SUCCESS, component});
  } catch (error) {
    dispatch({type: PREDICT_COMPONENT_FAILURE, error: error});
  }
};

export const updateApproval = (message) => async (dispatch) => {
  dispatch({type: UPDATE_APPROVAL_START});

  try {
    const resp = await prpcClient.call(
        'monorail.Issues', 'UpdateApproval', message);

    dispatch({type: UPDATE_APPROVAL_SUCCESS, approval: resp.approval});
    const baseMessage = {issueRef: message.issueRef};
    dispatch(fetch(baseMessage));
    dispatch(fetchComments(baseMessage));
  } catch (error) {
    dispatch({type: UPDATE_APPROVAL_FAILURE, error: error});
  };
};

export const update = (message) => async (dispatch) => {
  dispatch({type: UPDATE_START});

  try {
    const resp = await prpcClient.call(
        'monorail.Issues', 'UpdateIssue', message);

    dispatch({type: UPDATE_SUCCESS, issue: resp.issue});
    const fetchCommentsMessage = {issueRef: message.issueRef};
    dispatch(fetchComments(fetchCommentsMessage));
    dispatch(fetchRelatedIssues(resp.issue));
    dispatch(fetchReferencedUsers(resp.issue));
  } catch (error) {
    dispatch({type: UPDATE_FAILURE, error: error});
  };
};

export const convert = (message) => async (dispatch) => {
  dispatch({type: CONVERT_START});

  try {
    const resp = await prpcClient.call(
        'monorail.Issues', 'ConvertIssueApprovalsTemplate', message);

    dispatch({type: CONVERT_SUCCESS, issue: resp.issue});
    const fetchCommentsMessage = {issueRef: message.issueRef};
    dispatch(fetchComments(fetchCommentsMessage));
  } catch (error) {
    dispatch({type: CONVERT_FAILURE, error: error});
  };
};
