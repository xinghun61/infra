'use strict';

class CrdxHeader extends Polymer.Element {

  static get is() {
    return 'crdx-header';
  }

  static get properties() {
    return {
      appTitle: {
        type: String,
        value: 'CRDX App',
      },
      currentPage: String,
      currentPageRoute: String,
      user: String,
      logoUrl: String,
      logoutUrl: String,
    };
  }
}

customElements.define(CrdxHeader.is, CrdxHeader);
