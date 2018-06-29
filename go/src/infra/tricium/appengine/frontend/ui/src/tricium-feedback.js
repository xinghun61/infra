// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

import {LitElement, html} from '@polymer/lit-element/lit-element.js';
import {request} from './prpc.js';

class TriciumFeedback extends LitElement {
  static get properties() {
    return {
      category: String,
      data: Object,
      error: String,
    };
  }

  _render({category, data, error}) {
    if (error || !data) {
      return html`<p style="color:red">${error}</p>`;
    }
    return html`
      <table border="1">
        <tr><th>Time</th><th>Comments</th><th>Not useful reports</th></tr>
        <tr><td>All time</td><td>${data.comments}</td><td>${data.notUsefulReports}</td></tr>
      </table>
    `;
  }

  // This should be called after "connected".
  // It is assumed that properties are initialized at this time.
  connectedCallback() {
    super.connectedCallback();
    if (!this.category) {
      console.warn('No category set on tricium-feedback');
    }
    this._refresh();
  }

  async _refresh() {
    try {
      this.data = await request('Feedback', {category: this.category});
    } catch (error) {
      this.error = error.message;
    }
  }
}

customElements.define('tricium-feedback', TriciumFeedback);
