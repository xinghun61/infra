(function() {
  'use strict';

  Polymer({
    is: 'som-master-restarts',

    properties: {
      treeName: {
        type: String,
        observer: 'refresh',
      },
      _hasError: {
        type: Boolean,
        computed: '_computeHasError(_restartsErrorJson)',
        value: false,
      },
      _hideNotice: {
        type: Boolean,
        computed: '_computeHideNotice(_hasRestarts, _hasError)',
        value: true,
      },
      _restartsErrorJson: Object,
      _restartsJson: Object,
      _hasRestarts: {
        type: Boolean,
        value: false,
        computed: '_computeHasRestarts(_restartsJson)',
      },
      _restarts: {
        type: String,
        computed: '_computeRestarts(_restartsJson)',
      },
    },

    refresh: function() {
      this.$.masterRestarts.generateRequest();
    },

    _computeHasError: function(json) {
      return !!json && Object.keys(json).length > 0;
    },

    _computeHideNotice: function(hasRestarts, hasError) {
      return !hasRestarts || hasError;
    },

    _computeHasRestarts: function(json) {
      if (!json) {
        return false;
      }
      return Object.keys(json).length > 0;
    },

    _computeRestarts: function(json) {
      let restarts = [];
      if (!json) {
        return restarts;
      }

      Object.keys(json).forEach((master) => {
        let state = json[master];
        var tt = new Date(state.transition_time_utc).toLocaleString();
        restarts.push({
          master: master,
          desiredState: state.desired_state == 'running' ? 'restart'
                                                         : state.desired_state,
          transitionTime: tt
        })
      });
      return restarts;
    },
  });
})();
