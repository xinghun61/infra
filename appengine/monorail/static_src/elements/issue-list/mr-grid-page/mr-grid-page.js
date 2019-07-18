// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// TODO(juliacordero): Handle pRPC errors with a FE page

import {LitElement, html} from 'lit-element';
import {store, connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import * as project from 'elements/reducers/project.js';
import 'elements/framework/links/mr-issue-link/mr-issue-link.js';
import './mr-grid-controls.js';
import './mr-grid.js';


export class MrGridPage extends connectStore(LitElement) {
  render() {
    return html`
      <div id="grid-area">
        <mr-grid-controls
          .queryParams=${this.queryParams}
          .customIssueProperties=${this.fields}
          .issueCount=${this.issues.length}>
        </mr-grid-controls>
        <br>
        <mr-grid
          .issues=${this.issues}
          .xAttr=${this.queryParams.x}
          .yAttr=${this.queryParams.y}
          .cellMode=${this.queryParams.cells ? this.queryParams.cells : 'tiles'}
          .queryParams=${this.queryParams}
          .projectName=${this.projectName}
        ></mr-grid>
      </div>
    `;
  }

  static get properties() {
    return {
      projectName: {type: String},
      issueEntryUrl: {type: String},
      queryParams: {type: Object},
      userDisplayName: {type: String},
      issues: {type: Array},
      fields: {type: Array},
    };
  };

  constructor() {
    super();
    this.issues = [];
    this.fields = [];
  };

  updated(changedProperties) {
    if (changedProperties.has('projectName') ||
        changedProperties.has('queryParams')) {
      store.dispatch(issue.fetchIssueList(this.queryParams, this.projectName));
      store.dispatch(project.fetchFieldsList(this.projectName));
    }
  }

  stateChanged(state) {
    this.issues = (issue.issueList(state) || []);
    this.fields = (project.fieldsList(state) || []);
  }
};
customElements.define('mr-grid-page', MrGridPage);
