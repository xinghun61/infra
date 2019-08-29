// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import {css} from 'lit-element';
import {MrDropdown} from 'elements/framework/mr-dropdown/mr-dropdown.js';
import page from 'page';
import qs from 'qs';
import {connectStore} from 'reducers/base.js';
import * as project from 'reducers/project.js';
import {DEFAULT_ISSUE_FIELD_LIST} from 'shared/issue-fields.js';


/**
 * `<mr-show-columns-dropdown>`
 *
 * Issue list column options dropdown.
 *
 */
export class MrShowColumnsDropdown extends connectStore(MrDropdown) {
  static get styles() {
    return [
      ...MrDropdown.styles,
      css`
        :host {
          font-weight: normal;
          color: var(--chops-link-color);
          --mr-dropdown-icon-color: var(--chops-link-color);
          --mr-dropdown-anchor-padding: 3px 8px;
          --mr-dropdown-anchor-font-weight: bold;
          --mr-dropdown-menu-min-width: 150px;
          --mr-dropdown-menu-font-size: var(--chops-main-font-size);
          /* Because we're using a sticky header, we need to make sure the
          * dropdown cannot be taller than the screen. */
          --mr-dropdown-menu-max-height: 80vh;
          --mr-dropdown-menu-icon-size: var(--chops-main-font-size);
        }
      `,
    ];
  }
  static get properties() {
    return {
      ...MrDropdown.properties,
      /**
       * Array of displayed columns.
       */
      columns: {type: Array},
      /**
       * Array of built in fields that are available outside of project
       * configuration.
       */
      defaultIssueFields: {type: Array},
      _fieldDefs: {type: Array},
      _labelPrefixFields: {type: Array},
      // TODO(zhangtiff): Delete this legacy integration after removing
      // the list view.
      onHideColumn: {type: Function},
      onShowColumn: {type: Function},
    };
  }

  constructor() {
    super();

    this.icon = 'more_horiz';
    this.columns = [];

    // TODO(zhangtiff): Make this use more fields for hotlists.
    this.defaultIssueFields = DEFAULT_ISSUE_FIELD_LIST;
    this._fieldDefs = [];
    this._labelPrefixFields = [];

    this._page = page;
  }

  stateChanged(state) {
    this._fieldDefs = project.fieldDefs(state) || [];
    this._labelPrefixFields = project.labelPrefixFields(state) || [];
  }

  update() {
    this.items = this.issueOptions(this.defaultIssueFields, this._fieldDefs,
        this._labelPrefixFields, this.columns);

    super.update();
  }

  issueOptions(defaultFields, fieldDefs, labelPrefixes, columns) {
    const selectedOptions = new Set(
        columns.map((col) => col.toLowerCase()));

    const availableFields = new Set();

    defaultFields.forEach((field) => this._addAvailableField(
        availableFields, field, selectedOptions));

    fieldDefs.forEach((fd) => {
      const field = fd.fieldRef.fieldName;
      this._addAvailableField(
          availableFields, field, selectedOptions);
    });

    labelPrefixes.forEach((field) => this._addAvailableField(
        availableFields, field, selectedOptions));

    const sortedFields = [...availableFields];
    sortedFields.sort();

    return [
      ...columns.map((field, i) => ({
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
   * Removes the column at a particular index.
   *
   * @param {int} i the issue column to be removed.
   */
  removeColumn(i) {
    if (this.onHideColumn) {
      if (!this.onHideColumn(this.columns[i])) {
        return;
      }
    }
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
    if (this.onShowColumn) {
      if (!this.onShowColumn(name)) {
        return;
      }
    }
    this.reloadColspec([...this.columns, name]);
  }

  /**
   * Reflects changes to the columns of an issue list to the URL, through
   * frontend routing.
   *
   * @param {Array} newColumns the new colspec to set in the URL.
   */
  reloadColspec(newColumns) {
    this._updateQueryParams({colspec: newColumns.join(' ')});
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
}

customElements.define('mr-show-columns-dropdown', MrShowColumnsDropdown);
