// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
import {css} from 'lit-element';
import {MrDropdown} from 'elements/framework/mr-dropdown/mr-dropdown.js';
import page from 'page';
import qs from 'qs';
import {connectStore} from 'reducers/base.js';
import * as project from 'reducers/project.js';
import {DEFAULT_ISSUE_FIELD_LIST, fieldTypes} from 'shared/issue-fields.js';


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
       * Array of unique phase names to prepend to phase field columns.
       */
      phaseNames: {type: Array},
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
    this.phaseNames = [];

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
    this.items = this.issueOptions(
        this.defaultIssueFields, this._fieldDefs, this._labelPrefixFields,
        this.columns, this.phaseNames);

    super.update();
  }

  issueOptions(defaultFields, fieldDefs, labelPrefixes, columns, phaseNames) {
    const selectedOptions = new Set(
        columns.map((col) => col.toLowerCase()));

    const availableFields = new Set();

    // Built-in, hard-coded fields like Owner, Status, and Labels.
    defaultFields.forEach((field) => this._addUnselectedField(
        availableFields, field, selectedOptions));

    // Custom fields.
    fieldDefs.forEach((fd) => {
      const {fieldRef, isPhaseField} = fd;
      const {fieldName, type} = fieldRef;
      if (isPhaseField) {
        // If the custom field belongs to phases, prefix the phase name for
        // each phase.
        phaseNames.forEach((phaseName) => {
          this._addUnselectedField(
              availableFields, `${phaseName}.${fieldName}`, selectedOptions);
        });
        return;
      }

      // TODO(zhangtiff): Prefix custom fields with "approvalName" defined by
      // the approval name after deprecating the old issue list page.

      // Most custom fields can be directly added to the list with no
      // modifications.
      this._addUnselectedField(
          availableFields, fieldName, selectedOptions);

      // If the custom field is type approval, then it also has a built in
      // "Approver" field.
      if (type === fieldTypes.APPROVAL_TYPE) {
        this._addUnselectedField(
            availableFields, `${fieldName}-Approver`, selectedOptions);
      }
    });

    // Fields inferred from label prefixes.
    labelPrefixes.forEach((field) => this._addUnselectedField(
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

  _addUnselectedField(availableFields, field, selectedOptions) {
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
