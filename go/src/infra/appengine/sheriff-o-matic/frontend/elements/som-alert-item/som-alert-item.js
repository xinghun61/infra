(function() {
  'use strict';

  Polymer({
    is: 'som-alert-item',
    behaviors: [LinkifyBehavior, AlertTypeBehavior],

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
     * Fired when an alert requests that the group dialog be shown.
     *
     * @event group
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
      treeName: {
        type: String,
        value: '',
      },
      annotation: {
        type: Object,
        value: {},
      },
      selectedAlert: {
        tupe: String,
        value: '',
      },
      checked: {
        type: Boolean,
        value: false,
        observer: '_alertChecked',
      },
      openState: {
        type: String,
        value: '',
      },
      _bugs: {
        type: Array,
        computed: '_computeBugs(annotation)',
      },
      _commentsClass: {
        type: String,
        computed: '_computeCommentsClass(_numComments)',
      },
      _cssClass: {
        type: String,
        computed: '_computeCssClass(annotation.snoozed)',
      },
      _duration: {
        type: String,
        computed: '_calculateDuration(treeName, alert)'
      },
      _latestTime: {
        type: String,
        computed: '_formatTimestamp(alert.time)'
      },
      _numComments: {
        type: Number,
        computed: '_computeNumComments(annotation.comments)',
      },
      _snoozeText: {
        type: String,
        computed: '_computeSnoozeText(annotation.snoozed)',
      },
      _snoozeTimeLeft: {
        type: String,
        computed: '_computeSnoozeTimeLeft(annotation.snoozeTime)',
      },
      _snoozeIcon: {
        type: String,
        computed: '_computeSnoozeIcon(annotation.snoozed)',
      },
      _hasGroup: {
        type: Boolean,
        computed: '_computeHasGroup(treeName)',
      },
      _hasUngroup: {
        type: Boolean,
        computed: '_computeHasUngroup(alert)',
      },
      _hasResolve: {
        type: Boolean,
        computed: '_computeHasResolve(treeName)',
      },
      _isCollapsed: {
        type: Boolean,
        computed: '_computeIsCollapsed(openState, annotation, collapseByDefault)',
      },
      _startTime:
          {type: String, computed: '_formatTimestamp(alert.start_time)'},
      _groupNameInput: {
        type: Object,
        value: function() {
          return this.$.groupName;
        }
      },
      collapseByDefault: Boolean,
    },

    _alertChecked(isChecked) {
      this.fire('checked');
    },

    _computeBugs: function(annotation) {
      // bugData is a map with the bug ids used as keys.
      let bugs = annotation.bugs;
      if (!bugs) return [];
      return bugs.map((bug) => {
        if (annotation.bugData && bug in annotation.bugData) {
          return annotation.bugData[bug];
        }
        return {'id': bug};
      });
    },

    _calculateDuration(treeName, alert) {
      let date = moment(alert.start_time * 1000).tz('America/Los_Angeles');
      let duration =
          date.format('M/DD/YYYY, h:mm a z') + ' (' + date.fromNow() + ')';
      return duration;
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

    _comment: function(evt) {
      this.fire('comment');
      evt.preventDefault();
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

    _computeSnoozeTimeLeft: function(snoozeTime) {
      if (!snoozeTime)
        return '';
      let now = moment(new Date());
      let later = moment(snoozeTime);
      let duration = moment.duration(later.diff(now));
      let text = '';
      if (duration.hours()) {
        text += duration.hours() + 'h ';
      }
      if (duration.minutes()) {
        text += duration.minutes() + 'm ';
      }
      if (text == '') {
        text += duration.seconds() + 's ';
      }
      return text + 'left';
    },

    _computeCssClass: function(snoozed) {
      return snoozed ? 'snoozed' : '';
    },

    _computeSnoozeIcon: function(snoozed) {
      return snoozed ? 'alarm-off' : 'alarm';
    },

    _isCrOSTree: function(treeName) {
      return treeName && (treeName == 'chromeos' || treeName == 'gardener');
    },

    _computeHasUngroup: function(alert) {
      return alert && !!alert.grouped;
    },

    _computeHasResolve: function(treeName) {
      return this._isCrOSTree(treeName);
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

    _haveLinks: function(selected, alert) {
      let links = this._getLinks(selected, alert);
      return links && links.length > 0;
    },

    _removeBug: function(evt) {
      let bug = evt.model.bug;
      this.fire('remove-bug', {
        bug: String(bug.id),
        summary: bug.summary,
        url: 'https://crbug.com/' + bug.id,
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

    _group: function(evt) {
      this.fire('group');
    },

    _ungroup: function(evt) {
      this.fire('ungroup');
    },

    _resolve: function(evt) {
      this.fire('resolve');
    },

    _updateGroupName: function(evt) {
      let value = evt.detail.keyboardEvent.target.value;
      this.fire('annotation-change', {
        type: 'add',
        change: {'group_id': value},
      });
    },

    _haveSubAlerts: function(alert) {
      return alert && alert.alerts && alert.alerts.length > 0;
    },

    _getSelected: function(selected, alert) {
      if (!alert) {
        return selected;
      }

      if (selected && alert.grouped && alert.alerts) {
        // This alert is a group, search for the selected sub-alert.
        let subAlert = alert.alerts.find((a) => {
          return a.key == selected;
        });

        if (subAlert) {
          // Return the selected alert.
          return subAlert;
        }
      }

      return alert;
    },

    _getExtension: function(selected, alert) {
      return this._getSelected(selected, alert).extension;
    },

    _getLinks: function(selected, alert) {
      return this._getSelected(selected, alert).links;
    },

    _expandAlertCollapse: function() {
      this.$.alertCollapse.updateSize(String(this.$.alertCollapse.scrollHeight) + 'px');
    },

    _computeIsCollapsed: function(openState, annotation, collapseByDefault) {
      // If opened is not defined, fall back to defaults based on annotation
      // and collapseByDefault.
      if (openState == 'opened') {
        return false;
      } else if (openState == 'closed') {
        return true;
      }
      return annotation.snoozed || collapseByDefault;
    },

    _toggle: function(evt) {
      let path = evt.path;
      for (let i = 0; i < path.length; i++) {
        let itm = path[i];
        if (itm.classList && itm.classList.contains('no-toggle')) {
          // Clicking on a bug, checkbox, etc shouldn't affect toggled state.
          return;
        }
      }
      this.openState = this._isCollapsed ? 'opened' : 'closed';
    },
  });
})();
