// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {LitElement, html, css} from 'lit-element';
import {ifDefined} from 'lit-html/directives/if-defined';

/**
 * `<mr-dropdown>`
 *
 * Dropdown menu for Monorail.
 *
 */
export class MrDropdown extends LitElement {
  static get styles() {
    return css`
      :host {
        position: relative;
        display: inline-block;
        height: 100%;
        font-size: inherit;
        --mr-dropdown-icon-color: var(--chops-primary-icon-color);
        --mr-dropdown-anchor-font-weight: initial;
        --mr-dropdown-anchor-padding: 4px 0.25em;
        --mr-dropdown-menu-max-height: initial;
        --mr-dropdown-menu-min-width: 120%;
        --mr-dropdown-menu-font-size: var(--chops-large-font-size);
        --mr-dropdown-menu-icon-size: var(--chops-icon-font-size);
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
        color: var(--mr-dropdown-icon-color);
        padding: 0 2px;
        box-sizing: border-box;
      }
      i.material-icons[hidden],
      .menu-item > i.material-icons[hidden] {
        display: none;
      }
      .menu-item > i.material-icons {
        display: block;
        font-size: var(--mr-dropdown-menu-icon-size);
        width: var(--mr-dropdown-menu-icon-size);
        height: var(--mr-dropdown-menu-icon-size);
        margin-right: 8px;
      }
      .anchor:disabled {
        color: var(--chops-button-disabled-color);
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
        padding: var(--mr-dropdown-anchor-padding);
        color: var(--chops-link-color);
        font-weight: var(--mr-dropdown-anchor-font-weight);
      }
      .menu.right {
        right: 0px;
      }
      .menu.left {
        left: 0px;
      }
      .menu {
        font-size: var(--mr-dropdown-menu-font-size);
        position: absolute;
        min-width: var(--mr-dropdown-menu-min-width);
        top: 90%;
        display: block;
        background: white;
        border: var(--chops-accessible-border);
        z-index: 990;
        box-shadow: 2px 3px 8px 0px hsla(0, 0%, 0%, 0.3);
        overflow: auto;
        max-height: var(--mr-dropdown-menu-max-height);
      }
      .menu-item {
        box-sizing: border-box;
        text-decoration: none;
        white-space: nowrap;
        display: flex;
        align-items: center;
        justify-content: left;
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
    `;
  }

  render() {
    return html`
      <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
      <button class="anchor" @click=${this.toggle}
        ?disabled=${this.disabled} aria-expanded=${this.opened}>
        ${this.text}
        <i class="material-icons">${this.icon}</i>
      </button>
      <div class="menu ${this.menuAlignment}">
        ${this.items.map((item, index) => html`
          ${item.separator ? html`
            <strong ?hidden=${!item.text} class="menu-item">
              ${item.text}
            </strong>
            <hr />
          ` : html`
            <a
              href=${ifDefined(item.url)}
              @click=${this._onClick}
              @keydown=${this._onClick}
              data-idx=${index}
              tabindex="0"
              class="menu-item"
            >
              <i
                class="material-icons"
                ?hidden=${item.icon === undefined}
              >${item.icon}</i>
              ${item.text}
            </a>
          `}
        `)}
        <slot></slot>
      </div>
    `;
  }

  constructor() {
    super();

    this.text = '';
    this.items = [];
    this.icon = 'arrow_drop_down';
    this.menuAlignment = 'right';
    this.opened = false;
    this.disabled = false;

    this._boundCloseOnOutsideClick = this._closeOnOutsideClick.bind(this);
  }

  static get properties() {
    return {
      text: {type: String},
      items: {type: Array},
      icon: {type: String},
      menuAlignment: {type: String},
      opened: {type: Boolean, reflect: true},
      disabled: {type: Boolean},
    };
  }

  _onClick(e) {
    if (e instanceof MouseEvent || e.code === 'Enter') {
      const idx = e.target.dataset.idx;
      if (idx !== undefined && this.items[idx].handler) {
        this.items[idx].handler();
      }
      this.close();
    }
  }

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener('click', this._boundCloseOnOutsideClick, true);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener('click', this._boundCloseOnOutsideClick, true);
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

  /**
   * Click a specific item in mr-dropdown, using JavaScript. Useful for testing.
   *
   * @param {int} i index of the item to click.
   */
  clickItem(i) {
    const items = this.shadowRoot.querySelectorAll('.menu-item');
    items[i].click();
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
}

customElements.define('mr-dropdown', MrDropdown);
