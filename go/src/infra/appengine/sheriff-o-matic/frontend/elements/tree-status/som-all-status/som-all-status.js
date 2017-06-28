(function() {
  'use strict';

  Polymer({
    is: 'som-all-status',

    behaviors: [TreeStatusBehavior],

    properties: {
      trees: Object,
      _statusList: {
        type: Array,
        computed: '_computeStatusList(trees)',
      },
    },

    _computeStatusList(trees) {
      let result = [];
      for (let key in StatusApps) {
        let appData = {'key': key, 'name': this._capitalizeFirst(key)};
        if (key in trees) {
          appData.tree = trees[key];
        }
        result.push(appData);
      }
      return result;
    },

    _capitalizeFirst(s) {
      return s.charAt(0).toUpperCase() + s.slice(1);
    },
  });
})();
