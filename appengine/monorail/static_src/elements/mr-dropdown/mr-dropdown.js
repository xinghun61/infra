// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import '@polymer/polymer/polymer-legacy.js';
import {PolymerElement, html} from '@polymer/polymer';

/**
 * `<mr-dropdown>`
 *
 * Dropdown menu for Monorail.
 *
 */
export class MrDropdown extends PolymerElement {
  static get template() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <style>
        :host {
          position: relative;
          display: inline-block;
          cursor: pointer;
          height: 100%;
        }
        :host(:not([opened])) .menu {
          display: none;
          visibility: hidden;
        }
        i.material-icons {
          display: inline-block;
          color: var(--chops-primary-icon-color);
          margin: 2px;
        }
        .anchor {
          background: none;
          border: none;
          width: 100%;
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          color: var(--chops-link-color);
        }
        .menu {
          position: absolute;
          min-width: 120%;
          right: 0px;
          top: 98%;
          display: block;
          background: white;
          border: var(--chops-accessible-border);
          z-index: 990;
          box-shadow: 2px 3px 8px 0px hsla(0, 0%, 0%, 0.3);
        }
        .menu hr {
          width: 96%;
          margin: 0 2%;
          border: 0;
          height: 1px;
          background: hsl(0, 0%, 80%);
        }
        .menu a {
          box-sizing: border-box;
          text-decoration: none;
          font-size: 16px;
          white-space: nowrap;
          display: block;
          width: 100%;
          padding: 0.25em 8px;
          transition: 0.2s background ease-in-out;
          color: var(--chops-link-color);
        }
        .menu a:hover {
          background: hsl(0, 0%, 90%);
        }
      </style>
      <button class="anchor" on-click="toggle" aria-expanded$="[[_toString(opened)]]">
        [[text]]
        <i class="material-icons expand-icon">[[icon]]</i>
      </button>
      <div class="menu">
        <template is="dom-repeat" items="[[items]]">
          <hr hidden\$="[[!item.separator]]">
          <template is="dom-if" if="[[!item.separator]]">
            <a
              href\$="[[item.url]]"
              on-click="_onClick"
              data-idx\$="[[index]]"
              class="menu-item"
            >
              [[item.text]]
            </a>
          </template>
        </template>
      </div>
    `;
  }

  static get is() {
    return 'mr-dropdown';
  }

  static get properties() {
    return {
      text: String,
      items: Array,
      icon: String,
      opened: {
        type: Boolean,
        value: false,
        reflectToAttribute: true,
      },
      _boundCloseOnOutsideClick: {
        type: Function,
        value: function() {
          return this._closeOnOutsideClick.bind(this);
        },
      },
    };
  }

  _onClick(e) {
    const idx = e.target.dataset.idx;
    if (idx !== undefined && this.items[idx].handler) {
      this.items[idx].handler();
    }
    this.close();
  }

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener('click', this._boundCloseOnOutsideClick, true);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener('click', this._boundCloseOnOutsideClick,
      true);
  }

  toggle() {
    this.opened = !this.opened;
  }

  open() {
    this.opened = true;
  }

  close() {
    this.opened = false;
  }

  _closeOnOutsideClick(evt) {
    if (!this.opened) return;

    const hasMenu = evt.composedPath().find(
      (node) => {
        return node.classList && (
          node.classList.contains('menu') ||
          node.classList.contains('anchor')
        );
      }
    );
    if (hasMenu) return;

    this.close();
  }

  // TODO(zhangtiff): Remove this when upgrading to LitElement.
  _toString(bool) {
    return bool.toString();
  }
}

customElements.define(MrDropdown.is, MrDropdown);
