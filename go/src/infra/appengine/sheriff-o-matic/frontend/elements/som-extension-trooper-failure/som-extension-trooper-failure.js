'use strict';

class SomExtensionTrooperFailure extends Polymer.mixinBehaviors(
    [LinkifyBehavior, AlertTypeBehavior], Polymer.Element) {

  static get is() {
    return 'som-extension-trooper-failure';
  }

  static get properties() {
    return {
      treeName: String,
      type: {
        type: String,
        value: '',
      },
    };
  }

  _showSheriffMessage(type, treeName) {
    return treeName != 'trooper' && this.isTrooperAlertType(type);
  }

  _showTrooperMessage(type, treeName) {
    return treeName == 'trooper' && this.isTrooperAlertType(type);
  }
}

customElements.define(SomExtensionTrooperFailure.is, SomExtensionTrooperFailure);
