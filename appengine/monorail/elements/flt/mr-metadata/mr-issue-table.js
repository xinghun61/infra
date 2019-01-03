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
      },
    };
  }

  isIssue(item) {
    return item.type === 'issue';
  }

  isText(item) {
    return item.type === 'text';
  }
}

customElements.define(MrIssueTable.is, MrIssueTable);
