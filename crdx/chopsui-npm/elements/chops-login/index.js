// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

/**
 * `chops-login` shows the login/logout links and current user, if provided.
 *
 * When the user is logged in provide, at least, the user and logoutURL
 * properties. When there is no user logged in provide, at least the loginURL
 * property.  * In either case, bother URLs may be provided but only one will
 * be shown.
 *
 * @customElement
 * @polymer
 * @demo /demo/chops-login_demo.html
 */

export class ChopsLogin extends LitElement {
  static get styles() {
    return css`
      :host {
        --chops-login-link-color: inherit;
      }
      a, a:link {
        color: var(--chops-login-link-color);
        font-size: 0.75em;
        text-decoration: none;
      }
    `;
  }

  render() {
    if (this.user) {
      return html`${this.user} (<a href="${this.logoutUrl}">LOGOUT</a>)`;
    }
    return html`<a href="${this.loginUrl}">LOGIN</a>`;
  }

  static get properties() {
    return {
      /** The login URL must be provided if no user is given. */
      loginUrl: {
        type: String,
      },
      /** The logout URL must be provided if a user is given. */
      logoutUrl: {
        type: String,
      },
      /** The logged in user. If this isn't given the login URL will be shown.*/
      user: {
        type: String,
        value: '',
      },
    };
  }
}

customElements.define('chops-login', ChopsLogin);
