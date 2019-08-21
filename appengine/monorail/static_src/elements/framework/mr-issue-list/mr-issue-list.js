// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import qs from 'qs';
import page from 'page';
import {connectStore, store} from 'reducers/base.js';
import * as project from 'reducers/project.js';
import * as issue from 'reducers/issue.js';
import 'elements/framework/links/mr-issue-link/mr-issue-link.js';
import 'elements/framework/links/mr-crbug-link/mr-crbug-link.js';
import 'elements/framework/mr-dropdown/mr-dropdown.js';
import 'elements/framework/mr-star-button/mr-star-button.js';
import {issueRefToUrl, issueToIssueRef,
  issueRefToString} from 'shared/converters.js';
import {isTextInput} from 'shared/dom-helpers';
import {stringValuesForIssueField, DEFAULT_ISSUE_FIELD_LIST,
  EMPTY_FIELD_VALUE, COLSPEC_DELIMITER_REGEX} from 'shared/issue-fields.js';

const COLUMN_DISPLAY_NAMES = {
  'summary': 'Summary + Labels',
};

export class MrIssueList extends connectStore(LitElement) {
  static get styles() {
    return css`
      :host {
        display: table;
        width: 100%;
        font-size: var(--chops-main-font-size);
      }
      .edit-widget-container {
        display: flex;
        flex-wrap: no-wrap;
        align-items: center;
      }
      mr-star-button {
        --mr-star-button-size: 18px;
        margin-bottom: 1px;
        margin-left: 4px;
      }
      input[type="checkbox"] {
        cursor: pointer;
        margin: 0 4px;
        width: 16px;
        height: 16px;
        border-radius: 2px;
        box-sizing: border-box;
        appearance: none;
        -webkit-appearance: none;
        border: 2px solid var(--chops-gray-400);
        position: relative;
        background: white;
      }
      th input[type="checkbox"] {
        border-color: var(--chops-gray-500);
      }
      input[type="checkbox"]:checked {
        background: var(--chops-primary-accent-color);
        border-color: var(--chops-primary-accent-color);
      }
      input[type="checkbox"]:checked::after {
        left: 1px;
        top: 2px;
        position: absolute;
        content: "";
        width: 8px;
        height: 4px;
        border: 2px solid white;
        border-right: none;
        border-top: none;
        transform: rotate(-45deg);
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
        background: var(--chops-table-header-bg);
        white-space: nowrap;
        text-align: left;
        z-index: 10;
      }
      th.first-column {
        padding: 3px 8px;
      }
      th > mr-dropdown {
        font-weight: normal;
        color: var(--chops-link-color);
        --mr-dropdown-icon-color: var(--chops-link-color);
        --mr-dropdown-anchor-padding: 3px 8px;
        --mr-dropdown-anchor-font-weight: bold;
        --mr-dropdown-menu-min-width: 150px;
      }
      tr {
        padding: 0 8px;
      }
      tr[selected] {
        background: var(--chops-selected-bg);
      }
      mr-crbug-link {
        display: none;
      }
      td:hover > mr-crbug-link {
        display: block;
      }
      .col-summary {
        /* Setting a table cell to 100% width makes it take up
         * all remaining space in the table, not the full width of
         * the table. */
        width: 100%;
      }
      mr-dropdown.show-columns {
        --mr-dropdown-menu-font-size: var(--chops-main-font-size);
        /* Because we're using a sticky header, we need to make sure the
         * dropdown cannot be taller than the screen. */
        --mr-dropdown-menu-max-height: 80vh;
        --mr-dropdown-menu-icon-size: var(--chops-main-font-size);
      }

      @media (min-width: 1024px) {
        .first-row th {
          position: sticky;
          top: var(--monorail-header-height);
        }
      }
    `;
  }

