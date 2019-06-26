// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html} from 'lit-element';
import {store, connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import 'elements/framework/links/mr-issue-link/mr-issue-link.js';


export class MrGridPage extends connectStore(LitElement) {
  render() {
    return html`
      ${this.issues.map((issue) => html`
        <mr-issue-link
          .projectName=${this.projectName}
          .issue=${issue}
          .text=${issue.localId}
        ></mr-issue-link>`)}
      `;
  }

  static get properties() {
    return {
      projectName: {type: String},
      issueEntryUrl: {type: String},
      queryParams: {type: Object},
      userDisplayName: {type: String},
      issues: {type: Array},
    };
  };

  constructor() {
    super();
    this.issues = [];
  };

  updated(changedProperties) {
    if (changedProperties.has('projectName') ||
        changedProperties.has('queryParams')) {
      store.dispatch(issue.fetchIssueList(this.queryParams, this.projectName));
    }
  }

  stateChanged(state) {
    this.issues = (issue.issueList(state) || []);
  }

  static get styles() {
    // define css file.
  };
};
customElements.define('mr-grid-page', MrGridPage);
