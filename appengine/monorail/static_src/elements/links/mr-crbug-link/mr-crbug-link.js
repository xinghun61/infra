// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

/**
 * `<mr-crbug-link>`
 *
 * Displays a crbug short-link to an issue.
 *
 */
export class MrCrbugLink extends PolymerElement {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <style>
        a.material-icons {
          font-size: 20px;
          display: inline-block;
          color: var(--chops-primary-icon-color);
          padding: 0 2px;
          box-sizing: border-box;
          text-decoration: none;
          vertical-align: middle;
        }
      </style>
      <a
        id="bugLink"
        class="material-icons"
        href$="[[_issueUrl]]"
        title="crbug link"
      >link</a>
    `;
  }

  static get is() {
    return 'mr-crbug-link';
  }

  static get properties() {
    return {
      // The issue being viewed. Falls back gracefully if this is only a ref.
      issue: Object,
      _issueUrl: {
        type: String,
        computed: '_computeIssueUrl(issue)',
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      issue: state.issue,
    };
  }

  _getHost() {
    // This function allows us to mock the host in unit testing.
    return document.location.host;
  }

  _computeIssueUrl(issue) {
    if (this._getHost() === 'bugs.chromium.org') {
      const projectPart = (
        issue.projectName == 'chromium' ? '' : issue.projectName + '/');
      return `https://crbug.com/${projectPart}${issue.localId}`;
    }
    const issueType = issue.approvalValues ? 'approval' : 'detail';
    return `/p/${issue.projectName}/issues/${issueType}?id=${issue.localId}`;
  }
}
customElements.define(MrCrbugLink.is, MrCrbugLink);
