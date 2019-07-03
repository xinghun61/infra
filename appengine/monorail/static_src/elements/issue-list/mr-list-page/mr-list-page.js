// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {store, connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import 'elements/framework/mr-issue-list/mr-issue-list.js';


export class MrListPage extends connectStore(LitElement) {
  static get styles() {
    return css`
      :host {
        display: block;
        box-sizing: border-box;
        width: 100%;
        padding: 0.5em 8px;
      }
      .container-no-issues {
        width: 100%;
        padding: 0 8px;
        font-size: var(--chops-large-font-size);
      }
    `;
  }

  render() {
    if (this.fetchingIssueList) {
      return html`
        <div class="container-no-issues">
          Loading...
        </div>
      `;
    }
    return html`
      <mr-issue-list
        .issues=${this.issues}
        .projectName=${this.projectName}
      ></mr-issue-list>
    `;
  }

  static get properties() {
    return {
      issues: {type: Array},
      queryParams: {type: Object},
      projectName: {type: String},
      fetchingIssueList: {type: Boolean},
    };
  };

  constructor() {
    super();
    this.issues = [];
    this.fetchingIssueList = false;
  };

  updated(changedProperties) {
    if (changedProperties.has('projectName') ||
        changedProperties.has('queryParams')) {
      store.dispatch(issue.fetchIssueList(this.queryParams, this.projectName));
    }
  }

  stateChanged(state) {
    this.issues = (issue.issueList(state) || []);
    this.fetchingIssueList = issue.requests(state).fetchIssueList.requesting;
  }
};
customElements.define('mr-list-page', MrListPage);
