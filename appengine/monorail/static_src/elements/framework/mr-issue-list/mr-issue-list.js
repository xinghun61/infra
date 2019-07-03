// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import 'elements/framework/links/mr-issue-link/mr-issue-link.js';


export class MrIssueList extends LitElement {
  static get styles() {
    return css`
      :host {
        display: table;
        width: 100%;
        size: var(--chops-main-font-size);
      }
      td, th {
        padding: 0.25em 8px;
        border-bottom: var(--chops-normal-border);
      }
      td {
        text-overflow: ellipsis;
      }
      th {
        background: var(--chops-table-header-bg);
        font-weight: bold;
        text-decoration: none;
        white-space: nowrap;
        color: var(--chops-link-color);
        text-align: left;
      }
    `;
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <tbody>
        <tr>
          <th></th>
          ${this.columns.map((column) => html`
            <th>${column}</th>
          `)}
        </tr>
        ${this.issues.map((issue, i) => this._renderRow(issue, i))}
      </tbody>
    `;
  }

  _renderRow(issue, i) {
    const draggable = this.rerankEnabled && this.rerankEnabled(issue);
    return html`
      <tr
        class=${i === this.srcIndex ? 'dragged' : ''}
        draggable=${draggable}
        data-index=${i}
        @dragstart=${this._dragstart}
        @dragend=${this._dragend}
        @dragover=${this._dragover}
        @drop=${this._dragdrop}
      >
        <td>
          ${draggable ? html`
            <i class="material-icons draggable">drag_indicator</i>
          ` : ''}
          ${this.selectionEnabled ? html`
            <input type="checkbox" aria-label="Select Issue ${issue.localId}" />
          ` : ''}
        </td>

        ${this.columns.map((column) => html`
          <td class="col-${column.toLowerCase()}">
            ${this._renderCell(column, issue)}
          </td>
        `)}
      </tr>
    `;
  }

  _renderCell(column, issue) {
    switch (column) {
      case 'Issue':
        return html`
           <mr-issue-link
            .projectName=${this.projectName}
            .issue=${issue}
          ></mr-issue-link>
        `;
      case 'Summary':
        return issue.summary;
      default:
        return '';
    }
  }

  static get properties() {
    return {
      columns: {type: Array},
      /**
       * List of issues to display.
       */
      issues: {type: Array},
      /**
       * A function that takes in an issue and computes whether
       * reranking should be enabled for a given issue.
       */
      rerankEnabled: {type: Object},
      /**
       * Whether issues should be selectable or not.
       */
      selectionEnabled: {type: Boolean},
      /**
       * Attribute set to make host element into a table. Do not override.
       */
      role: {
        type: String,
        reflect: true,
      },
    };
  };

  constructor() {
    super();
    this.issues = [];
    this.selectionEnabled = false;
    this.role = 'table';

    this.columns = ['Issue', 'Summary'];
  };
};

customElements.define('mr-issue-list', MrIssueList);
