(function() {
  'use strict';

  Polymer({
    is: 'som-extension-trooper-failure',
    behaviors: [LinkifyBehavior, AlertTypeBehavior],
    properties: {
      treeName: String,
      type: {
        type: String,
        value: '',
      },
    },

    _showSheriffMessage: function(type, treeName) {
      return treeName != 'trooper' && this.isTrooperAlertType(type);
    },

    _showTrooperMessage: function(type, treeName) {
      return treeName == 'trooper' && this.isTrooperAlertType(type);
    },

  });
})();
