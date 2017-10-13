'use strict';

class TsTreeRow extends Polymer.Element {

  static get is() {
    return 'ts-tree-row';
  }

  static get properties() {
    return {
      tree: {
        type: Object,
        observer: 'refresh',
      },
    };
  }

  refresh() {
    if (!this.tree.status_url) {
      return;
    }
    this.$.treeStatusAjax.generateRequest();
  }
}

customElements.define(TsTreeRow.is, TsTreeRow);
