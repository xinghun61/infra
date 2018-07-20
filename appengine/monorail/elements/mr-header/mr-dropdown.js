'use strict';

/**
 * `<mr-dropdown>`
 *
 * Dropdown menu for Monorail.
 *
 */
// TODO(zhangtiff): generalize this menu for other drop downs. Right
// now this is designed only for the login dropdown.
class MrDropdown extends Polymer.Element {
  static get is() {
    return 'mr-dropdown';
  }

  static get properties() {
    return {
      text: String,
      items: Array,
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
}

customElements.define(MrDropdown.is, MrDropdown);
