// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import page from 'page';
import qs from 'qs';

import {getServerStatusCron} from 'elements/shared/cron.js';
import 'elements/framework/mr-site-banner/mr-site-banner.js';
import {store, connectStore} from 'elements/reducers/base.js';
import * as issue from 'elements/reducers/issue.js';
import * as ui from 'elements/reducers/ui.js';
import {arrayToEnglish} from 'elements/shared/helpers.js';
import 'elements/framework/mr-header/mr-header.js';
import 'elements/framework/mr-keystrokes/mr-keystrokes.js';

import {SHARED_STYLES} from 'elements/shared/shared-styles.js';

/**
 * `<mr-app>`
 *
 * The container component for all pages under the Monorail SPA.
 *
 */
export class MrApp extends connectStore(LitElement) {
  static get styles() {
    return [SHARED_STYLES, css`
      main {
        border-top: var(--chops-normal-border);
      }
    `];
  }

  render() {
    return html`
      <mr-keystrokes
        .projectName=${this.projectName}
        .issueId=${this.queryParams.id}
        .queryParams=${this.queryParams}
        .issueEntryUrl=${this.issueEntryUrl}
      ></mr-keystrokes>
      <mr-header
        .projectName=${this.projectName}
        .userDisplayName=${this.userDisplayName}
        .issueEntryUrl=${this.issueEntryUrl}
        .loginUrl=${this.loginUrl}
        .logoutUrl=${this.logoutUrl}
      ></mr-header>
      <mr-site-banner></mr-site-banner>
      <mr-cue
        cuePrefName="switch_to_parent_account"
        .loginUrl=${this.loginUrl}
        centered
        nondismissible
      ></mr-cue>
      <mr-cue cuePrefName="search_for_numbers" centered></mr-cue>
      <main></main>
    `;
  }

  static get properties() {
    return {
      issueEntryUrl: {type: String},
      loginUrl: {type: String},
      logoutUrl: {type: String},
      projectName: {type: String},
      userDisplayName: {type: String},
      queryParams: {type: Object},
      dirtyForms: {type: Array},
      versionBase: {type: String},
      _currentContext: {type: Object},
    };
  }

  constructor() {
    super();
    this.queryParams = {};
    this.dirtyForms = [];
    this._currentContext = [];
  }

  stateChanged(state) {
    this.dirtyForms = ui.dirtyForms(state);
  }

  connectedCallback() {
    super.connectedCallback();

    // TODO(zhangtiff): Figure out some way to save Redux state between
    //   page loads.

    // page doesn't handle users reloading the page or closing a tab.
    window.onbeforeunload = this._confirmDiscardMessage.bind(this);

    // Start a cron task to periodically request the status from the server.
    getServerStatusCron.start();

    page('*', (ctx, next) => {
      // Navigate to the requested element if a hash is present.
      if (ctx.hash) {
        store.dispatch(ui.setFocusId(ctx.hash));
      }

      // We're not really navigating anywhere, so don't do anything.
      if (ctx.path === this._currentContext.path) {
        Object.assign(ctx, this._currentContext);
        // Set ctx.handled to false, so we don't push the state to browser's
        // history.
        ctx.handled = false;
        return;
      }

      // Check if there were forms with unsaved data before loading the next
      // page.
      const discardMessage = this._confirmDiscardMessage();
      if (!discardMessage || confirm(discardMessage)) {
        // Clear the forms to be checked, since we're navigating away.
        store.dispatch(ui.clearDirtyForms());
      } else {
        Object.assign(ctx, this._currentContext);
        // Set ctx.handled to false, so we don't push the state to browser's
        // history.
        ctx.handled = false;
        // We don't call next to avoid loading whatever page was supposed to
        // load next.
        return;
      }

      // Run query string parsing on all routes.
      // Based on: https://visionmedia.github.io/page.js/#plugins
      ctx.query = qs.parse(ctx.querystring);
      this.queryParams = ctx.query;
      this._currentContext = ctx;

      // Increment the count of navigations in the Redux store.
      store.dispatch(ui.incrementNavigationCount());

      next();
    });
    page('/p/:project/issues/list_new', this._loadGridPage.bind(this));
    page('/p/:project/issues/detail', this._loadIssuePage.bind(this));
    page();
  }

  loadWebComponent(name, props) {
    const component = document.createElement(name, {is: name});

    for (const key in props) {
      if (props.hasOwnProperty(key)) {
        component[key] = props[key];
      }
    }

    const main = this.shadowRoot.querySelector('main');
    if (main) {
      // Clone the main tag without copying its children.
      const mainClone = main.cloneNode(false);
      mainClone.appendChild(component);

      main.parentNode.replaceChild(mainClone, main);
    }
  }

  async _loadIssuePage(ctx, next) {
    performance.clearMarks('start load issue detail page');
    performance.mark('start load issue detail page');

    store.dispatch(issue.setIssueRef(
      Number.parseInt(ctx.query.id), ctx.params.project));

    this.projectName = ctx.params.project;

    await import(/* webpackChunkName: "mr-issue-page" */ '../issue-detail/mr-issue-page/mr-issue-page.js');
    // TODO(zhangtiff): Make sure the properties passed in to the loaded
    // component can still dynamically change.
    this.loadWebComponent('mr-issue-page', {
      'projectName': ctx.params.project,
      'userDisplayName': this.userDisplayName,
      'issueEntryUrl': this.issueEntryUrl,
      'queryParams': ctx.params,
      'loginUrl': this.loginUrl,
    });
  }

  async _loadGridPage(ctx, next) {
    store.dispatch(issue.setIssueRef(
      Number.parseInt(ctx.query.id), ctx.params.project));

    this.projectName = ctx.params.project;

    await import('../issue-list/mr-grid-page/mr-grid-page.js');
    this.loadWebComponent(/* webpackChunkName: "mr-grid-page" */ 'mr-grid-page', {
      'projectName': ctx.params.project,
      'userDisplayName': this.userDisplayName,
      'issueEntryUrl': this.issueEntryUrl,
      'queryParams': this.queryParams,
    });
  }

  _confirmDiscardMessage() {
    if (!this.dirtyForms.length) return null;
    const dirtyFormsMessage =
      'Discard your changes in the following forms?\n' +
      arrayToEnglish(this.dirtyForms);
    return dirtyFormsMessage;
  }
}

customElements.define('mr-app', MrApp);
