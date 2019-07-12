// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import page from 'page';
import 'elements/framework/links/mr-issue-link/mr-issue-link.js';
import {issueRefToUrl} from 'elements/shared/converters.js';


export class MrIssueList extends LitElement {
  static get styles() {
    return css`
      :host {
        display: table;
        width: 100%;
        font-size: var(--chops-main-font-size);
      }
      input {
        cursor: pointer;
      }
      td {
        padding: 4px 8px;
        text-overflow: ellipsis;
        border-bottom: var(--chops-normal-border);
        cursor: pointer;
      }
      td.ignore-navigation {
        cursor: default;
      }
      th {
        padding: 3px 8px;
        background: var(--chops-table-header-bg);
        font-weight: bold;
        text-decoration: none;
        white-space: nowrap;
        color: var(--chops-link-color);
        text-align: left;
      }
      tr[selected] {
        background: var(--chops-selected-bg);
      }

      @media (min-width: 1024px) {
        .first-row th {
          position: sticky;
          top: var(--monorail-header-height);
          z-index: 10;
        }
      }
    `;
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <tbody>
        <tr class="first-row">
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
    const rowSelected = this._selectedIssues[i];
    return html`
      <tr
        class=${i === this.srcIndex ? 'dragged' : ''}
        ?selected=${rowSelected}
        draggable=${draggable}
        data-index=${i}
        @dragstart=${this._dragstart}
        @dragend=${this._dragend}
        @dragover=${this._dragover}
        @drop=${this._dragdrop}
        @click=${this._navigateToIssue}
      >
        <td class="ignore-navigation">
          ${draggable ? html`
            <i class="material-icons draggable">drag_indicator</i>
          ` : ''}
          ${this.selectionEnabled ? html`
            <input
              class="issue-checkbox"
              .value=${i}
              type="checkbox"
              aria-label="Select Issue ${issue.localId}"
              @change=${this._selectIssue}
            />
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
            .queryParams=${this.queryParams}
            short
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
      /**
       * Array of columns to display.
       */
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
      /**
       * Object containing URL parameters to be preserved when issue links are
       * clicked.
       */
      queryParams: {type: Object},
      /**
       * Array of all selected issues. Each value is either true or false
       * depending on whether the issue at that index is selected.
       */
      _selectedIssues: {type: Object},
    };
  };

  constructor() {
    super();
    this.issues = [];
    this._selectedIssues = [];
    this.selectionEnabled = false;
    this.role = 'table';

    this.columns = ['Issue', 'Summary'];
  };

  update(changedProperties) {
    if (changedProperties.has('issues')) {
      // TODO(zhangtiff): Consider whether we want to redesign _selectedIssues
      // to work in the case when the issue list changes. ie: for example if
      // issues are auto-updated to reflect the latest issues matching a query.
      this._selectedIssues = Array(this.issues.length).fill(false);
    }
    super.update(changedProperties);
  }

  /**
   * Return an Array of selected issues in the order they appear in the list.
   */
  get selectedIssues() {
    return this._selectedIssues.map(
      (isSelected, i) => isSelected ? this.issues[i] : false).filter(Boolean);
  }

  // TODO(zhangtiff): Add Shift+Click to select a range of issues.
  _selectIssue(e) {
    if (!this.selectionEnabled) return;

    const checkbox = e.target;
    const i = Number.parseInt(checkbox.value);

    if (i < 0 || i >= this._selectedIssues.length) return;

    const oldSelection = this._selectedIssues[i];

    if (checkbox.checked) {
      this._selectedIssues[i] = true;
    } else {
      this._selectedIssues[i] = false;
    }

    if (this._selectedIssues[i] !== oldSelection) {
      this.requestUpdate('_selectedIssues');

      this.dispatchEvent(new CustomEvent('selection-change'));
    }
  }

  _navigateToIssue(e) {
    const containsIgnoredElement = e.path && e.path.find(
      (node) => node.classList
        && node.classList.contains('ignore-navigation'));
    if (containsIgnoredElement) return;

    const row = e.currentTarget;

    const i = Number.parseInt(row.dataset.index);

    if (i >= 0 && i < this.issues.length) {
      const issue = this.issues[i];
      const url = issueRefToUrl(issue);

      // TODO(zhangtiff): Find a better way to handle carrying
      // over query params.
      let query = window.location.search;
      query = query ? query.replace('?', '&') : '';
      page(`${url}${query}`);
    }
  }
};

customElements.define('mr-issue-list', MrIssueList);
