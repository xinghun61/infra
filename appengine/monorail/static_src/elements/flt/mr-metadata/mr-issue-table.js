// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

import '../../mr-bug-link/mr-bug-link.js';
import {selectors} from '../../redux/selectors.js';
import {ReduxMixin} from '../../redux/redux-mixin.js';
import '../shared/mr-flt-styles.js';

export class MrIssueTable extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <style include="mr-flt-styles">
        :host {
          display: block;
        }
        table {
          word-wrap: break-word;
          width: 100%;
        }
        tr {
          font-weight: normal;
          text-align: left;
          margin: 0 auto;
          padding: 2em 1em;
          height: 20px;
        }
        td {
          background: #f8f8f8;
          padding: 4px;
          padding-left: 8px;
          text-overflow: ellipsis;
        }
        th {
          text-decoration: none;
          margin-right: 0;
          padding-right: 0;
          padding-left: 8px;
          white-space: nowrap;
          background: #e3e9ff;
          text-align: left;
          border-right: 1px solid #fff;
          border-top: 1px solid #fff;
        }
        tr.dragged td {
          background: #eee;
        }
        .draggable {
          cursor: grab;
        }
        .error {
          max-width: 100%;
          color: red;
          margin-bottom: 1em;
        }
      </style>
      <h3 class="medium-heading">Blocked on issues</h3>
      <template is="dom-if" if="[[error]]">
        <div class="error">[[error]]</div>
      </template>
      <table><tbody>
        <tr>
          <template is="dom-if" if="[[rerankEnabled]]">
            <th></th>
          </template>
          <template is="dom-repeat" items="[[columns]]" as="column">
            <th>[[column]]</th>
          </template>
        </tr>
        <template is="dom-repeat" items="[[renderRows]]" as="row">
          <tr class\$="[[_getClass(index, srcIndex)]]" draggable="[[_canRerank(rerankEnabled, row)]]" data-index\$="[[index]]" on-dragstart="_dragstart" on-dragend="_dragend" on-dragover="_dragover" on-drop="_dragdrop">
            <template is="dom-if" if="[[rerankEnabled]]">
              <td>
                <template is="dom-if" if="[[_canRerank(rerankEnabled, row)]]">
                  <i class="material-icons draggable">drag_indicator</i>
                </template>
              </td>
            </template>
            <template is="dom-repeat" items="[[row.cells]]" as="cell">
              <td>
                <template is="dom-if" if="[[_isIssue(cell)]]">
                  <mr-bug-link project-name="[[cell.projectName]]" issue="[[cell.issue]]" is-closed="[[cell.isClosed]]"></mr-bug-link>
                </template>
                <template is="dom-if" if="[[_isText(cell)]]">
                  [[cell.content]]
                </template>
              </td>
            </template>
          </tr>
        </template>
      </tbody></table>
    `;
  }

  static get is() {
    return 'mr-issue-table';
  }

  static get properties() {
    return {
      columns: {
        type: Array,
        value: [],
      },
      rows: {
        type: Array,
        value: [],
        observer: 'reset',
      },
      rerankEnabled: {
        type: Boolean,
        value: false,
      },
      renderRows: {
        type: Array,
        value: [],
      },
      error: {
        String,
        value: '',
      },
      srcIndex: {
        type: Number,
        value: null,
      },
    };
  }

  reset() {
    this.error = null;
    this.srcIndex = null;
    this.renderRows = this.rows.slice();
  }

  _isIssue(item) {
    return item.type === 'issue';
  }

  _isText(item) {
    return item.type === 'text';
  }

  _getClass(index, srcIndex) {
    if (index === srcIndex) {
      return 'dragged';
    }
    return '';
  }

  _dragstart(e) {
    if (e.currentTarget.draggable) {
      this.srcIndex = Number(e.currentTarget.dataset.index);
      e.dataTransfer.setDragImage(new Image(), 0, 0);
    }
  }

  _dragover(e) {
    if (e.currentTarget.draggable && this.srcIndex !== null) {
      e.preventDefault();
      const targetIndex = Number(e.currentTarget.dataset.index);
      this._reorderRows(this.srcIndex, targetIndex);
      this.srcIndex = targetIndex;
    }
  }

  _dragend(e) {
    if (this.srcIndex !== null) {
      this.reset();
    }
  }

  _dragdrop(e) {
    if (e.currentTarget.draggable && this.srcIndex !== null) {
      const detail = {
        src: this.renderRows[this.srcIndex],
      };
      if (this.srcIndex > 0) {
        detail.target = this.renderRows[this.srcIndex-1];
        detail.above = false;
        this.dispatchEvent(new CustomEvent('reorder', {detail}));
      } else if (this.srcIndex === 0 &&
                 this.renderRows[1] && this.renderRows[1].draggable) {
        detail.target = this.renderRows[1];
        detail.above = true;
        this.dispatchEvent(new CustomEvent('reorder', {detail}));
      }
      this.srcIndex = null;
    }
  }

  _reorderRows(srcIndex, toIndex) {
    if (srcIndex <= toIndex) {
      this.renderRows = this.renderRows.slice(0, srcIndex).concat(
        this.renderRows.slice(srcIndex + 1, toIndex + 1),
        [this.renderRows[srcIndex]],
        this.renderRows.slice(toIndex + 1));
    } else {
      this.renderRows = this.renderRows.slice(0, toIndex).concat(
        [this.renderRows[srcIndex]],
        this.renderRows.slice(toIndex, srcIndex),
        this.renderRows.slice(srcIndex + 1));
    }
  }

  _canRerank(rerankEnabled, row) {
    return rerankEnabled && row.draggable;
  }
}

customElements.define(MrIssueTable.is, MrIssueTable);
