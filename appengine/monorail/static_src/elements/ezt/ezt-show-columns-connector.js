/**
 * @fileoverview Description of this file.
 */
// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html} from 'lit-element';
import qs from 'qs';
import 'elements/framework/mr-issue-list/mr-show-columns-dropdown.js';
import {COLSPEC_DELIMITER_REGEX} from 'shared/issue-fields.js';
import {equalsIgnoreCase} from 'shared/helpers.js';

/**
 * `<ezt-show-columns-connector>`
 *
 * Glue component to make "Show columns" dropdown work on EZT.
 *
 */
export class EztShowColumnsConnector extends LitElement {
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
      columns: {type: Array},
      queryParams: {type: Object},
      colspec: {type: String},
    };
  }

  constructor() {
    super();
    this.initialColumns = [];
    this.hiddenColumns = new Set();
    this.queryParams = {};
  }

  connectedCallback() {
    super.connectedCallback();

    this.setQueryParams();
  }

  get columns() {
    return this.initialColumns.filter((_, i) =>
      !this.hiddenColumns.has(i));
  }

  setQueryParams() {
    const search = (window.location.search || '').substr(1);
    const params = qs.parse(search);
    if (!params['colspec']) {
      params['colspec'] = this.colspec || '';
    }
    this.queryParams = params;
    this.initialColumns = params['colspec'].split(COLSPEC_DELIMITER_REGEX);
  }

  onHideColumn(colName) {
    // Custom column hiding logic to avoid reloading the
    // EZT list page when a user hides a column.
    const colIndex = this.initialColumns.findIndex(
        (col) => equalsIgnoreCase(col, colName));

    // Legacy code integration.
    TKR_toggleColumn('hide_col_' + colIndex);

    this.hiddenColumns.add(colIndex);

    this.queryParams.colspec = this.columns.join(' ');

    window.history.replaceState({}, '', '?' + qs.stringify(this.queryParams));

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

      this.requestUpdate();
      return false;
    }
    // Reload the page if this column is not part of the initial
    // table render.
    return true;
  }
}
customElements.define('ezt-show-columns-connector', EztShowColumnsConnector);
