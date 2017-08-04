'use strict';

class SomAlertCategory extends Polymer.mixinBehaviors(
    [AnnotationManagerBehavior], Polymer.Element) {

  static get is() {
    return 'som-alert-category';
  }

  static get properties() {
    return {
      alerts: {
        type: Array,
        value: function() {
          return [];
        },
      },
      annotations: {
        type: Object,
        value: function() {
          return {};
        },
      },
      categoryTitle: String,
      treeName: String,
      _checkedAlertKeys: {
        type: Object,
        value: function() {
          return {};
        },
      },
      checkedAlerts: {
        type: Array,
        computed: '_computeCheckedAlerts(alerts, _checkedAlertKeys)',
        value: function() {
          return [];
        },
      },
      // Note that this is for collapsing individual alerts.
      collapseByDefault: {
        type: Boolean,
        value: false,
      },
      _toggleIcon: {
        type: String,
        computed: '_computeToggleIcon(_opened)',
      },
      tooltip: String,
      // Note that this is the collapsed state of the whole category.
      _opened: {
        type: Boolean,
        value: true,
      },
      isInfraFailuresSection: {
        type: Boolean,
        value: false,
        observer: '_initializeCollapseState',
      },
      isResolvedSection: {
        type: Boolean,
        value: false,
      },
      linkStyle: String,
      xsrfToken: String,
    };
  }

  ////////////////////// Annotations ///////////////////////////

  _computeCheckedAlerts(alerts, checkedAlertKeys) {
    return alerts.filter((alert) => {
      return alert.key in checkedAlertKeys && checkedAlertKeys[alert.key];
    });
  }

  ////////////////////// Checking Alerts ///////////////////////////

  _handleChecked(evt) {
    let keys = {};
    let alerts = Polymer.dom(this.root).querySelectorAll('.alert-item');
    for (let i = 0; i < alerts.length; i++) {
      let a = alerts[i];
      keys[a.alert.key] = a.checked;
    }
    this._checkedAlertKeys = keys;
  }

  uncheckAll(evt) {
    let alerts = Polymer.dom(this.root).querySelectorAll('.alert-item');
    for (let i = 0; i < alerts.length; i++) {
      alerts[i].checked = false;
    }

    this.$.checkAll.checked = false;
  }

  checkAll(evt) {
    let checked = evt.target.checked;
    let alerts = Polymer.dom(this.root).querySelectorAll('.alert-item');
    for (let i = 0; i < alerts.length; i++) {
      alerts[i].checked = checked;
    }
  }

  ////////////////////// Collapsing Alerts ///////////////////////////

  _collapseAll(evt) {
    let alerts = Polymer.dom(this.root).querySelectorAll('.alert-item');
    for (let i = 0; i < alerts.length; i++) {
      alerts[i].openState = 'closed';
    }
  }

  _expandAll(evt) {
    let alerts = Polymer.dom(this.root).querySelectorAll('.alert-item');
    for (let i = 0; i < alerts.length; i++) {
      alerts[i].openState = 'opened';
    }
    this._opened = true;
  }

  ////////////////////// Collapsing the Category ///////////////////////////

  _computeToggleIcon(opened) {
    return opened ? 'unfold-less' : 'unfold-more';
  }

  _initializeCollapseState(isInfraFailuresSection) {
    this._opened = !isInfraFailuresSection;
  }

  _toggleCategory(evt) {
    this._opened = !this._opened;
  }
}

customElements.define(SomAlertCategory.is, SomAlertCategory);
