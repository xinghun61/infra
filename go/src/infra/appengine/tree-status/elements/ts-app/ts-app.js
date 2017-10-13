'use strict';

class TsApp extends Polymer.Element {

  static get is() {
    return 'ts-app';
  }

  static get properties() {
    return {
      queryParams: Object,
      route: Object,
      _mainRouteIsActive: Boolean,
      _tree: {
        type: Object,
        computed: '_computeTree(_treeViewData.tree, _trees)',
      },
      _trees: {
        type: Array,
        value: function() {
          return window.trees;
        },
      },
      _treeViewData: Object,
    };
  }

  _capitalizeWords(s) {
    return s.replace(/\b\w/g, ch => ch.toUpperCase());
  }

  _computeTree(treeName, trees) {
    return trees.find((tree) => {
      return tree && tree.name == treeName;
    });
  }
}

customElements.define(TsApp.is, TsApp);
