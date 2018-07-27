// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


(function(window) {
  'use strict';

  const CRBUG_LINK_RE = '(?<prefix>\\b(https?:\/\/)?crbug\\.com\/)((?<project_name>\\b[-a-z0-9]+)(?<separator>\/))?(?<local_id>\\d+)\\b(?<anchor>\\#c[0-9]+)?';
  const crbugReReplacers = [{re: CRBUG_LINK_RE, replacerFunc: ReplaceIssueRef}];

  const Components = new Map();
  Components.set(
      '01-tracker-crbug',
      {
        lookup: LookupReferencedIssues,
        extractRefs: ExtractProjectAndIssueIds,
        replacers: crbugReReplacers,
      }
  );

  // Lookup referenced artifacts functions.
  function LookupReferencedIssues(issueRefs, token, componentName) {
    return new Promise((resolve, reject) => {
      const message = {
        trace: {token: token},
        issue_refs: issueRefs,
      };
      const listReferencedIssues =  window.prpcClient.call(
          'monorail.Issues', 'ListReferencedIssues', message
      );
      return listReferencedIssues.then(response => {
        resolve({'componentName': componentName, 'existingRefs': response});
      });
    });
  }

  // Extract referenced artifacts info functions.
  function ExtractProjectAndIssueIds(match, default_project_name='chromium') {
    const groups = match.groups;
    const project_name = groups.project_name ? groups.project_name : default_project_name;
    return {project_name: project_name, local_id: groups.local_id};
  }

  // Replace plain text references with links functions.
  function ReplaceIssueRef(match, components, default_project_name='chromium') {
    const projectName = match.groups.project_name || default_project_name;
    const localId = match.groups.local_id;
    if (components.openRefs && components.openRefs.length) {
      const openRef = components.openRefs.find(ref => {
          return (ref.localId == localId) && (ref.projectName === projectName);
      });
      if (openRef) {
        return createIssueRefRun(projectName, localId, false, match[0]);
      }
    }
    if (components.closedRefs && components.closedRefs.length) {
      const closedRef = components.closedRefs.find(ref => {
	  return (ref.localId == localId) && (ref.projectName == projectName);
      });
      if (closedRef) {
        return createIssueRefRun(projectName, localId, true, match[0]);
      }
    }
    return {content: match[0]};
  }

  // Create custom textrun functions.
  function createIssueRefRun(projectName, localId, isClosed, content) {
    return {
      tag: 'a',
      css: isClosed ? 'strikeThrough' : '',
      href: `/p/${projectName}/issues/detail?id=${localId}`,
      content: content,
    };
  }

  window.__autolink = window.__autolink || {};
  Object.assign(window.__autolink, {Components, createIssueRefRun});

})(window);
