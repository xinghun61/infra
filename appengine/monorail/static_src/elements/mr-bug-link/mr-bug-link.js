// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

/**
 * `<mr-bug-link>`
 *
 * Displays a link to a bug.
 *
 */
export class MrBugLink extends PolymerElement {
  static get template() {
    return html`
      <style>
        :host([is-closed]) a {
          text-decoration: line-through;
        }
      </style>
      <a
        id="bugLink"
        href$="[[_issueUrl]]"
        title$="[[issue.summary]]"
      >[[_linkText]]</a>
    `;
  }

  static get is() {
    return 'mr-bug-link';
  }

  static get properties() {
    return {
      issue: Object,
      text: String,
      isClosed: {
        type: Boolean,
        reflectToAttribute: true,
      },
      projectName: String,
      _issueUrl: {
        type: String,
        computed: '_computeIssueUrl(issue)',
      },
      _linkText: {
        type: String,
        computed: '_computeLinkText(projectName, issue, text)',
      },
    };
  }

  _showProjectName(mainProjectName, localProjectName) {
    if (!mainProjectName || !localProjectName) return false;
    return mainProjectName.toLowerCase() !== localProjectName.toLowerCase();
  }

  _computeIssueUrl(issue) {
    const issueType = issue.approvalValues ? 'approval' : 'detail';
    return `/p/${issue.projectName}/issues/${issueType}?id=${issue.localId}`;
  }

  _computeLinkText(projectName, issue, text) {
    if (text) return text;
    const projectNamePart =
      this._showProjectName(projectName, issue.projectName)
      ? `${issue.projectName}:` : '';
    return `Issue ${projectNamePart}${issue.localId}`;
  }
}
customElements.define(MrBugLink.is, MrBugLink);
