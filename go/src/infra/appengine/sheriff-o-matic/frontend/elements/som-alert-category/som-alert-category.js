(function() {
  'use strict';

  Polymer({
    is: 'som-alert-category',
    behaviors: [AnnotationManagerBehavior],
    properties: {
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
      linkStyle: String,
      xsrfToken: String,
    },

    ////////////////////// Annotations ///////////////////////////

    _computeCheckedAlerts: function(alerts, checkedAlertKeys) {
      let checkedAlerts = [];
      for (let i = 0; i < alerts.length; i++) {
        let key = alerts[i].key;
        if (key in checkedAlertKeys && checkedAlertKeys[key]) {
          checkedAlerts.push(alerts[i]);
        }
      }
      return checkedAlerts;
    },

    ////////////////////// Checking Alerts ///////////////////////////

    _handleChecked: function(evt) {
      let keys = {};
      let alerts = this.getElementsByClassName('alert-item');
      for (let i = 0; i < alerts.length; i++) {
        keys[alerts[i].alert.key] = alerts[i].checked;
      }
      this._checkedAlertKeys = {};
      this._checkedAlertKeys = keys;
    },

    uncheckAll: function(evt) {
      let alerts = this.getElementsByClassName('alert-item');
      for (let i = 0; i < alerts.length; i++) {
        alerts[i].checked = false;
      }

      this.$.checkAll.checked = false;
    },

    checkAll: function(evt) {
      let checked = evt.target.checked;
      let alerts = this.getElementsByClassName('alert-item');
      for (let i = 0; i < alerts.length; i++) {
        alerts[i].checked = checked;
      }
    },

    ////////////////////// Collapsing Alerts ///////////////////////////

    _collapseAll: function(evt) {
      let alerts = this.getElementsByClassName('alert-item');
      for (let i = 0; i < alerts.length; i++) {
        alerts[i].openState = 'closed';
      }
    },

    _expandAll: function(evt) {
      let alerts = this.getElementsByClassName('alert-item');
      for (let i = 0; i < alerts.length; i++) {
        alerts[i].openState = 'opened';
      }
      this._opened = true;
    },

    ////////////////////// Collapsing the Category ///////////////////////////

    _computeToggleIcon: function(opened) {
      return opened ? 'unfold-less' : 'unfold-more';
    },

    _initializeCollapseState: function(isInfraFailuresSection) {
      this._opened = !isInfraFailuresSection;
    },

    _toggleCategory: function(evt) {
      this._opened = !this._opened;
    },
  });
})();
