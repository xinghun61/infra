(function() {
  'use strict';

  Polymer({
    is: 'som-settings',

    properties: {
      collapseByDefault: {
        type: Boolean,
        notify: true,
      },
      defaultTree: {
        type: String,
        notify: true,
      },
      showInfraFailures: {
        type: Boolean,
        notify: true,
      },
      linkStyle: {
        type: String,
        notify: true,
      },
    },

    _initializeUber: function(evt) {
      evt.target.value = 'uber';
    },
  });
})();
