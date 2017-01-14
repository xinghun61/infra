(function() {
  'use strict';

  const bugLinkRegExp = /([0-9]{3,})/;


  Polymer({
    is: 'som-alert-item',
    behaviors: [LinkifyBehavior],

    /**
     * Fired when an alert requests that the link bug dialog be shown.
     *
     * @event link-bug
     */

    /**
     * Fired when an alert requests that the snooze dialog be shown.
     *
     * @event snooze
     */

    /**
     * Fired when an alert has an annotation change that needs to be sent to the
     * server.
     *
     * @event annotation-change
     * @param {Object} changes The changes to be sent to the server.
     */

    properties: {
      alert: Object,
      examining: {
        type: Boolean,
        value: false,
      },
      tree: String,
      annotation: Object,
      _commentsClass: {
        type: String,
        computed: '_computeCommentsClass(_numComments)',
      },
      _cssClass: {
        type: String,
        computed: '_computeCssClass(annotation.snoozed)',
      },
      _duration: {type: String, computed: '_calculateDuration(alert)'},
      _hasBugs: {
        type: Boolean,
        computed: '_computeHasBugs(annotation.bugs)',
      },
      _latestTime: {type: String, computed: '_formatTimestamp(alert.time)'},
      _numComments: {
        type: Number,
        computed: '_computeNumComments(annotation.comments)',
      },
      _snoozeText: {
        type: String,
        computed: '_computeSnoozeText(annotation.snoozed)',
      },
      _snoozeIcon: {
        type: String,
        computed: '_computeSnoozeIcon(annotation.snoozed)',
      },
      _startTime:
          {type: String, computed: '_formatTimestamp(alert.start_time)'},
      useCompactView: Boolean,
    },

    _bugLabel: function(bug) {
      let bugId = bugLinkRegExp.exec(bug);

      return !!bugId[0] ? `Bug ${bugId[0]}` : bug;
    },

    _bugSummary: function(bug, bugData) {
      for (let i in bugData) {
        if (bug == bugData[i].id) {
          return bugData[i].summary;
        }
      }
      return '';
    },

    // This is for backwards compatibility with old bug data that is stored as
    // URLs rather than ids.
    _bugUrl: function(bug) {
      if (bug.indexOf('http') == 0) {
        return bug;
      }
      return 'https://crbug.com/' + bug;
    },

    _calculateDuration(alert) {
      let deltaSec = Math.round((alert.time - alert.start_time));
      let hours = Math.floor(deltaSec / 60 / 60);
      let minutes = Math.floor((deltaSec - hours * 60 * 60) / 60);
      let seconds = deltaSec - hours * 60 * 60 - minutes * 60;
      if (hours == 0 && minutes == 0 && seconds == 0) {
        return '';
      }
      return `Active for: ${hours}h ${minutes}m ${seconds}s`;
    },

    _helpLinkForAlert: function(alert) {
      // TODO(zhangtiff): Add documentation links for other kinds of alerts
      if (this._alertIsWebkit(alert)) {
        return 'http://www.chromium.org/blink/sheriffing';
      }
      return null;
    },

    _alertIsWebkit(alert) {
      // TODO(zhangtiff): Find a better way to categorize alerts
      return alert.key && alert.key.includes('chromium.webkit');
    },

    _classForAlert: function(alert, selected) {
      return 'alert' + (selected ? ' selected' : '');
    },

    _comment: function(evt) {
      this.fire('comment');
      evt.preventDefault();
    },

    _computeHasBugs: function(bugs) {
      return !!(bugs && bugs.length > 0);
    },

    _computeCommentsClass: function(numComments) {
      if (numComments > 0) {
        return 'comments-link-highlighted';
      }
      return 'comments-link';
    },

    _computeNumComments: function(comments) {
      if (comments) {
        return comments.length;
      }
      return 0;
    },

    _computeSnoozeText: function(snoozed) {
      return snoozed ? 'Unsnooze' : 'Snooze';
    },

    _computeCssClass: function(snoozed) {
      return snoozed ? 'snoozed' : '';
    },

    _computeSnoozeIcon: function(snoozed) {
      return snoozed ? 'alarm-off' : 'alarm';
    },

    _linkBug: function(evt) {
      this.fire('link-bug');
    },

    _formatTimestamp: function(timestamp) {
      if (timestamp != undefined) {
        return new Date(timestamp * 1000).toLocaleString();
      }
      return '';
    },

    _haveLinks: function(alert) {
      return alert && alert.links && alert.links.length > 0;
    },

    _removeBug: function(evt) {
      this.fire('annotation-change', {
        type: 'remove',
        change: {'bugs': [evt.model.bug]},
      });
    },

    _snooze: function(evt) {
      if (this.annotation.snoozed) {
        this.fire('annotation-change', {
          type: 'remove',
          change: {'snoozeTime': true},
        });
      } else {
        this.fire('snooze');
      }
      evt.preventDefault();
    },

    toggle: function(evt) {
      let path = evt.path;
      for (let i = 0; i < path.length; i++) {
        let itm = path[i];
        if (itm.classList && itm.classList.contains('bug')) {
          // Clicking on a bug shouldn't affect toggled state.
          return;
        }
      }

      this.fire('opened-change', {value: !this.annotation.opened});
    },

    _isHidden: function(opened, useCompactView) {
      if (!useCompactView) {
        return false;
      }

      return !opened;
    },
  });
})();
