// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '../../node_modules/@polymer/polymer/polymer-legacy.js';
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
        href$="[[issueUrl]]"
        title$="[[issue.summary]]"
      >
        Issue <template
          is="dom-if"
          if="[[!_hideProjectName(projectName, issue.projectName)]]"
        >[[issue.projectName]]:</template>[[issue.localId]]</a>
    `;
  }

  static get is() {
    return 'mr-bug-link';
  }

  static get properties() {
    return {
      issue: Object,
      isClosed: {
        type: Boolean,
        reflectToAttribute: true,
      },
      projectName: String,
      issueUrl: {
        type: String,
        computed: '_computeIssueUrl(issue)',
      },
    };
  }

  _hideProjectName(mainProjectName, localProjectName) {
    if (!mainProjectName || !localProjectName) return true;
    return mainProjectName.toLowerCase() === localProjectName.toLowerCase();
  }

  _computeIssueUrl(issue) {
    const issueType = issue.approvalValues ? 'approval' : 'detail';
    return `/p/${issue.projectName}/issues/${issueType}?id=${issue.localId}`;
  }
}
customElements.define(MrBugLink.is, MrBugLink);
