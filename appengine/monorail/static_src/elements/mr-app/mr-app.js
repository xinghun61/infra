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
import * as user from 'elements/reducers/user.js';
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
      ${this._renderPage()}
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
      page: {type: String},
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

  updated(changedProperties) {
    if (changedProperties.has('userDisplayName')) {
      store.dispatch(user.fetch(this.userDisplayName));
    }
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
    page('/p/:project/issues/list_new', this._loadListPage.bind(this));
    page('/p/:project/issues/detail', this._loadIssuePage.bind(this));
    page();
  }

  _renderPage() {
    if (this.page === 'detail') {
      return html`
        <mr-issue-page
          .projectName=${this.projectName}
          .userDisplayName=${this.userDisplayName}
          .queryParams=${this.queryParams}
          .loginUrl=${this.loginUrl}
        ></mr-issue-page>
      `;
    } else if (this.page === 'grid') {
      return html`
        <mr-grid-page
          .projectName=${this.projectName}
          .queryParams=${this.queryParams}
        ></mr-grid-page>
      `;
    } else if (this.page === 'list') {
      return html`
        <mr-list-page
          .projectName=${this.projectName}
          .queryParams=${this.queryParams}
        ></mr-list-page>
      `;
    }
  }

  async _loadIssuePage(ctx, next) {
    performance.clearMarks('start load issue detail page');
    performance.mark('start load issue detail page');

    store.dispatch(issue.setIssueRef(
      Number.parseInt(ctx.query.id), ctx.params.project));

    this.projectName = ctx.params.project;

    await import(/* webpackChunkName: "mr-issue-page" */ '../issue-detail/mr-issue-page/mr-issue-page.js');
    this.page = 'detail';
  }

  async _loadListPage(ctx, next) {
    this.projectName = ctx.params.project;

    switch (this.queryParams && this.queryParams.mode
        && this.queryParams.mode.toLowerCase()) {
      case 'grid':
        await import(/* webpackChunkName: "mr-grid-page" */ '../issue-list/mr-grid-page/mr-grid-page.js');
        this.page = 'grid';
        break;
      // TODO(zhangtiff): Add case for loading chart SPA page.
      // case 'chart':
      default:
        await import(/* webpackChunkName: "mr-list-page" */ '../issue-list/mr-list-page/mr-list-page.js');
        this.page = 'list';
        break;
    }
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
