(function() {
  'use strict';

  Polymer({
    is: 'som-swarming-bots',

    properties: {
      bots: {
        type: Object,
        value: function() {
          return {}
        },
      },
      _hideDeadBots: {
        type: Boolean,
        computed: '_computeHideBots(bots.dead)',
        value: true,
      },
      _hideErrors: {
        type: Boolean,
        computed: '_computeHideBots(bots.errors)',
        value: true,
      },
      _hideQuarantinedBots: {
        type: Boolean,
        computed: '_computeHideBots(bots.quarantined)',
        value: true,
      },
    },

    toggleDead: function() {
      this.$.deadBotsList.toggle();
    },

    toggleQuarantined: function() {
      this.$.quarantinedBotsList.toggle();
    },

    _computeHideBots: function(bots) {
      return !bots || bots.length == 0;
    },
  });
})();
