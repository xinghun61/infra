// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html} from 'lit-element';
import {prpcClient} from 'prpc-client-instance.js';
import 'elements/framework/links/mr-issue-link/mr-issue-link.js';

export class MrGridPage extends LitElement {
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

  static get styles() {
    // define css file.
  };

  updated(changedProperties) {
    if (changedProperties.has('projectName') ||
        changedProperties.has('queryParams')) {
      this._fetchListIssues(this.queryParams, this.projectName);
    }
  }

  async _fetchListIssues(queryParams, projectName) {
    // TODO(juliacordero): call the API using Redux
    if (queryParams && projectName) {
      const issues = await prpcClient.call(
        'monorail.Issues', 'ListIssues', {
          query: queryParams.q,
          cannedQuery: queryParams.can,
          projectNames: [projectName],
          pagination: {},
          groupBySpec: queryParams.groupby,
          sortSpec: queryParams.sort,
        }
      );
      this.issues = issues.issues;
    }
  };
}
customElements.define('mr-grid-page', MrGridPage);
