(function() {
  'use strict';

  Polymer({
    is: 'som-extension-cros-failure',

    properties: {
      extension: {type: Object, value: null},
      type: {type: String, value: ''},
    },

    _isCrosFailure: function(type) {
      return type == 'cros-failure';
    },

    _classForStage: function(stage) {
      let classes = ['stage'];
      if (stage.status == 'failed') {
        classes.push('stage-failed');
      } else if (stage.status == 'forgiven') {
        classes.push('stage-forgiven');
      } else if (stage.status == 'timed out') {
        classes.push('stage-timed-out');
      }
      return classes.join(' ');
    },

    _haveStages: function(extension) {
      return extension && extension.stages && extension.stages.length > 0;
    },
  });
})();
