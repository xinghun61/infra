// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.


(function(window) {
  'use strict';

  const CRBUG_LINK_STR = '(?<prefix>\\b(https?:\/\/)?crbug\\.com\/)((?<projectName>\\b[-a-z0-9]+)(?<separator>\/))?(?<localId>\\d+)\\b(?<anchor>\\#c[0-9]+)?';
  const ISSUE_TRACKER_STR = '(?<prefix>\\b(issues?|bugs?)[ \\t]*(:|=)?)([ \\t]*(?<projectName>\\b[-a-z0-9]+[:\\#])?(?<numberSign>\\#?)(?<localId>\\d+)\\b(,?[ \\t]*(and|or)?)?)+';
  const PROJECT_LOCALID_STR = '([ \\t]*(?<projectName>\\b[-a-z0-9]+[:\\#])?(?<numberSign>\\#?)(?<localId>\\d+))';
  const IMPLIED_EMAIL_STR = '\\b[a-z]((-|\\.)?[a-z0-9])+@[a-z]((-|\\.)?[a-z0-9])+\\.(com|net|org|edu)\\b';

  const Components = new Map();
  Components.set(
      '01-tracker-crbug',
      {
        lookup: LookupReferencedIssues,
        extractRefs: ExtractCrbugProjectAndIssueIds,
        replacers: [{re: CRBUG_LINK_STR, replacerFunc: ReplaceCrbugIssueRef}],
      }
  );
  Components.set(
      '02-tracker-regular',
      {
        lookup: LookupReferencedIssues,
        extractRefs: ExtractTrackerProjectAndIssueIds,
        replacers: [{re: ISSUE_TRACKER_STR, replacerFunc: ReplaceTrackerIssueRef}],
      }
  );
  Components.set(
      '03-user-emails',
      {
        lookup: LookupReferencedUsers,
        extractRefs: (match, _defaultProjectName) => { return match[0]; },
        replacers: [{re: IMPLIED_EMAIL_STR, replacerFunc: ReplaceUserRef}],
      }
  )

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

  function LookupReferencedUsers(emails, token, componentName) {
    // TODO(jojwang): monorail:4033, implement this.
    return true;
  }

  // Extract referenced artifacts info functions.
  function ExtractCrbugProjectAndIssueIds(match, defaultProjectName='chromium') {
    const groups = match.groups;
    const projectName = groups.projectName || defaultProjectName;
    return {projectName: projectName, localId: groups.localId};
  }

  function ExtractTrackerProjectAndIssueIds(match, defaultProjectName='chromium') {
    const issueRefRE = new RegExp(PROJECT_LOCALID_STR, 'gi');
    let refMatch;
    let refs = [];
    while ((refMatch = issueRefRE.exec(match[0])) !== null) {
      if (refMatch.groups.projectName) {
        defaultProjectName = refMatch.groups.projectName.slice(0, -1);
      }
      refs.push({projectName: defaultProjectName, localId: refMatch.groups.localId});
    }
    return refs;
  }

  // Replace plain text references with links functions.
  function ReplaceIssueRef(stringMatch, projectName, localId, components) {
    if (components.openRefs && components.openRefs.length) {
      const openRef = components.openRefs.find(ref => {
          return (ref.localId == localId) && (ref.projectName === projectName);
      });
      if (openRef) {
        return createIssueRefRun(projectName, localId, false, stringMatch);
      }
    }
    if (components.closedRefs && components.closedRefs.length) {
      const closedRef = components.closedRefs.find(ref => {
        return (ref.localId == localId) &&
            (ref.projectName.toLowerCase() == projectName.toLowerCase());
      });
      if (closedRef) {
        return createIssueRefRun(projectName, localId, true, stringMatch);
      }
    }
    return {content: stringMatch};
  }

  function ReplaceCrbugIssueRef(match, components, defaultProjectName='chromium') {
    const projectName = match.groups.projectName || defaultProjectName;
    const localId = match.groups.localId;
    return ReplaceIssueRef(match[0], projectName, localId, components);
  }

  function ReplaceTrackerIssueRef(match, components, defaultProjectName='chromium') {
    const issueRefRE = new RegExp(PROJECT_LOCALID_STR, 'gi');
    let textRuns = [];
    let refMatch;
    while ((refMatch = issueRefRE.exec(match[0])) !== null) {
      if (refMatch.groups.projectName) {
        defaultProjectName = refMatch.groups.projectName.slice(0, -1);
      }
      textRuns.push(ReplaceIssueRef(refMatch[0].trim(), defaultProjectName, refMatch.groups.localId, components));
    };
    return textRuns;
  }

  function ReplaceUserRef(match, components, _defaultProjectName) {
    let href;
    let textRun = {content: match[0], tag: 'a'};
    if (components.users && components.users.length) {
      const existingUser = components.users.find(user => {
        return user.email.toLowerCase() === match[0].toLowerCase();
      });
      if (existingUser) {
        textRun.href = `/u/${match[0]}`;
        return textRun;
      }
    }
    textRun.href = `mailto:${match[0]}`;
    return textRun;
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
