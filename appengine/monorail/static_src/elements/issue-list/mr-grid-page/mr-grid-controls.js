// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {connectStore} from 'elements/reducers/base.js';
import page from 'page';
import qs from 'qs';
import './mr-grid-dropdown';
import './mr-choice-buttons';
import * as issue from 'elements/reducers/issue.js';
import {getAvailableGridFields} from './extract-grid-data.js';

export class MrGridControls extends connectStore(LitElement) {
  render() {
    return html`
    <div>
      <div class="rowscols">
        <mr-grid-dropdown
          class="rows"
          .text=${'Rows'}
          .items=${this.issueProperties}
          .selection=${this.queryParams.y}
          @change=${this._rowChanged}>
        </mr-grid-dropdown>
        <mr-grid-dropdown
          class="cols"
          .text=${'Cols'}
          .items=${this.issueProperties}
          .selection=${this.queryParams.x}
          @change=${this._colChanged}>
        </mr-grid-dropdown>
      </div>
      <div class="cell-selector">
        <mr-choice-buttons
          class='cells'
          .options=${this.cells}
          @change=${this._cellSelected}
          .value=${this.cellType}>
        </mr-choice-buttons>
      </div>
    </div>
    <div class="right-controls">
      <div class="issue-count">
        ${this.issueCount}
        of
        ${this.totalIssues}
        ${this.totalIssues === 1 ? html`
          issue `: html`
          issues `} shown
      </div>
      <div class="view-selector">
        <mr-choice-buttons
          .options=${this.viewSelector}
          @change=${this._viewSelected}
          .value=${'grid'}>
        </mr-choice-buttons>
      </div>
    </div>
      `;
  }

  constructor() {
    super();
    this.issueProperties = getAvailableGridFields();
    this.cells = [
      {text: 'Tile', value: 'tiles'},
      {text: 'IDs', value: 'ids'},
      {text: 'Counts', value: 'counts'},
    ];
    this.viewSelector = [
      {text: 'List', value: 'list'},
      {text: 'Grid', value: 'grid'},
      {text: 'Chart', value: 'chart'},
    ];
    this.queryParams = {y: 'None', x: 'None'};
    this.cellType = 'tiles';
    this.totalIssues = 0;
  };

  static get properties() {
    return {
      issueProperties: {type: Array},
      cells: {type: Array},
      cellType: {type: String},
      viewSelector: {type: Array},
      queryParams: {type: Object},
      customFieldDefs: {type: Array},
      issueCount: {type: Number},
      totalIssues: {type: Number},
    };
  };

  update(changedProperties) {
    if (changedProperties.has('customFieldDefs')) {
      this.issueProperties = getAvailableGridFields(this.customFieldDefs);
    }
    if (changedProperties.has('cells') && this.queryParams.cells) {
      this.cellType = this.queryParams.cells;
    }
    super.update(changedProperties);
  }

  stateChanged(state) {
    this.totalIssues = (issue.totalIssues(state) || 0);
  }
  static get styles() {
    return css`
      :host {
        display: flex;
        justify-content: space-between;
        margin-top: 20px;
        aign-items: center;
        margin-right: 20px;
      }
      .rows {
        display: inline-block;
        padding-left: 20px;
      }
      .cols {
        display: inline-block;
        padding-left: 20px;
      }
      .rowscols {
        display: inline-block;
      }
      .cell-selector {
        padding-left: 20px;
        display: inline-block;
      }
      .right-controls {
        display: inline-block;
      }
      .issue-count {
        display: inline-block;
        padding-right: 20px;
      }
      .view-selector {
        display: inline-block;
      }
    `;
  };

  _rowChanged(e) {
    this.queryParams.y = e.target.selection;
    const params = Object.assign({}, this.queryParams);
    if (this.queryParams.y === 'None') {
      params.y = '';
    }
    this._changeUrlParams(params);
  }

  _colChanged(e) {
    this.queryParams.x = e.target.selection;
    const params = Object.assign({}, this.queryParams);
    if (this.queryParams.x === 'None') {
      params.x = '';
    }
    this._changeUrlParams(params);
  }

  _changeUrlParams(params) {
    const newParams = qs.stringify(params);
    const newUrl = `${location.pathname}?${newParams}`;
    page(newUrl);
  }

  _cellSelected(e) {
    this.queryParams.cells = e.target.value;
    this._changeUrlParams(this.queryParams);
  }

  _viewSelected(e) {
    const value = e.target.value.toLowerCase();
    if (value !== 'grid') {
      if (value === 'chart') {
        this.queryParams.mode = 'chart';
      } else {
        delete this.queryParams.mode;
      }
      const params = qs.stringify(this.queryParams);
      const newURL =
        `${location.pathname.replace('list_new', 'list')}?${params}`;
      page(newURL);
    }
  }
};

customElements.define('mr-grid-controls', MrGridControls);
