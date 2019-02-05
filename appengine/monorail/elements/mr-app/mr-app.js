/* Copyright 2019 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file.
 */

import '../../node_modules/polymer-resin/standalone/polymer-resin.js';
import 'noclosure-resin-bridge';
import {dom} from '../../node_modules/@polymer/polymer/lib/legacy/polymer.dom.js';
import {PolymerElement, html} from '@polymer/polymer';
import page from 'page';
import qs from 'qs';

import {ReduxMixin, actionType} from '../redux/redux-mixin.js';
import '../flt/mr-approval-page/mr-approval-page.js';
import '../mr-header/mr-header.js';

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
      <mr-header project-name="[[projectName]]" user-display-name="[[userDisplayName]]" login-url="[[loginUrl]]" logout-url="[[logoutUrl]]">
        <template is="dom-if" if="[[subheader]]">
          <span slot="subheader">&gt; [[subheader]]</span>
        </template>
      </mr-header>
      <main></main>
    `;
  }

  static get is() {
    return 'mr-app';
  }

  static get properties() {
    return {
      loginUrl: String,
      logoutUrl: String,
      projectName: String,
      subheader: String,
      userDisplayName: String,
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

    const main = dom(this.root).querySelector('main');
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
    this.subheader = 'Feature Launch Issue';

    this.loadWebComponent('mr-approval-page', {
      'projectName': ctx.params.project,
      'userDisplayName': this.userDisplayName,
    });
  }
}

customElements.define(MrApp.is, MrApp);
