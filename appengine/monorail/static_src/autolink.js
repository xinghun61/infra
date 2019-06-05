// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';
import {prpcClient} from 'prpc-client-instance.js';

// When crbug links don't specify a project, the default project is Chromium.
const CRBUG_DEFAULT_PROJECT = 'chromium';
const CRBUG_LINK_RE = /(\b(https?:\/\/)?crbug\.com\/)((\b[-a-z0-9]+)(\/))?(\d+)\b(\#c[0-9]+)?/gi;
const CRBUG_LINK_RE_PROJECT_GROUP = 4;
const CRBUG_LINK_RE_ID_GROUP = 6;
const CRBUG_LINK_RE_COMMENT_GROUP = 7;
const ISSUE_TRACKER_RE = /(\b(issues?|bugs?)[ \t]*(:|=|\b))([ \t]*((\b[-a-z0-9]+)[:\#])?(\#?)(\d+)\b(,?[ \t]*(and|or)?)?)+/gi;
const PROJECT_LOCALID_RE = /((\b(issue|bug)[ \t]*(:|=)?[ \t]*)?((\b[-a-z0-9]+)[:\#])?(\#?)(\d+))/gi;
const PROJECT_COMMENT_RE = /((\b(comment)[ \t]*(:|=)?[ \t]*)(\#?)(\d+))/gi;
const PROJECT_COMMENT_ABBR_RE = /((\B(\#)(c))(\d+))/gi;
const PROJECT_LOCALID_RE_PROJECT_GROUP = 6;
const PROJECT_LOCALID_RE_ID_GROUP = 8;
const IMPLIED_EMAIL_RE = /\b[a-z]((-|\.)?[a-z0-9])+@[a-z]((-|\.)?[a-z0-9])+\.(com|net|org|edu)\b/gi;
// TODO(zhangtiff): Replace (^|[^-/._]) with (?<![-/._]) on the 3 Regexes below
// once Firefox supports lookaheads.
const SHORT_LINK_RE = /(^|[^-\/._])\b(https?:\/\/|ftp:\/\/|mailto:)?(go|g|shortn|who|teams)\/([^\s<]+)/gi;
const NUMERIC_SHORT_LINK_RE = /(^|[^-\/._])\b(https?:\/\/|ftp:\/\/)?(b|t|o|omg|cl|cr)\/([0-9]+)/gi;
const IMPLIED_LINK_RE = /(^|[^-\/._])\b[a-z]((-|\.)?[a-z0-9])+\.(com|net|org|edu)\b(\/[^\s<]*)?/gi;
const IS_LINK_RE = /()\b(https?:\/\/|ftp:\/\/|mailto:)([^\s<]+)/gi;
const GIT_HASH_RE = /\b(r(evision\s+#?)?)?([a-f0-9]{40})\b/gi;
const SVN_REF_RE = /\b(r(evision\s+#?)?)([0-9]{4,7})\b/gi;
const NEW_LINE_REGEX = /^(\r\n?|\n)$/;
const NEW_LINE_OR_BOLD_REGEX = /(<b>[^<\n]+<\/b>)|(\r\n?|\n)/;
// The revNum is in the same position for the above two Regexes. The
// extraction function uses this similar format to allow switching out
// Regexes easily, so be careful about changing GIT_HASH_RE and SVN_HASH_RE.
const REV_NUM_GROUP = 3;
const LINK_TRAILING_CHARS = [
  [null, ':'],
  [null, '.'],
  [null, ','],
  [null, '>'],
  ['(', ')'],
  ['[', ']'],
  ['{', '}'],
  ['\'', '\''],
  ['"', '"'],
];
const GOOG_SHORT_LINK_RE = /^(b|t|o|omg|cl|cr|go|g|shortn|who|teams)\/.*/gi;

const Components = new Map();
Components.set(
  '01-tracker-crbug',
  {
    lookup: LookupReferencedIssues,
    extractRefs: ExtractCrbugProjectAndIssueIds,
    refRegs: [CRBUG_LINK_RE],
    replacer: ReplaceCrbugIssueRef,

  }
);
Components.set(
  '02-full-urls',
  {
    lookup: null,
    extractRefs: (match, _currentProjectName) => {
      return [match[0]];
    },
    refRegs: [IS_LINK_RE],
    replacer: ReplaceLinkRef,
  }
);
Components.set(
  '03-user-emails',
  {
    lookup: LookupReferencedUsers,
    extractRefs: (match, _currentProjectName) => {
      return [match[0]];
    },
    refRegs: [IMPLIED_EMAIL_RE],
    replacer: ReplaceUserRef,
  }
);
Components.set(
  '04-tracker-regular',
  {
    lookup: LookupReferencedIssues,
    extractRefs: ExtractTrackerProjectAndIssueIds,
    refRegs: [ISSUE_TRACKER_RE],
    replacer: ReplaceTrackerIssueRef,
  }
);
Components.set(
  '05-linkify-shorthand',
  {
    lookup: null,
    extractRefs: (match, _currentProjectName) => {
      return [match[0]];
    },
    refRegs: [
      SHORT_LINK_RE,
      NUMERIC_SHORT_LINK_RE,
      IMPLIED_LINK_RE,
    ],
    replacer: ReplaceLinkRef,
  }
);
Components.set(
  '06-versioncontrol',
  {
    lookup: null,
    extractRefs: (match, _currentProjectName) => {
      return [match[0]];
    },
    refRegs: [GIT_HASH_RE, SVN_REF_RE],
    replacer: ReplaceRevisionRef,
  }
);
Components.set(
  '07-comment',
  {
    lookup: null,
    extractRefs: null,
    refRegs: [PROJECT_COMMENT_RE],
    replacer: ReplaceCommentRef,
  }
);
Components.set(
  '08-abbreviatedcomment',
  {
    lookup: null,
    extractRefs: null,
    refRegs: [PROJECT_COMMENT_ABBR_RE],
    replacer: ReplaceAbbrCommentRef,
  }
);

// Lookup referenced artifacts functions.
function LookupReferencedIssues(issueRefs, componentName) {
  return new Promise((resolve, reject) => {
    issueRefs = issueRefs.filter(
      ({projectName, localId}) => projectName && parseInt(localId));
    const listReferencedIssues = prpcClient.call(
      'monorail.Issues', 'ListReferencedIssues', {issueRefs});
    return listReferencedIssues.then((response) => {
      resolve({'componentName': componentName, 'existingRefs': response});
    });
  });
}

function LookupReferencedUsers(emails, componentName) {
  return new Promise((resolve, reject) => {
    const userRefs = emails.map((displayName) => {
      return {displayName};
    });
    const listReferencedUsers = prpcClient.call(
      'monorail.Users', 'ListReferencedUsers', {userRefs});
    return listReferencedUsers.then((response) => {
      resolve({'componentName': componentName, 'existingRefs': response});
    });
  });
}

// Extract referenced artifacts info functions.
function ExtractCrbugProjectAndIssueIds(match, _currentProjectName) {
  // When crbug links don't specify a project, the default project is Chromium.
  const projectName = match[CRBUG_LINK_RE_PROJECT_GROUP] || CRBUG_DEFAULT_PROJECT;
  const localId = match[CRBUG_LINK_RE_ID_GROUP];
  return [{projectName: projectName, localId: localId}];
}

function ExtractTrackerProjectAndIssueIds(match, currentProjectName) {
  const issueRefRE = PROJECT_LOCALID_RE;
  let refMatch;
  let refs = [];
  while ((refMatch = issueRefRE.exec(match[0])) !== null) {
    if (refMatch[PROJECT_LOCALID_RE_PROJECT_GROUP]) {
      currentProjectName = refMatch[PROJECT_LOCALID_RE_PROJECT_GROUP];
    }
    refs.push({
      projectName: currentProjectName,
      localId: refMatch[PROJECT_LOCALID_RE_ID_GROUP],
    });
  }
  return refs;
}

// Replace plain text references with links functions.
function ReplaceIssueRef(stringMatch, projectName, localId, components,
  commentId) {
  if (components.openRefs && components.openRefs.length) {
    const openRef = components.openRefs.find((ref) => {
      return ref.localId && ref.projectName && (ref.localId == localId) &&
          (ref.projectName.toLowerCase() === projectName.toLowerCase());
    });
    if (openRef) {
      return createIssueRefRun(
        projectName, localId, openRef.summary, false, stringMatch, commentId);
    }
  }
  if (components.closedRefs && components.closedRefs.length) {
    const closedRef = components.closedRefs.find((ref) => {
      return ref.localId && ref.projectName && (ref.localId == localId) &&
          (ref.projectName.toLowerCase() === projectName.toLowerCase());
    });
    if (closedRef) {
      return createIssueRefRun(
        projectName, localId, closedRef.summary, true, stringMatch, commentId);
    }
  }
  return {content: stringMatch};
}

function ReplaceCrbugIssueRef(match, components, _currentProjectName) {
  components = components || {};
  // When crbug links don't specify a project, the default project is Chromium.
  const projectName =
    match[CRBUG_LINK_RE_PROJECT_GROUP] || CRBUG_DEFAULT_PROJECT;
  const localId = match[CRBUG_LINK_RE_ID_GROUP];
  let commentId = '';
  if (match[CRBUG_LINK_RE_COMMENT_GROUP] !== undefined) {
    commentId = match[CRBUG_LINK_RE_COMMENT_GROUP];
  }
  return [ReplaceIssueRef(match[0], projectName, localId, components,
    commentId)];
}

function ReplaceTrackerIssueRef(match, components, currentProjectName) {
  components = components || {};
  const issueRefRE = PROJECT_LOCALID_RE;
  const commentId = '';
  let textRuns = [];
  let refMatch;
  let pos = 0;
  while ((refMatch = issueRefRE.exec(match[0])) !== null) {
    if (refMatch.index > pos) {
      // Create textrun for content between previous and current match.
      textRuns.push({content: match[0].slice(pos, refMatch.index)});
    }
    if (refMatch[PROJECT_LOCALID_RE_PROJECT_GROUP]) {
      currentProjectName = refMatch[PROJECT_LOCALID_RE_PROJECT_GROUP];
    }
    textRuns.push(ReplaceIssueRef(
      refMatch[0], currentProjectName,
      refMatch[PROJECT_LOCALID_RE_ID_GROUP], components, commentId));
    pos = refMatch.index + refMatch[0].length;
  }
  if (match[0].slice(pos) !== '') {
    textRuns.push({content: match[0].slice(pos)});
  }
  return textRuns;
}

function ReplaceUserRef(match, components, _currentProjectName) {
  components = components || {};
  const textRun = {content: match[0], tag: 'a'};
  if (components.users && components.users.length) {
    const existingUser = components.users.find((user) => {
      return user.email.toLowerCase() === match[0].toLowerCase();
    });
    if (existingUser) {
      textRun.href = `/u/${match[0]}`;
      return [textRun];
    }
  }
  textRun.href = `mailto:${match[0]}`;
  return [textRun];
}

function ReplaceCommentRef(match) {
  const textRun = {content: match[0], tag: 'a', href: '#c' + match[6]};
  return [textRun];
}

function ReplaceAbbrCommentRef(match) {
  const textRun = {content: match[0], tag: 'a', href: '#c' + match[5]};
  return [textRun];
}

function ReplaceLinkRef(match, _componets, _currentProjectName) {
  const textRuns = [];
  let content = match[0];
  let trailing = '';
  if (match[1]) {
    textRuns.push({content: match[1]});
    content = content.slice(match[1].length);
  }
  LINK_TRAILING_CHARS.forEach(([begin, end]) => {
    if (content.endsWith(end)) {
      if (!begin || !content.slice(0, -end.length).includes(begin)) {
        trailing = end + trailing;
        content = content.slice(0, -end.length);
      }
    }
  });
  let href = content;
  let lowerHref = href.toLowerCase();
  if (!lowerHref.startsWith('http') && !lowerHref.startsWith('ftp') &&
      !lowerHref.startsWith('mailto')) {
    // Prepend google-internal short links with http to
    // prevent HTTPS error interstitial.
    // SHORT_LINK_RE should not be used here as it might be
    // in the middle of another match() process in an outer loop.
    if (GOOG_SHORT_LINK_RE.test(lowerHref)) {
      href = 'http://' + href;
    } else {
      href = 'https://' + href;
    }
    GOOG_SHORT_LINK_RE.lastIndex = 0;
  }
  textRuns.push({content: content, tag: 'a', href: href});
  if (trailing.length) {
    textRuns.push({content: trailing});
  }
  return textRuns;
}

function ReplaceRevisionRef(match, _components, _currentProjectName) {
  const content = match[0];
  const href = `https://crrev.com/${match[REV_NUM_GROUP]}`;
  return [{content: content, tag: 'a', href: href}];
}

// Create custom textrun functions.
function createIssueRefRun(projectName, localId, summary, isClosed, content,
  commentId) {
  return {
    tag: 'a',
    css: isClosed ? 'strike-through' : '',
    href: `/p/${projectName}/issues/detail?id=${localId}${commentId}`,
    title: summary || '',
    content: content,
  };
}

function getReferencedArtifacts(comments, currentProjectName) {
  return new Promise((resolve, reject) => {
    let fetchPromises = [];
    Components.forEach(({lookup, extractRefs, refRegs, replacer}, componentName) => {
      if (lookup !== null) {
        let refs = [];
        refRegs.forEach((re) => {
          let match;
          comments.forEach((comment) => {
            while ((match = re.exec(comment.content)) !== null) {
              refs.push(...extractRefs(match, currentProjectName));
            };
          });
        });
        if (refs.length) {
          fetchPromises.push(lookup(refs, componentName));
        }
      }
    });
    resolve(Promise.all(fetchPromises));
  });
}

function markupAutolinks(plainString, componentRefs, currentProjectName) {
  plainString = plainString || '';
  const chunks = plainString.trim().split(NEW_LINE_OR_BOLD_REGEX);
  let textRuns = [];
  chunks.filter(Boolean).forEach((chunk) => {
    if (chunk.match(NEW_LINE_REGEX)) {
      textRuns.push({tag: 'br'});
    } else if (chunk.startsWith('<b>') && chunk.endsWith('</b>')) {
      textRuns.push({content: chunk.slice(3, -4), tag: 'b'});
    } else {
      textRuns.push(...autolinkChunk(chunk, componentRefs, currentProjectName));
    }
  });
  return textRuns;
}

function autolinkChunk(chunk, componentRefs, currentProjectName) {
  let textRuns = [{content: chunk}];
  Components.forEach(({refRegs, replacer}, componentName) => {
    refRegs.forEach((re) => {
      textRuns = applyLinks(textRuns, replacer, re,
        componentRefs.get(componentName), currentProjectName);
    });
  });
  return textRuns;
}

function applyLinks(textRuns, replacer, re, existingRefs, currentProjectName) {
  let resultRuns = [];
  textRuns.forEach((textRun) => {
    if (textRun.tag) {
      resultRuns.push(textRun);
    } else {
      const content = textRun.content;
      let pos = 0;
      let match;
      while ((match = re.exec(content)) !== null) {
        if (match.index > pos) {
          // Create textrun for content between previous and current match.
          resultRuns.push({content: content.slice(pos, match.index)});
        }
        resultRuns.push(...replacer(match, existingRefs, currentProjectName));
        pos = match.index + match[0].length;
      }
      if (content.slice(pos) !== '') {
        resultRuns.push({content: content.slice(pos)});
      }
    }
  });
  return resultRuns;
}


export const autolink = {Components, getReferencedArtifacts, markupAutolinks};
