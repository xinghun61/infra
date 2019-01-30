// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

/**
 * `<mr-app>`
 *
 * The container component for all pages under the Monorail Polymer SPA.
 *
 */
class MrApp extends ReduxMixin(Polymer.Element) {
  static get is() {
    return 'mr-app';
  }

  static get properties() {
    return {
      loginUrl: String,
      logoutUrl: String,
      projectName: String,
      subheader: String,
      user: String,
      _boundLoadApprovalPage: {
        type: Function,
        value: function() {
          return this._loadApprovalPage.bind(this);
        },
      },
    };
  }

  connectedCallback() {
    super.connectedCallback();

    // TODO(zhangtiff): Figure out some way to save Redux state between
    //   page loads.

    page('*', (ctx, next) => {
      // Run query string parsing on all routes.
      // Based on: https://visionmedia.github.io/page.js/#plugins
      ctx.query = Qs.parse(ctx.querystring);

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

    const main = Polymer.dom(this.root).querySelector('main');
    if (main) {
      // Clone the main tag without copying its children.
      const mainClone = main.cloneNode(false);
      mainClone.appendChild(component);

      main.parentNode.replaceChild(mainClone, main);
    }
  }

  _loadApprovalPage(ctx, next) {
    this.dispatch({
      type: actionType.UPDATE_ISSUE_REF,
      issueId: Number.parseInt(ctx.query.id),
      projectName: ctx.params.project,
    });

    this.projectName = ctx.params.project;
    this.subheader = 'Feature Launch Issue';

    this.loadWebComponent('mr-approval-page', {
      'projectName': ctx.params.project,
      'user': this.user,
    });
  }
}

customElements.define(MrApp.is, MrApp);