  render() {
    const selectAllChecked = this._selectedIssues.some(Boolean);
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <tbody>
        <tr class="first-row">
          <th class="first-column">
            <div class="edit-widget-container">
              ${this.selectionEnabled ? html`
                <input
                  class="select-all"
                  .checked=${selectAllChecked}
                  type="checkbox"
                  aria-label="Select ${selectAllChecked ? 'All' : 'None'}"
                  @change=${this._selectAll}
                />
              ` : ''}
            </div>
          </th>
          ${this.columns.map((column, i) => this._renderHeader(column, i))}
          <th style="z-index: ${this.highestZIndex};">
            <mr-dropdown
              class="show-columns"
              icon="more_horiz"
              title="Show columns"
              menuAlignment="right"
              .items=${this.issueOptions}
            ></mr-dropdown>
          </th>
        </tr>
        ${this.issues.map((issue, i) => this._renderRow(issue, i))}
      </tbody>
    `;
  }

  _renderHeader(column, i) {
    // zIndex is used to render the z-index property in descending order
    const zIndex = this.highestZIndex - i;

    const colKey = column.toLowerCase();
    const name = colKey in COLUMN_DISPLAY_NAMES ? COLUMN_DISPLAY_NAMES[colKey]
      : column;
    return html`
      <th style="z-index: ${zIndex};">
        <mr-dropdown
          class="dropdown-${column.toLowerCase()}"
          .text=${name}
          .items=${this._headerActions(column, i)}
          menuAlignment="left"
        ></mr-dropdown>
      </th>`;
  }

  _headerActions(column, i) {
    return [
      {
        text: 'Sort up',
        handler: () => this.updateSortSpec(column),
      },
      {
        text: 'Sort down',
        handler: () => this.updateSortSpec(column, true),
      },
      // TODO(zhangtiff): Add "Show only" feature.
      {
        text: 'Hide column',
        handler: () => this.removeColumn(i),
      },
      // TODO(zhangtiff): Add "Group rows" feature.
    ];
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
        @auxclick=${this._clickIssueRow}
        @keydown=${this._runListHotkeys}
        tabindex="0"
      >
        <td class="first-column ignore-navigation">
          <div class="edit-widget-container">
            ${draggable ? html`
              <i class="material-icons draggable">drag_indicator</i>
            ` : ''}
            ${this.selectionEnabled ? html`
              <input
                class="issue-checkbox"
                .value=${i}
                .checked=${rowSelected}
                type="checkbox"
                aria-label="Select Issue ${issue.localId}"
                @change=${this._selectIssue}
              />
            ` : ''}
            <mr-star-button
              .issueRef=${issueToIssueRef(issue)}
            ></mr-star-button>
          </div>
        </td>

        ${this.columns.map((column) => html`
          <td class="col-${column.toLowerCase()}">
            ${this._renderCell(column, issue) || EMPTY_FIELD_VALUE}
          </td>
        `)}

        <td>
          <mr-crbug-link .issue=${issue}></mr-crbug-link>
        </td>
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
        // TODO(zhangtiff): Add labels.
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
       * Array of built in fields that are available outside of project
       * configuration.
       */
      defaultIssueFields: {type: Array},
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

    // TODO(zhangtiff): Make this use more fields for hotlists.
    this.defaultIssueFields = DEFAULT_ISSUE_FIELD_LIST;

    this._boundRunNavigationHotKeys = this._runNavigationHotKeys.bind(this);

    this._fieldDefs = [];
    this._labelPrefixFields = [];
    this._fieldDefMap = new Map();
    this._labelPrefixSet = new Set();

    this._starredIssues = new Set();
    this._fetchingStarredIssues = false;
    this._starringIssues = new Map();

    // Expose page.js for stubbing.
    this._page = page;
  };

  stateChanged(state) {
    // The keys in the Set and Map objects for these values don't preserve
    // casing, so we want the original field lists as well.
    this._fieldDefs = project.fieldDefs(state) || [];
    this._labelPrefixFields = project.labelPrefixFields(state) || [];

    this._fieldDefMap = project.fieldDefMap(state);
    this._labelPrefixSet = project.labelPrefixSet(state);

    this._starredIssues = issue.starredIssues(state);
    this._fetchingStarredIssues =
        issue.requests(state).fetchStarredIssues.requesting;
    this._starringIssues = issue.starringIssues(state);
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
   * Compute all columns available for a given issue list.
   */
  get issueOptions() {
    const selectedOptions = new Set(
        this.columns.map((col) => col.toLowerCase()));

    const availableFields = new Set();

    this.defaultIssueFields.forEach((field) => this._addAvailableField(
        availableFields, field, selectedOptions));

    this._fieldDefs.forEach((fd) => {
      const field = fd.fieldRef.fieldName;
      this._addAvailableField(
          availableFields, field, selectedOptions);
    });

    this._labelPrefixFields.forEach((field) => this._addAvailableField(
        availableFields, field, selectedOptions));

    const sortedFields = [...availableFields];
    sortedFields.sort();

    return [
      ...this.columns.map((field, i) => ({
        icon: 'check',
        text: field,
        handler: () => this.removeColumn(i),
      })),
      ...sortedFields.map((field) => ({
        icon: '',
        text: field,
        handler: () => this.addColumn(field),
      })),
    ];
  }

  _addAvailableField(availableFields, field, selectedOptions) {
    if (!selectedOptions.has(field.toLowerCase())) {
      availableFields.add(field);
    }
  }

  /**
   * Used for dynamically computing z-index to ensure column dropdowns overlap
   * properly.
   */
  get highestZIndex() {
    return this.columns.length + 10;
  }

  /**
   * Return an Array of selected issues in the order they appear in the list.
   */
  get selectedIssues() {
    return this.issues.filter((_, i) => this._selectedIssues[i]);
  }

  /**
   * Update sort parameter in the URL based on user input.
   *
   * @param {string} column name of the column to be sorted.
   * @param {Boolean} descending descending or ascending order.
   */
  updateSortSpec(column, descending = false) {
    column = column.toLowerCase();
    const oldSpec = this.queryParams.sort || '';
    const columns = oldSpec.toLowerCase().split(COLSPEC_DELIMITER_REGEX);

    // Remove any old instances of the same sort spec.
    const newSpec = columns.filter(
        (c) => c && c !== column && c !== `-${column}`);

    newSpec.unshift(`${descending ? '-' : ''}${column}`);

    this._updateQueryParams({sort: newSpec.join(' ')});
  }

  /**
   * Removes the column at a particular index.
   *
   * @param {int} i the issue column to be removed.
   */
  removeColumn(i) {
    const columns = [...this.columns];
    columns.splice(i, 1);
    this.reloadColspec(columns);
  }

  /**
   * Adds a new column to a particular index.
   *
   * @param {string} name of the new column added.
   */
  addColumn(name) {
    this.reloadColspec([...this.columns, name]);
  }

  /**
   * Reflects changes to the columns of an issue list to the URL, through
   * frontend routing.
   *
   * @param {Array} newColumns the new colspec to set in the URL.
   */
  reloadColspec(newColumns) {
    this._updateQueryParams({colspec: newColumns.join('+')});
  }

  /**
   * Navigates to the same URL as the current page, but with query
   * params updated.
   *
   * @param {Object} newParams keys and values of the queryParams
   * Object to be updated.
   */
  _updateQueryParams(newParams) {
    const params = {...this.queryParams, ...newParams};
    this._page(`${this._baseUrl()}?${qs.stringify(params)}`);
  }

  /**
   * Get the current URL of the page, without query params. Useful for
   * test stubbing.
   *
   * @return {string} the URL of the list page, without params.
   */
  _baseUrl() {
    return window.location.pathname;
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
        this.starIssue(issueToIssueRef(issue));
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

  starIssue(issueRef) {
    const issueKey = issueRefToString(issueRef);

    // TODO(zhangtiff): Find way to share star disabling logic more.
    const isStarring = this._starringIssues.has(issueKey)
      && this._starringIssues.get(issueKey).requesting;
    const starEnabled = !this._fetchingStarredIssues && !isStarring;
    if (starEnabled) {
      const newIsStarred = !this._starredIssues.has(issueKey);
      this._starIssue(issueRef, newIsStarred);
    }
  }

  /**
   * Wrap store.dispatch and issue.star, for testing.
   *
   * @param {Object} issueRef the issue being starred.
   * @param {Boolean} newIsStarred whether to star or unstar the issue.
   */
  _starIssue(issueRef, newIsStarred) {
    store.dispatch(issue.star(issueRef, newIsStarred));
  }

  _selectAll(e) {
    const checkbox = e.target;

    if (checkbox.checked) {
      this._selectedIssues = this.issues.map(() => true);
    } else {
      this._selectedIssues = this.issues.map(() => false);
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
        (node) => (node.tagName || '').toUpperCase() === 'A' || (node.classList
        && node.classList.contains('ignore-navigation')));
    if (containsIgnoredElement) return;

    const row = e.currentTarget;

    const i = Number.parseInt(row.dataset.index);

    if (i >= 0 && i < this.issues.length) {
      this._navigateToIssue(this.issues[i], e.metaKey ||
          e.ctrlKey || e.button === 1);
    }
  }

  _navigateToIssue(issue, newTab) {
    const link = issueRefToUrl(issue, this.queryParams);

    if (newTab) {
      // Whether the link opens in a new tab or window is based on the
      // user's browser preferences.
      window.open(link, '_blank', 'noopener');
    } else {
      this._page(link);
    }
  }
};

customElements.define('mr-issue-list', MrIssueList);
