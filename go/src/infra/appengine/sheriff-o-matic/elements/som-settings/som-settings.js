(function() {
  'use strict';

  Polymer({
    is: 'som-settings',

    properties: {
      defaultTree: {
        type: String,
        notify: true,
      },
      showInfraFailures: {
        type: Boolean,
        notify: true,
      },
      useCompactView: {
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
