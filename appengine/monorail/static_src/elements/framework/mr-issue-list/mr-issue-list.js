// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import page from 'page';
import {connectStore} from 'elements/reducers/base.js';
import * as project from 'elements/reducers/project.js';
import 'elements/framework/links/mr-issue-link/mr-issue-link.js';
import {issueRefToUrl} from 'elements/shared/converters.js';
import {isTextInput} from 'elements/shared/dom-helpers';
import {stringValuesForIssueField,
  EMPTY_FIELD_VALUE} from 'elements/shared/issue-fields.js';


export class MrIssueList extends connectStore(LitElement) {
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
      tr {
        padding: 0 8px;
      }
      tr[selected] {
        background: var(--chops-selected-bg);
      }

      @media (min-width: 1024px) {
        .first-row th {
          position: sticky;
          top: var(--monorail-header-height);
          z-index: 5;
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
        class="row-${i} list-row ${i === this.srcIndex ? 'dragged' : ''}"
        ?selected=${rowSelected}
        draggable=${draggable}
        data-index=${i}
        @dragstart=${this._dragstart}
        @dragend=${this._dragend}
        @dragover=${this._dragover}
        @drop=${this._dragdrop}
        @click=${this._clickIssueRow}
        @keydown=${this._runListHotkeys}
        tabindex="0"
      >
        <td class="first-column ignore-navigation">
          ${draggable ? html`
            <i class="material-icons draggable">drag_indicator</i>
          ` : ''}
          ${this.selectionEnabled ? html`
            <input
              class="issue-checkbox"
              .value=${i}
              ?checked=${rowSelected}
              type="checkbox"
              aria-label="Select Issue ${issue.localId}"
              @change=${this._selectIssue}
            />
          ` : ''}
        </td>

        ${this.columns.map((column) => html`
          <td class="col-${column.toLowerCase()}">
            ${this._renderCell(column, issue) || EMPTY_FIELD_VALUE}
          </td>
        `)}
      </tr>
    `;
  }

  _renderCell(column, issue) {
    // Fields that need to render more than strings happen first.
    switch (column.toLowerCase()) {
      case 'id':
        return html`
           <mr-issue-link
            .projectName=${this.projectName}
            .issue=${issue}
            .queryParams=${this.queryParams}
            short
          ></mr-issue-link>
        `;
      case 'summary':
        return issue.summary;
    }
    const values = stringValuesForIssueField(issue, column, this.projectName,
      this._fieldDefMap, this._labelPrefixSet);
    return values.join(', ');
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
      /**
       * Map of fieldDefs in currently viewed project, used for computing
       * displayed values.
       */
      _fieldDefMap: {type: Object},
      /**
       * Set of label prefixes.
       */
      _labelPrefixSet: {type: Object},
    };
  };

  constructor() {
    super();
    this.issues = [];
    this._selectedIssues = [];
    this.selectionEnabled = false;
    this.role = 'table';

    this.columns = ['ID', 'Summary'];

    this._boundRunNavigationHotKeys = this._runNavigationHotKeys.bind(this);

    this._fieldDefMap = new Map();
    this._labelPrefixSet = new Set();
  };

  stateChanged(state) {
    this._fieldDefMap = project.fieldDefMap(state);
    this._labelPrefixSet = project.labelPrefixSet(state);
  }

  firstUpdated() {
    // Only attach an event listener once the DOM has rendered.
    window.addEventListener('keydown', this._boundRunNavigationHotKeys);
  }

  disconnectedCallback() {
    super.disconnectedCallback();

    window.removeEventListener('keydown', this._boundRunNavigationHotKeys);
  }

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
    return this.issues.filter((_, i) => this._selectedIssues[i]);
  }

  // Navigate between issues in the list by focusing them. These keys
  // need to be bound globally because the user can run these actions
  // even when they are not currently focusing an issue.
  _runNavigationHotKeys(e) {
    if (!this.issues || !this.issues.length) return;
    const target = e.path ? e.path[0] : e.target;
    if (!target || isTextInput(target)) return;
    const key = e.key;
    if (key === 'j' || key === 'k') {
      let activeRow = this.shadowRoot.activeElement;

      // If the focused element is a child of a table row, find the parent
      // table row to navigate users to the prev/next issue relative to where
      // they are focused.
      while (activeRow && (activeRow.tagName.toUpperCase() !== 'TR'
          || !activeRow.classList.contains('list-row'))) {
        // This loop is guaranteed to run in the DOM within this component's
        // template because of ShadowDOM. Neither HTMLElement.activeElement
        // nor HTMLElement.parentElement penetrate shadow roots.
        // This guarantees that we don't need to worry about <tr> tags or
        // class="list-row" elements anywhere else on the page, including
        // nested inside the element.
        activeRow = activeRow.parentElement;
      }

      let i = -1;
      if (activeRow) {
        i = Number.parseInt(activeRow.dataset.index);
      }

      if (key === 'j') { // Navigate down the list.
        i += 1;
        if (i >= this.issues.length) {
          i = 0;
        }
      } else if (key === 'k') { // Navigate up the list.
        i -= 1;
        if (i < 0) {
          i = this.issues.length - 1;
        }
      }

      const row = this.shadowRoot.querySelector(`.row-${i}`);
      row.focus();
    }
  }

  // Issue list hot key actions
  _runListHotkeys(e) {
    const target = e.target;
    const i = Number.parseInt(target.dataset.index);
    if (Number.isNaN(i)) return;

    const issue = this.issues[i];

    switch (e.key) {
      case 's': // Star focused issue.
        // TODO(zhangtiff): Add this hot key when adding issue starring.
        break;
      case 'x': // Toggle selection of focused issue.
        this._updateSelectedIssue(i, !this._selectedIssues[i]);
        break;
      case 'o': // Open current issue.
      case 'O': // Open current issue in new tab.
        this._navigateToIssue(issue, e.shiftKey);
        break;
    }
  }

  // TODO(zhangtiff): Add Shift+Click to select a range of issues.
  _selectIssue(e) {
    if (!this.selectionEnabled) return;

    const checkbox = e.target;
    const i = Number.parseInt(checkbox.value);

    if (i < 0 || i >= this._selectedIssues.length) return;

    this._updateSelectedIssue(i, checkbox.checked);
  }

  _updateSelectedIssue(i, selected) {
    const oldSelection = this._selectedIssues[i];

    if (selected) {
      this._selectedIssues[i] = true;
    } else {
      this._selectedIssues[i] = false;
    }

    if (this._selectedIssues[i] !== oldSelection) {
      this.requestUpdate('_selectedIssues');

      this.dispatchEvent(new CustomEvent('selectionChange'));
    }
  }

  _clickIssueRow(e) {
    const containsIgnoredElement = e.path && e.path.find(
      (node) => node.classList
        && node.classList.contains('ignore-navigation'));
    if (containsIgnoredElement) return;

    const row = e.currentTarget;

    const i = Number.parseInt(row.dataset.index);

    if (i >= 0 && i < this.issues.length) {
      this._navigateToIssue(this.issues[i]);
    }
  }

  _navigateToIssue(issue, newTab) {
    const url = issueRefToUrl(issue);

    // TODO(zhangtiff): Find a better way to handle carrying
    // over query params.
    let query = window.location.search;
    query = query ? query.replace('?', '&') : '';
    const link = `${url}${query}`;

    if (newTab) {
      window.open(link, '_blank', 'noopener');
    } else {
      page(link);
    }
  }
};

customElements.define('mr-issue-list', MrIssueList);
