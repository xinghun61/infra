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
          height: 100%;
          font-size: inherit;
        }
        :host([hidden]) {
          display: none;
          visibility: hidden;
        }
        :host(:not([opened])) .menu {
          display: none;
          visibility: hidden;
        }
        strong {
          font-size: var(--chops-large-font-size);
        }
        i.material-icons {
          font-size: var(--chops-icon-font-size);
          display: inline-block;
          color: var(--chops-primary-icon-color);
          padding: 0 2px;
          box-sizing: border-box;
        }
        .anchor {
          box-sizing: border-box;
          background: none;
          border: none;
          font-size: inherit;
          width: 100%;
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          color: var(--chops-link-color);
        }
        .menu.right {
          right: 0px;
        }
        .menu.left {
          left: 0px;
        }
        .menu {
          font-size: var(--chops-large-font-size);
          position: absolute;
          min-width: 120%;
          top: 90%;
          display: block;
          background: white;
          border: var(--chops-accessible-border);
          z-index: 990;
          box-shadow: 2px 3px 8px 0px hsla(0, 0%, 0%, 0.3);
        }
        .menu-item {
          box-sizing: border-box;
          text-decoration: none;
          white-space: nowrap;
          display: block;
          width: 100%;
          padding: 0.25em 8px;
          transition: 0.2s background ease-in-out;
        }
        .menu-item[hidden] {
          display: none;
        }
        .menu hr {
          width: 96%;
          margin: 0 2%;
          border: 0;
          height: 1px;
          background: hsl(0, 0%, 80%);
        }
        .menu a {
          cursor: pointer;
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
      <div class\$="menu [[menuAlignment]]">
        <template is="dom-repeat" items="[[items]]">
          <template is="dom-if" if="[[item.separator]]">
            <strong hidden\$="[[!item.text]]" class="menu-item">
              [[item.text]]
            </strong>
            <hr />
          </template>
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
        <slot></slot>
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
      icon: {
        type: String,
        value: 'arrow_drop_down',
      },
      menuAlignment: {
        type: String,
        value: 'right',
      },
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
        return node === this;
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
