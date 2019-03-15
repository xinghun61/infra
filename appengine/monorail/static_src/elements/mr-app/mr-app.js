// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import 'polymer-resin/standalone/polymer-resin.js';
import 'noclosure-resin-bridge';
import {PolymerElement, html} from '@polymer/polymer';
import page from 'page';
import qs from 'qs';

import {ReduxMixin, actionType} from '../redux/redux-mixin.js';
import '../flt/mr-issue-page/mr-issue-page.js';
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
      _boundLoadApprovalPage: {
        type: Function,
        value: function() {
          return this._loadApprovalPage.bind(this);
        },
      },
      formsToCheck: Array,
      _currentContext: {
        type: Object,
        value: {},
      },
    };
  }

  static mapStateToProps(state, element) {
    return {
      formsToCheck: state.formsToCheck,
      prevContext: state.prevContext,
    };
  }

  connectedCallback() {
    super.connectedCallback();

    // TODO(zhangtiff): Figure out some way to save Redux state between
    //   page loads.

    page('*', (ctx, next) => {
      // Navigate to the requested element if a hash is present.
      if (ctx.hash) {
        this.dispatchAction({
          type: actionType.SET_FOCUS_ID,
          focusId: ctx.hash,
        });
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
      const isDirty = this.formsToCheck.some((form) => {
        return (Object.keys(form.getDelta()).length !== 0);
      });
      if (!isDirty || confirm('Discard your changes?')) {
        // Clear the forms to be checked, since we're navigating away.
        this.dispatchAction({type: actionType.CLEAR_FORMS_TO_CHECK});
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
    page('/p/:project/issues/approval', this._boundLoadApprovalPage);
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

  _loadApprovalPage(ctx, next) {
    this.dispatchAction({
      type: actionType.UPDATE_ISSUE_REF,
      issueId: Number.parseInt(ctx.query.id),
      projectName: ctx.params.project,
    });

    this.projectName = ctx.params.project;

    // TODO(zhangtiff): Make sure the properties passed in to the loaded
    // component can still dynamically change.
    this.loadWebComponent('mr-issue-page', {
      'projectName': ctx.params.project,
      'userDisplayName': this.userDisplayName,
      'issueEntryUrl': this.issueEntryUrl,
      'queryParams': ctx.params,
    });
  }
}

customElements.define(MrApp.is, MrApp);
