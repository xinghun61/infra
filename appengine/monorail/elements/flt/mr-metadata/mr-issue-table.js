// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

class MrIssueTable extends ReduxMixin(Polymer.Element) {
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
