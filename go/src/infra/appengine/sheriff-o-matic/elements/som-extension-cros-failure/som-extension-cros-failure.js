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

    _haveNotes: function(extension) {
      return extension && extension.notes && extension.notes.length > 0;
    },

    _haveStages: function(extension) {
      return extension && extension.stages && extension.stages.length > 0;
    },

    _haveStageBuilders: function(stage) {
      return stage && stage.builders && stage.builders.length > 0;
    },

    _buildName: function(name, number) {
      return name + ':' + number;
    },

    _buildRange: function(builder) {
      if (builder.first_failure == builder.latest_failure) {
        return this._buildName(builder.name, builder.first_failure);
      } else {
        return this._buildName(builder.name, builder.first_failure) + "-" +
               this._buildName(builder.name, builder.latest_failure);
      }
    },

    _stageBuilderText: function(stage, builders) {
      if (!stage.builders) {
        return 'no stage.builders';
      }
      if (!builders) {
        return 'no builders';
      }
      return String(stage.builders.length) + ' of ' + String(builders.length) +
             ' builds (' +
             (stage.builders.length / builders.length * 100).toFixed(0) + '%)';
    },
  });
})();
