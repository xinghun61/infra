'use strict';

class SomExamine extends Polymer.mixinBehaviors([LinkifyBehavior],
    Polymer.Element) {

  static get is() {
    return 'som-examine';
  }

  static get properties() {
    return {
      alert: {
        type: Object,
        value: function() {
          return {};
        },
        observer: '_alertChanged',
      },
      selectedStep: {
        type: String,
        value: '',
        observer: '_selectedStepChanged',
      },
      selectedTest: {
        type: String,
        value: '',
      },
      selectedBuilder: {
        type: String,
        value: '',
      },
      hideTests: {
        type: Boolean,
        value: true,
      },
      hideWebKitTests: {
        type: Boolean,
        value: true,
      }
    };
  }

  _alertChanged() {
    if (!this.alert || !this.alert.extension ||
        !this.alert.extension.builders) {
      return;
    }
    this.selectedBuilder = this._tabId(this.alert.extension.builders[0]);
    if (!this.alert.extension.reason) {
      return;
    }
    if (this.alert.extension.reason.name) {
      this.selectedStep = this.alert.extension.reason.name;
    } else if (this.alert.extension.reason.test_names) {
      this.selectedStep = 'tests';
    }
  }

  _selectedStepChanged() {
    if (!this.alert.extension || !this.alert.extension.reason) {
      return undefined;
    }
    let reason = this.alert.extension.reason;
    if (reason && reason.test_names) {
      this.hideTests = false;
      this.selectedTest = reason.test_names[0];
      // TODO(martiniss): put the failing step name back into the alert
      // JSON so we don't have to peek at the alert title to tell if
      // if the failing step is webkit_layout_tests.
      // TODO(crbug/706192): Remove the check for webkit_tests, once this
      // step name no longer exists.
      this.hideWebKitTests =
          !(this.alert.title.startsWith('webkit_tests') ||
            this.alert.title.startsWith('webkit_layout_tests'));
    } else {
      this.hideTests = true;
      this.hideWebKitTests = true;
    }
  }

  _tabId(builder) {
    return builder.name + ':' + builder.latest_failure;
  }

  _tabTitle(builder) {
    let title = builder.name;
    let numBuilds = builder.latest_failure - builder.first_failure + 1;
    if (numBuilds > 1) {
      return `${builder.name} (${numBuilds} builds)`;
    }
    return builder.name;
  }

  _computeFailingTests(builder, step) {
    if (!this.alert.extension || !this.alert.extension.reason) {
      return undefined;
    }
    let reason = this.alert.extension.reason;

    if (reason) {
      if (reason.test_names) {
        this.selectedTest = reason.test_names[0];
      }
      return reason.test_names;
    }
    return undefined;
  }
}

customElements.define(SomExamine.is, SomExamine);
