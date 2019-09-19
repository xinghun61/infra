// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

import page from 'page';
import {connectStore, store} from 'reducers/base.js';
import * as project from 'reducers/project.js';
import * as issue from 'reducers/issue.js';
import 'elements/framework/links/mr-issue-link/mr-issue-link.js';
import 'elements/framework/links/mr-crbug-link/mr-crbug-link.js';
import 'elements/framework/mr-dropdown/mr-dropdown.js';
import 'elements/framework/mr-star-button/mr-star-button.js';
import {issueRefToUrl, issueToIssueRef,
  issueRefToString, labelRefsToOneWordLabels} from 'shared/converters.js';
import {isTextInput} from 'shared/dom-helpers.js';
import {urlWithNewParams, pluralize} from 'shared/helpers.js';
import {stringValuesForIssueField, EMPTY_FIELD_VALUE,
  SPEC_DELIMITER_REGEX} from 'shared/issue-fields.js';
import './mr-show-columns-dropdown.js';

const COLUMN_DISPLAY_NAMES = {
  'summary': 'Summary + Labels',
};

/**
 * Really high cardinality attributes like ID and Summary are unlikely to be
 * useful if grouped, so it's better to just hide the option.
 */
const UNGROUPABLE_COLUMNS = new Set(['id', 'summary']);

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
      td, th.group-header {
        padding: 4px 8px;
        text-overflow: ellipsis;
        border-bottom: var(--chops-normal-border);
        cursor: pointer;
        font-weight: normal;
      }
      .group-header-content {
        height: 100%;
        width: 100%;
        align-items: center;
        display: flex;
      }
      th.group-header i.material-icons {
        font-size: var(--chops-icon-font-size);
        color: var(--chops-primary-icon-color);
        margin-right: 4px;
      }
      td.ignore-navigation {
        cursor: default;
      }
      th {
        background: var(--chops-table-header-bg);
        white-space: nowrap;
        text-align: left;
        z-index: 10;
        border-bottom: var(--chops-normal-border);
      }
      th.first-column {
        padding: 3px 8px;
      }
      th > mr-dropdown, th > mr-show-columns-dropdown {
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
        visibility: hidden;
      }
      td:hover > mr-crbug-link {
        visibility: visible;
      }
      .col-summary, .header-summary {
        /* Setting a table cell to 100% width makes it take up
         * all remaining space in the table, not the full width of
         * the table. */
        width: 100%;
      }
      .summary-label {
        display: inline-block;
        margin: 0 2px;
        color: var(--chops-green-800);
        text-decoration: none;
        font-size: 90%;
      }
      .summary-label:hover {
        text-decoration: underline;
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
    const selectAllChecked = this._selectedIssues.size > 0;

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
            <mr-show-columns-dropdown
              title="Show columns"
              menuAlignment="right"
              .columns=${this.columns}
              .queryParams=${this.queryParams}
              .phaseNames=${this._phaseNames}
            ></mr-show-columns-dropdown>
          </th>
        </tr>
        ${this._renderIssues()}
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
      <th style="z-index: ${zIndex};" class="header-${colKey}">
        <mr-dropdown
          class="dropdown-${colKey}"
          .text=${name}
          .items=${this._headerActions(column, i)}
          menuAlignment="left"
        ></mr-dropdown>
      </th>`;
  }

  _headerActions(column, i) {
    const actions = [
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
    ];
    if (!UNGROUPABLE_COLUMNS.has(column.toLowerCase())) {
      actions.push({
        text: 'Group rows',
        handler: () => this.addGroupBy(i),
      });
    }
    return actions;
  }

  _renderIssues() {
    // Keep track of all the groups that we've seen so far to create
    // group headers as needed.
    const {issues, groupedIssues} = this;

    if (groupedIssues) {
      // Make sure issues in groups are rendered with unique indices across
      // groups to make sure hot keys and the like still work.
      let indexOffset = 0;
      return html`${groupedIssues.map(({groupName, issues}) => {
        const template = html`
          ${this._renderGroup(groupName, issues, indexOffset)}
        `;
        indexOffset += issues.length;
        return template;
      })}`;
    }

    return html`
      ${issues.map((issue, i) => this._renderRow(issue, i))}
    `;
  }

  _renderGroup(groupName, issues, iOffset) {
    if (!this.groups.length) return '';

    const count = issues.length;
    const groupKey = groupName.toLowerCase();
    const isHidden = this._hiddenGroups.has(groupKey);

    return html`
      <tr>
        <th
          class="group-header"
          colspan="${this.numColumns}"
          @click=${() => this._toggleGroup(groupKey)}
          aria-expanded=${(!isHidden).toString()}
        >
          <div class="group-header-content">
            <i
              class="material-icons"
              title=${isHidden ? 'Show' : 'Hide'}
            >${isHidden ? 'add' : 'remove'}</i>
            ${count} ${pluralize(count, 'issue')}: ${groupName}
          </div>
        </th>
      </tr>
      ${issues.map((issue, i) => this._renderRow(issue, iOffset + i, isHidden))}
    `;
  }

  _toggleGroup(groupKey) {
    if (this._hiddenGroups.has(groupKey)) {
      this._hiddenGroups.delete(groupKey);
    } else {
      this._hiddenGroups.add(groupKey);
    }

    // Lit-element's default hasChanged check does not notice when Sets mutate.
    this.requestUpdate('_hiddenGroups');
  }

  _renderRow(issue, i, isHidden = false) {
    const draggable = this.rerankEnabled && this.rerankEnabled(issue);
    const rowSelected = this._selectedIssues.has(issueRefToString(issue));
    const id = issueRefToString(issue);

    return html`
      <tr
        class="row-${i} list-row ${i === this.srcIndex ? 'dragged' : ''}"
        ?selected=${rowSelected}
        ?hidden=${isHidden}
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
              <i
                class="material-icons draggable"
                title="Drag issue"
              >drag_indicator</i>
            ` : ''}
            ${this.selectionEnabled ? html`
              <input
                class="issue-checkbox"
                .value=${id}
                .checked=${rowSelected}
                type="checkbox"
                aria-label="Select Issue ${issue.localId}"
                @change=${this._selectIssue}
              />
            ` : ''}
            ${this.starringEnabled ? html`
              <mr-star-button
                .issueRef=${issueToIssueRef(issue)}
              ></mr-star-button>
            ` : ''}
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
        return html`
          ${issue.summary}
          ${labelRefsToOneWordLabels(issue.labelRefs).map(({label}) => html`
            <a
              class="summary-label"
              href="${this._baseUrl()}?q=label%3A${label}"
            >${label}</a>
          `)}
        `;
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
       * Array of columns that are used as groups for issues.
       */
      groups: {type: Array},
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
       * Whether to show issue starring or not.
       */
      starringEnabled: {type: Boolean},
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
       * Set of group keys that are currently hidden.
       */
      _hiddenGroups: {type: Object},
      /**
       * Set of all selected issues where each entry is an issue ref string.
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
      /**
       * List of unique phase names for all phases in issues.
       */
      _phaseNames: {type: Array},
    };
  };

  constructor() {
    super();
    this.issues = [];
    // TODO(jojwang): monorail:6336#c8, when ezt listissues page is fully
    // deprecated, remove phaseNames from mr-issue-list.
    this._phaseNames = [];
    this._selectedIssues = new Set();
    this.selectionEnabled = false;
    this.starringEnabled = false;
    this.role = 'table';

    this.columns = ['ID', 'Summary'];
    this.groups = [];

    this._boundRunNavigationHotKeys = this._runNavigationHotKeys.bind(this);

    this._hiddenGroups = new Set();

    this._fieldDefMap = new Map();
    this._labelPrefixSet = new Set();

    this._starredIssues = new Set();
    this._fetchingStarredIssues = false;
    this._starringIssues = new Map();

    // Expose page.js for stubbing.
    this._page = page;
  };

  stateChanged(state) {
    this._fieldDefMap = project.fieldDefMap(state);
    this._labelPrefixSet = project.labelPrefixSet(state);

    this._starredIssues = issue.starredIssues(state);
    this._fetchingStarredIssues =
        issue.requests(state).fetchStarredIssues.requesting;
    this._starringIssues = issue.starringIssues(state);

    this._phaseNames = (issue.issueListPhaseNames(state) || []);
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
      // Clear selected issues to avoid an ever-growing Set size. In the future,
      // we may want to consider saving selections across issue reloads, though,
      // such as in the case or list refreshing.
      this._selectedIssues = new Set();

      // Clear group toggle state when the list of issues changes to prevent an
      // ever-growing Set size.
      this._hiddenGroups = new Set();
    }
    super.update(changedProperties);
  }

  /**
   * Used for dynamically computing z-index to ensure column dropdowns overlap
   * properly.
   */
  get highestZIndex() {
    return this.columns.length + 10;
  }

  /**
   * The number of columns displayed in the table. This is the count of
   * customized columns + number of built in columns.
   */
  get numColumns() {
    return this.columns.length + 2;
  }

  /**
   * Sort issues into groups if groups are defined.
   */
  get groupedIssues() {
    if (!this.groups || !this.groups.length) return;

    const issuesByGroup = new Map();

    this.issues.forEach((issue) => {
      const groupName = this._groupNameForIssue(issue);
      const groupKey = groupName.toLowerCase();

      if (!issuesByGroup.has(groupKey)) {
        issuesByGroup.set(groupKey, {groupName, issues: [issue]});
      } else {
        const entry = issuesByGroup.get(groupKey);
        entry.issues.push(issue);
      }
    });
    return [...issuesByGroup.values()];
  }

  _groupNameForIssue(issue) {
    const groups = this.groups;
    const keyPieces = [];

    groups.forEach((group) => {
      const values = stringValuesForIssueField(issue, group, this.projectName,
          this._fieldDefMap, this._labelPrefixSet);
      if (!values.length) {
        keyPieces.push(`-has:${group}`);
      } else {
        values.forEach((v) => {
          keyPieces.push(`${group}=${v}`);
        });
      }
    });

    return keyPieces.join(' ');
  }

  /**
   * Return an Array of selected issues in the order they appear in the list.
   */
  get selectedIssues() {
    return this.issues.filter((issue) =>
      this._selectedIssues.has(issueRefToString(issue)));
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
    const columns = oldSpec.toLowerCase().split(SPEC_DELIMITER_REGEX);

    // Remove any old instances of the same sort spec.
    const newSpec = columns.filter(
        (c) => c && c !== column && c !== `-${column}`);

    newSpec.unshift(`${descending ? '-' : ''}${column}`);

    this._updateQueryParams({sort: newSpec.join(' ')}, ['start']);
  }

  /**
   * Updates the groupby URL parameter to include a new column to group.
   *
   * @param {Number} i index of the column to be grouped.
   */
  addGroupBy(i) {
    const groups = [...this.groups];
    const columns = [...this.columns];
    const groupedColumn = columns[i];
    columns.splice(i, 1);

    groups.unshift(groupedColumn);

    this._updateQueryParams({
      groupby: groups.join(' '),
      colspec: columns.join('+'),
    }, ['start']);
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
   * @param {Array} deletedParams keys to be cleared from queryParams.
   */
  _updateQueryParams(newParams = {}, deletedParams = []) {
    const url = urlWithNewParams(this._baseUrl(), this.queryParams, newParams,
        deletedParams);
    this._page(url);
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
        const key = issueRefToString(issue);
        this._updateSelectedIssue(key, !this._selectedIssues.has(key));
        break;
      case 'o': // Open current issue.
      case 'O': // Open current issue in new tab.
        this._navigateToIssue(issue, e.shiftKey);
        break;
    }
  }

  starIssue(issueRef) {
    if (!this.starringEnabled) return;
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
      this._selectedIssues = new Set(this.issues.map(issueRefToString));
    } else {
      this._selectedIssues = new Set();
    }
    this.dispatchEvent(new CustomEvent('selectionChange'));
  }

  // TODO(zhangtiff): Add Shift+Click to select a range of issues.
  _selectIssue(e) {
    if (!this.selectionEnabled) return;

    const checkbox = e.target;
    const idKey = checkbox.value;

    this._updateSelectedIssue(idKey, checkbox.checked);
  }

  _updateSelectedIssue(issueKey, selected) {
    const oldSelection = this._selectedIssues.has(issueKey);

    if (selected) {
      this._selectedIssues.add(issueKey);
    } else if (this._selectedIssues.has(issueKey)) {
      this._selectedIssues.delete(issueKey);
    }

    const newSelection = this._selectedIssues.has(issueKey);

    if (newSelection !== oldSelection) {
      this.requestUpdate('_selectedIssues');
      this.dispatchEvent(new CustomEvent('selectionChange'));
    }
  }

  _clickIssueRow(e) {
    const path = e.path || e.composedPath();
    const containsIgnoredElement = path.find(
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
