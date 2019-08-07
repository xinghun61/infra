// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// TODO(juliacordero): Handle pRPC errors with a FE page

import {LitElement, html, css} from 'lit-element';
import {store, connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import 'elements/framework/links/mr-issue-link/mr-issue-link.js';
import './mr-grid-controls.js';
import './mr-grid.js';

export class MrGridPage extends connectStore(LitElement) {
  render() {
    const doneLoading = this.progress === 1;
    return html`
      <div id="grid-area">
        <mr-grid-controls
          .queryParams=${this.queryParams}
          .issueCount=${this.issues.length}>
        </mr-grid-controls>
        <progress
          title="${Math.round(this.progress * 100)}%"
          value=${this.progress}
          ?hidden=${doneLoading}
        ></progress>
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
      fetchingIssueList: {type: Boolean},
      progress: {type: Number},
    };
  };

  constructor() {
    super();
    this.issues = [];
    this.progress = 0;
    this.queryParams = {y: 'None', x: 'None'};
  };

  updated(changedProperties) {
    if (changedProperties.has('userDisplayName')) {
      store.dispatch(issue.fetchStarredIssues());
    }
    // TODO(zosha): Abort sets of calls to ListIssues when
    // queryParams.q is changed.
    if (changedProperties.has('projectName')) {
      store.dispatch(issue.fetchIssueList(this.queryParams,
        this.projectName, {maxItems: 500}, 12));
    } else if (changedProperties.has('queryParams').q) {
      const oldParams = changedProperties.get('queryParams');
      if (oldParams.q !== this.queryParams.q) {
        store.dispatch(issue.fetchIssueList(this.queryParams,
          this.projectName, {maxItems: 500}, 12));
      }
    }
  }

  stateChanged(state) {
    this.issues = (issue.issueList(state) || []);
    this.progress = (issue.issueListProgress(state) || 0);
  }

  static get styles() {
    return css `
      progress {
        background-color: white;
        border: 1px solid var(--chops-blue-700);
        width: 25%;
        visibility: visible;
        margin-left: 1.5em;
      }
      ::-webkit-progress-bar {
        background-color: white;
      }
      progress::-webkit-progress-value {
        transition: width 1s;
        background-color: var(--chops-blue-700);
      }
    `;
  }
};
customElements.define('mr-grid-page', MrGridPage);
