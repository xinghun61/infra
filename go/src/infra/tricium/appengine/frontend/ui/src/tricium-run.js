// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

import {LitElement, html} from '@polymer/lit-element/lit-element.js';
import {repeat} from 'lit-html/lib/repeat.js';

import {request} from './prpc.js';

class TriciumRun extends LitElement {
  static get properties() {
    return {
      run: String,
      data: Object,
      error: String,
    };
  }

  _render({run, data, error}) {
    if (error || !data || !data.runId) {
      return html`<p style="color:red">${error}</p>`;
    }
    return html`
      <p>
        <b>Run ID: ${data.runId}</b> (State: ${data.state})
      </p>
      ${repeat(data.functionProgress, f => f.name, this._renderFunction)}
    `;
  }

  _renderFunction(f) {
    return html`
      <p>
        <b>${f.name}</b>
        (State: ${f.state},
        <a href$="${f.swarmingUrl}/task?id=${f.swarmingTaskId}">Swarming task</a>,
        comments: ${f.numComments})
      </p>
    `;
  }

  _url(f) {
    return `${f.swarmingUrl}/task?id=${f.swarmingTaskId}`;
  }

  connectedCallback() {
    super.connectedCallback();
    if (!this.run) {
      console.warn('No run set on tricium-run');
    }
    this._refresh();
  }

  async _refresh() {
    try {
      this.data = await request('Progress', {runId: this.run});
    } catch (error) {
      this.error = error.message;
    }
  }
}

customElements.define('tricium-run', TriciumRun);
