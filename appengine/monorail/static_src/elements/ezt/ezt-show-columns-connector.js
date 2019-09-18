/**
 * @fileoverview Description of this file.
 */
// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html} from 'lit-element';
import {store, connectStore} from 'reducers/base.js';
import qs from 'qs';
import * as sitewide from 'reducers/sitewide.js';
import 'elements/framework/mr-issue-list/mr-show-columns-dropdown.js';
import {SPEC_DELIMITER_REGEX} from 'shared/issue-fields.js';
import {equalsIgnoreCase} from 'shared/helpers.js';

/**
 * `<ezt-show-columns-connector>`
 *
 * Glue component to make "Show columns" dropdown work on EZT.
 *
 */
export class EztShowColumnsConnector extends connectStore(LitElement) {
  render() {
    return html`
      <mr-show-columns-dropdown
        .columns=${this.columns}
        .queryParams=${this.queryParams}
        .onHideColumn=${(name) => this.onHideColumn(name)}
        .onShowColumn=${(name) => this.onShowColumn(name)}
      ></mr-show-columns-dropdown>
    `;
  }

  static get properties() {
    return {
      initialColumns: {type: Array},
      hiddenColumns: {type: Object},
      queryParams: {type: Object},
      colspec: {type: String},
      phasespec: {type: String},
    };
  }

  constructor() {
    super();
    this.hiddenColumns = new Set();
    this.queryParams = {};
  }

  stateChanged(state) {
    this.queryParams = sitewide.queryParams(state);
  }

  get columns() {
    return this.initialColumns.filter((_, i) =>
      !this.hiddenColumns.has(i));
  }

  get initialColumns() {
    // EZT will always pass in a colspec.
    return this.colspec.split(SPEC_DELIMITER_REGEX);
  }

  get phaseNames() {
    return this.phasespec.split(SPEC_DELIMITER_REGEX);
  }

  onHideColumn(colName) {
    // Custom column hiding logic to avoid reloading the
    // EZT list page when a user hides a column.
    const colIndex = this.initialColumns.findIndex(
        (col) => equalsIgnoreCase(col, colName));

    // Legacy code integration.
    TKR_toggleColumn('hide_col_' + colIndex);

    this.hiddenColumns.add(colIndex);

    this.reflectColumnsToQueryParams();
    this.requestUpdate();

    // Don't continue navigation.
    return false;
  }

  onShowColumn(colName) {
    const colIndex = this.initialColumns.findIndex(
        (col) => equalsIgnoreCase(col, colName));
    if (colIndex >= 0) {
      this.hiddenColumns.delete(colIndex);
      TKR_toggleColumn('hide_col_' + colIndex);

      this.reflectColumnsToQueryParams();
      this.requestUpdate();
      return false;
    }
    // Reload the page if this column is not part of the initial
    // table render.
    return true;
  }

  reflectColumnsToQueryParams() {
    this.queryParams.colspec = this.columns.join(' ');

    // Make sure the column changes in the URL.
    window.history.replaceState({}, '', '?' + qs.stringify(this.queryParams));

    store.dispatch(sitewide.setQueryParams(this.queryParams));
  }
}
customElements.define('ezt-show-columns-connector', EztShowColumnsConnector);
