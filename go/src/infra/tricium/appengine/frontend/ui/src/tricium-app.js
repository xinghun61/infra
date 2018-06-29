// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

import {LitElement, html} from '@polymer/lit-element/lit-element.js';
import {installRouter} from 'pwa-helpers/router.js';

import './tricium-feedback.js';
import './tricium-run.js';

class TriciumApp extends LitElement {
  constructor() {
    super();
    installRouter((loc) => {
      this.path = loc.pathname;
    });
  }

  static get properties() {
    return {
      path: String,
    };
  }

  _render({path}) {
    return html`
      <style>
        header {
          background-color: hsl(221, 67%, 92%);
          padding: 1em;
        }
        #main-title {
          pointer-events: auto;
          text-decoration: none;
          font-size: 1.5em;
        }
        .link {
          margin-top: 0.2em;
          float: right;
        }
      </style>
      <header>
        <a id="main-title" href="/">Tricium</a>
        <a class="link" href="/rpcexplorer/">RPC explorer</a>
      </header>
      ${this._body(path)}
    `;
  }

  _body(path) {
    if (path.startsWith('/run/')) {
      const runID = path.slice('/run/'.length);
      return html`
        <tricium-run run$="${runID}"></tricium-run>
      `;
    }
    if (path.startsWith('/feedback/')) {
      const category = path.slice('/feedback/'.length);
      return html`
        <tricium-feedback category$="${category}"></tricium-feedback>
      `;
    }
    return html`<img src="/static/images/tri.png">`;
  }
}

customElements.define('tricium-app', TriciumApp);
