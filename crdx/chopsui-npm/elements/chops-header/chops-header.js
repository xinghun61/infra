// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';

export class ChopsHeader extends LitElement {
  constructor() {
    super();
    this.appTitle = 'Chops App';
    this.homeUrl = '/';
  }

  static get properties() {
    return {
      /* String for the title of the application. */
      appTitle: {
        type: String,
      },
      /* The home URL for the application. Defaults to '/'. */
      homeUrl: {
        type: String,
      },
      /* URL for the image location of the application's logo. No logo is
       * shown if this is not specified. */
      logoSrc: {
        type: String,
      },
      // TODO(zhangtiff): Also make the :host element extend the "header"
      // tag once browsers implement extending native elements with web
      // components.
      role: {
        type: String,
        reflect: true,
      },
    };
  }

  static get styles() {
    return css`
      :host {
        color: var(--chops-header-text-color);
        box-sizing: border-box;
        background: hsl(221, 67%, 92%);
        font-size: 14px;
        width: 100%;
        height: 50px;
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        z-index: 100;
      }
      a {
        color: var(--chops-header-text-color);
        text-decoration: none;
      }
      a:hover {
        text-decoration: underline;
      }
      #headerTitle {
        font-size: 18px;
        display: flex;
        align-items: center;
      }
      #headerTitle img {
        height: 32px;
        width: 32px;
        font-size: 10px;
        overflow: hidden;
        margin: 0;
      }
      #headerTitle small {
        font-size: 14px;
      }
      #headerTitleText {
        display: flex;
        align-items: baseline;
      }
      #headerTitleTextMain {
        padding: 0 8px;
      }
      .header-section {
        padding: 0.5em 16px;
        display: flex;
        align-items: center;
      }
      @media (max-width: 840px) {
        .header-section {
          font-size: 0.8em;
          min-width: 10%;
          text-align: left;
        }
      }
    `;
  }

  render() {
    return html`
      <div class="header-section">
        <slot name="before-header"></slot>
        <div id="headerTitle">
          ${this.logoSrc ? html`
            <a href="/">
              <img src=${this.logoSrc} alt="${this.appTitle} Logo" title="${this.appTitle} Logo">
            </a>
          ` : ''}
          <span id="headerTitleText">
            <a id="headerTitleTextMain" href="/">
              ${this.appTitle}
            </a>
            <small>
              <slot name="subheader"></slot>
            </small>
          </span>
        </div>
      </div>
      <div class="header-section">
        <slot></slot>
      </div>
    `;
  }
}

customElements.define('chops-header', ChopsHeader);
