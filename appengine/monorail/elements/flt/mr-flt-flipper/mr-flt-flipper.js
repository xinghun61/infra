'use strict';

// TODO(zhangtiff): Later on in our Polymerization cycle, we should merge this
// with the mr-flt-flipper used on the EZT issue page while keeping this component
// data-agnostic.
/**
 * `<mr-flt-flipper>`
 *
 * A view-only component for an issue flipper.
 *
 */
class MrFlipper extends Polymer.Element {
  static get is() {
    return 'mr-flt-flipper';
  }

  static get properties() {
    return {
      count: Number,
      index: Number,
      prevUrl: String,
      nextUrl: String,
    };
  }

  firePrevClick(evt) {
    this.dispatchEvent(new CustomEvent('click-prev'));
    if (this.prevUrl) {
      window.location.href = this.prevUrl;
    }
  }

  fireNextClick(evt) {
    this.dispatchEvent(new CustomEvent('click-next'));
    if (this.nextUrl) {
      window.location.href = this.nextUrl;
    }
  }
}

customElements.define(MrFlipper.is, MrFlipper);
