// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement} from 'lit-element';
import qs from 'qs';
import {store, connectStore} from 'reducers/base.js';
import * as user from 'reducers/user.js';
import * as project from 'reducers/project.js';
import * as sitewide from 'reducers/sitewide.js';

/**
 * `<ezt-app-base>`
 *
 * Base component meant to simulate a subset of the work mr-app does on
 * EZT pages in order to allow us to more easily glue web components
 * on EZT pages to SPA web components.
 *
 */
export class EztAppBase extends connectStore(LitElement) {
  static get properties() {
    return {
      projectName: {type: String},
      userDisplayName: {type: String},
    };
  }

  connectedCallback() {
    super.connectedCallback();

    this.mapUrlToQueryParams();
  }

  updated(changedProperties) {
    if (changedProperties.has('userDisplayName') && this.userDisplayName) {
      this.fetchUserData(this.userDisplayName);
    }

    if (changedProperties.has('projectName')) {
      this.fetchProjectData(this.projectName);
    }
  }

  fetchUserData(displayName) {
    store.dispatch(user.fetch(displayName));
  }

  fetchProjectData(projectName) {
    store.dispatch(project.fetch(projectName));
  }

  mapUrlToQueryParams() {
    const params = qs.parse((window.location.search || '').substr(1));

    store.dispatch(sitewide.setQueryParams(params));
  }
}
customElements.define('ezt-app-base', EztAppBase);
