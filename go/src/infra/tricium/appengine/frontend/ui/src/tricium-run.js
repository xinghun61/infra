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

  // Renders (returns a TemplateResult) for the run page.
  _render({run, data, error}) {
    if (error || !data || !data.runId) {
      return html`<p style="color:red">${error}</p>`;
    }
    return html`
      <p>
        <b>Run ID: ${data.runId}</b> (State: ${data.state})
      </p>
      ${repeat(data.functionProgress, (f) => f.name, this._renderFunction.bind(this))}
    `;
  }

  // Renders a single function run with state and a link to more details.
  _renderFunction(f) {
    const link = this._renderLink(f);
    return html`
      <p>
        <b>${f.name}</b>
        (State: ${f.state || 'PENDING'},
        ${link},
        comments: ${f.numComments || 0})
      </p>
    `;
  }

  // Renders a link to more details for the run, or an empty TemplateResult.
  _renderLink(f) {
    if (f.swarmingTaskId) {
      return html`
        <a href$="${f.swarmingUrl}/task?id=${f.swarmingTaskId}">
          task ${f.swarmingTaskId}
        </a>`;
    } else if (f.buildbucketBuildId) {
      const host = this._chromiumMiloHost(f.buildbucketHost);
      if (!host) {
        return html`build ${f.buildbucketBuildId}`;
      }
      return html`
        <a href$="https://${host}/b/${f.buildbucketBuildId}">
          build ${f.buildbucketBuildId}
        </a>`;
    }
    return html`error: no swarming task ID or buildbucket build ID`;
  }

  // Returns a host for viewing build information for buildbucket builds.
  //
  // This makes a "best-effort" attempt at guessing. For some specific
  // instances of Buildbucket, we know which hosts to use; if the Buildbucket
  // host doesn't match those, this function returns empty string.
  _chromiumMiloHost(buildbucketHost) {
    if (buildbucketHost == 'cr-buildbucket-dev.appspot.com') {
      return 'luci-milo-dev.appspot.com';
    } else if (buildbucketHost == 'cr-buildbucket.appspot.com') {
      return 'ci.chromium.org';
    }
    return '';
  }

  // connectedCallback is called when the element is inserted (connected)
  // into the document.
  connectedCallback() {
    super.connectedCallback();
    if (!this.run) {
      console.warn('No run set on tricium-run');
    }
    this._refresh();
  }

  // _refresh fetches data from Tricium and sets this.data or
  // this.error; when those values change _render will be called.
  async _refresh() {
    try {
      this.data = await request('Progress', {runId: this.run});
    } catch (error) {
      this.error = error.message;
    }
  }
}

customElements.define('tricium-run', TriciumRun);
