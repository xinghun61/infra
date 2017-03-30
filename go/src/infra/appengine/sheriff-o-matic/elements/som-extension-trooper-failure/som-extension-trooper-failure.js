(function() {
  'use strict';

  Polymer({
    is: 'som-extension-trooper-failure',
    behaviors: [LinkifyBehavior, AlertTypeBehavior],
    properties: {
      tree: String,
      type: {type: String, value: ''},
    },

    _showSheriffMessage: function(type, tree) {
      return tree != 'trooper' && this.isTrooperAlertType(type);
    },

    _showTrooperMessage: function(type, tree) {
      return tree == 'trooper' && this.isTrooperAlertType(type);
    },

  });
})();
