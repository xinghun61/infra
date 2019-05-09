// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import * as issue from 'elements/reducers/issue.js';

/**
 * `<mr-crbug-link>`
 *
 * Displays a crbug short-link to an issue.
 *
 */
export class MrCrbugLink extends LitElement {
  static get styles() {
    return css`
      a.material-icons {
        font-size: var(--chops-icon-font-size);
        display: inline-block;
        color: var(--chops-primary-icon-color);
        padding: 0 2px;
        box-sizing: border-box;
        text-decoration: none;
        vertical-align: middle;
      }
    `;
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <a
        id="bugLink"
        class="material-icons"
        href=${this._issueUrl}
        title="crbug link"
      >link</a>
    `;
  }

  static get properties() {
    return {
      // The issue being viewed. Falls back gracefully if this is only a ref.
      issue: {type: Object},
    };
  }

  get _issueUrl() {
    const issue = this.issue;
    if (!issue) return '';
    if (this._getHost() === 'bugs.chromium.org') {
      const projectPart = (
        issue.projectName == 'chromium' ? '' : issue.projectName + '/');
      return `https://crbug.com/${projectPart}${issue.localId}`;
    }
    const issueType = issue.approvalValues ? 'approval' : 'detail';
    return `/p/${issue.projectName}/issues/${issueType}?id=${issue.localId}`;
  }

  _getHost() {
    // This function allows us to mock the host in unit testing.
    return document.location.host;
  }
}
customElements.define('mr-crbug-link', MrCrbugLink);
