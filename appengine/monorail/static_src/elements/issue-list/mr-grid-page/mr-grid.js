// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {extractGridData} from './extract-grid-data.js';

export class MrGrid extends LitElement {
  render() {
    return html`
      <table>
        <tr>
          <th>&nbsp</th>
          ${this.xHeadings.map((heading) => html`
              <th>${heading}</th>`)}
        </tr>
        ${this.yHeadings.map((yHeading) => html`
          <tr>
            <th>${yHeading}</th>
            ${this.xHeadings.map((xHeading) => html`
              ${this.groupedIssues.has(xHeading + '-' + yHeading) ? html`
                <td>${this.groupedIssues.get(
                  xHeading + '-' + yHeading).map((issue) => html`
                    <mr-issue-link
                      .projectName=${this.projectName}
                      .issue=${issue}
                      .text=${issue.localId}
                      .queryParams=${this.queryParams}
                    ></mr-issue-link>
                `)} </td>`: html`<td></td>
              `}
            `)}
          </tr>
        `)}
      </table>
    `;
  }

  static get properties() {
    return {
      xAttr: {type: String},
      yAttr: {type: String},
      xHeadings: {type: Array},
      yHeadings: {type: Array},
      issues: {type: Array},
      cellMode: {type: String},
      groupedIssues: {type: Map},
    };
  }

  static get styles() {
    return css`
      table {
        border-collapse: collapse;
        margin: 20px 1%;
        width: 98%;
        text-align: left;
      }
      th {
        border: 1px solid white;
        padding: 5px;
        background-color: var(--chops-table-header-bg);
      }
      td {
        border: var(--chops-table-divider);
        background-color: white;
      }
      td .issue-link {
        margin-right: 0.6em;
        margin-left: 0.6em;
      }
    `;
  }

  constructor() {
    super();
    this.xHeadings = [];
    this.yHeadings = [];
    this.groupedIssues = new Map();
  }

  updated(changedProperties) {
    if (changedProperties.has('xAttr') || changedProperties.has('yAttr') ||
        changedProperties.has('issues')) {
      const gridData = extractGridData(this.issues, this.xAttr, this.yAttr);
      this.xHeadings = gridData.xHeadings;
      this.yHeadings = gridData.yHeadings;
      this.groupedIssues = gridData.sortedIssues;
    }
  }
};
customElements.define('mr-grid', MrGrid);
