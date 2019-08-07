// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {connectStore} from 'elements/reducers/base.js';
import * as project from 'elements/reducers/project.js';
import {extractGridData, makeGridCellKey} from './extract-grid-data.js';
import {EMPTY_FIELD_VALUE} from 'elements/shared/issue-fields.js';
import {issueRefToUrl} from '../../shared/converters.js';
import './mr-grid-tile.js';
import qs from 'qs';

export class MrGrid extends connectStore(LitElement) {
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
              ${this.groupedIssues.has(makeGridCellKey(xHeading, yHeading)) ? html`
                <td>
                  ${this.renderCellMode(this.cellMode, xHeading, yHeading)}
                </td>
              `: html`
                <td></td>
              `}
            `)}
          </tr>
        `)}
      </table>
    `;
  }

  renderCellMode(cellMode, xHeading, yHeading) {
    cellMode = cellMode.toLowerCase();
    const cellHeading = makeGridCellKey(xHeading, yHeading);
    if (cellMode === 'ids') {
      return html`
        ${this.groupedIssues.get(cellHeading).map((issue) => html`
          <mr-issue-link
            .projectName=${this.projectName}
            .issue=${issue}
            .text=${issue.localId}
            .queryParams=${this.queryParams}
          ></mr-issue-link>
        `)}
      `;
    } else if (cellMode === 'counts') {
      const itemCount =
        this.groupedIssues.get(cellHeading).length;
      if (itemCount === 1) {
        const issue = this.groupedIssues.get(cellHeading)[0];
        return html`
          <a href=${issueRefToUrl(issue, this.queryParams)} class="counts">
            1 item
          </a>
        `;
      } else {
        return html`
          <a href=${this.formatCountsURL(xHeading, yHeading)} class="counts">
            ${itemCount} items
          </a>
        `;
      }
    } else if (cellMode === 'tiles') {
      return html`
        ${this.groupedIssues.get(cellHeading).map((issue) => html`
          <mr-grid-tile
            .issue=${issue}
            .queryParams=${this.queryParams}
          ></mr-grid-tile>`)}
      `;
    }
  }

  formatCountsURL(xHeading, yHeading) {
    let url = 'list?';
    const params = Object.assign({}, this.queryParams);
    params.mode = '';

    params.q = this.addHeadingsToSearch(params.q, xHeading, this.xAttr);
    params.q = this.addHeadingsToSearch(params.q, yHeading, this.yAttr);

    url += qs.stringify(params);

    return url;
  }

  addHeadingsToSearch(params, heading, attr) {
    if (attr && attr !== 'None') {
      if (heading === EMPTY_FIELD_VALUE) {
        params += ' -has:' + attr;
      // The following two cases are to handle grouping issues by Blocked
      } else if (heading === 'No') {
        params += ' -is:' + attr;
      } else if (heading === 'Yes') {
        params += ' is:' + attr;
      } else {
        params += ' ' + attr + '=' + heading;
      }
    }
    return params;
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
      queryParams: {type: Object},
      projectName: {type: String},
      _fieldDefMap: {type: Object},
      _labelPrefixSet: {type: Object},
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
    this._fieldDefMap = new Map();
    this._labelPrefixSet = new Set();
  }

  stateChanged(state) {
    this._fieldDefMap = project.fieldDefMap(state);
    this._labelPrefixSet = project.labelPrefixSet(state);
  }

  updated(changedProperties) {
    if (changedProperties.has('xAttr') || changedProperties.has('yAttr') ||
        changedProperties.has('issues')) {
      const gridData = extractGridData(this.issues, this.xAttr, this.yAttr,
        this.projectName, this._fieldDefMap, this._labelPrefixSet);
      this.xHeadings = gridData.xHeadings;
      this.yHeadings = gridData.yHeadings;
      this.groupedIssues = gridData.sortedIssues;
    }
  }
};
customElements.define('mr-grid', MrGrid);
