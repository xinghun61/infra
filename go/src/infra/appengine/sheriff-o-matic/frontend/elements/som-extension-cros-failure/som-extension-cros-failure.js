'use strict';
class SomExtensionCrosFailure extends Polymer.mixinBehaviors([TreeBehavior],
    Polymer.Element) {

  static get is() {
    return 'som-extension-cros-failure';
  }

  static get properties() {
    return {
      extension: {
        type: Object,
        value: null,
      },
      type: {
        type: String,
        value: '',
      },
    };
  }

  _classForStage(stage) {
    let classes = ['stage'];
    if (stage.status == 'failed') {
      classes.push('stage-failed');
    } else if (stage.status == 'forgiven') {
      classes.push('stage-forgiven');
    } else if (stage.status == 'timed out') {
      classes.push('stage-timed-out');
    }
    return classes.join(' ');
  }

  _haveNotes(extension) {
    return extension && extension.notes && extension.notes.length > 0;
  }

  _haveStages(extension) {
    return extension && extension.stages && extension.stages.length > 0;
  }

  _haveStageBuilders(stage) {
    return stage && stage.builders && stage.builders.length > 0;
  }

  _buildName(name, number) {
    return name + ':' + number;
  }

  _buildRange(builder) {
    if (builder.first_failure == builder.latest_failure) {
      return this._buildName(builder.name, builder.first_failure);
    } else {
      return this._buildName(builder.name, builder.first_failure) + '-' +
             this._buildName(builder.name, builder.latest_failure);
    }
  }

  _stageBuilderText(stage, builders) {
    if (!stage.builders) {
      return 'no stage.builders';
    }
    if (!builders) {
      return 'no builders';
    }
    return String(stage.builders.length) + ' of ' + String(builders.length) +
           ' builds (' +
           (stage.builders.length / builders.length * 100).toFixed(0) + '%)';
  }
}

customElements.define(SomExtensionCrosFailure.is, SomExtensionCrosFailure);
