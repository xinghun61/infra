// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import 'polymer-resin/standalone/polymer-resin.js';
import 'noclosure-resin-bridge';
import {PolymerElement, html} from '@polymer/polymer';
import page from 'page';
import qs from 'qs';

import {ReduxMixin} from '../redux/redux-mixin.js';
import * as issue from '../redux/issue.js';
import * as ui from '../redux/ui.js';
import {arrayToEnglish} from '../shared/helpers.js';
import '../mr-header/mr-header.js';
import '../mr-keystrokes/mr-keystrokes.js';

/**
 * `<mr-app>`
 *
 * The container component for all pages under the Monorail Polymer SPA.
 *
 */
export class MrApp extends ReduxMixin(PolymerElement) {
  static get template() {
    return html`
      <script>
        security.polymer_resin.install({
          'allowedIdentifierPrefixes': [''],
          'safeTypesBridge': security.polymer_resin.noclosure_bridge,
        });
      </script>
      <mr-keystrokes
        project-name="[[projectName]]"
        issue-id="[[queryParams.id]]"
        query-params="[[queryParams]]"
        issue-entry-url="[[issueEntryUrl]]"
      ></mr-keystrokes>
      <mr-header
        project-name="[[projectName]]"
        user-display-name="[[userDisplayName]]"
        issue-entry-url="[[issueEntryUrl]]"
        login-url="[[loginUrl]]"
        logout-url="[[logoutUrl]]"
      ></mr-header>
      <main></main>
    `;
  }

  static get is() {
    return 'mr-app';
  }

  static get properties() {
    return {
      issueEntryUrl: String,
      loginUrl: String,
      logoutUrl: String,
      projectName: String,
      userDisplayName: String,
      queryParams: Object,
      dirtyForms: Array,
      _currentContext: {
        type: Object,
        value: {},
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      dirtyForms: ui.dirtyForms(state),
    };
  }

  connectedCallback() {
    super.connectedCallback();

    // TODO(zhangtiff): Figure out some way to save Redux state between
    //   page loads.

    page('*', (ctx, next) => {
      // Navigate to the requested element if a hash is present.
      if (ctx.hash) {
        this.dispatchAction(ui.setFocusId(ctx.hash));
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
      if (this._confirmDiscard()) {
        // Clear the forms to be checked, since we're navigating away.
        this.dispatchAction(ui.clearDirtyForms());
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

      next();
    });
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
    this.dispatchAction(issue.setIssueRef(
      Number.parseInt(ctx.query.id), ctx.params.project));

    this.projectName = ctx.params.project;

    await import(/* webpackChunkName: "mr-issue-page" */ '../flt/mr-issue-page/mr-issue-page.js');
    // TODO(zhangtiff): Make sure the properties passed in to the loaded
    // component can still dynamically change.
    this.loadWebComponent('mr-issue-page', {
      'projectName': ctx.params.project,
      'userDisplayName': this.userDisplayName,
      'issueEntryUrl': this.issueEntryUrl,
      'queryParams': ctx.params,
    });
  }

  _confirmDiscard() {
    if (!this.dirtyForms.length) return true;
    const dirtyFormsMessage =
      'Discard your changes in the following forms?\n' +
      arrayToEnglish(this.dirtyForms);
    return confirm(dirtyFormsMessage);
  }
}

customElements.define(MrApp.is, MrApp);
