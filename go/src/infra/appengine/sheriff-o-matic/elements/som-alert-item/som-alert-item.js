(function() {
  'use strict';

  const bugLinkRegExp = /([0-9]{3,})/;


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
      tree: {type: String, value: function() { return ''; }},
      annotation: Object,
      selectedAlert: {
        tupe: String,
        value: '',
      },
      _commentsClass: {
        type: String,
        computed: '_computeCommentsClass(_numComments)',
      },
      _cssClass: {
        type: String,
        computed: '_computeCssClass(annotation.snoozed)',
      },
      _duration: {type: String, computed: '_calculateDuration(tree, alert)'},
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
        computed: '_computeHasGroup(tree)',
      },
      _hasUngroup: {
        type: Boolean,
        computed: '_computeHasUngroup(alert)',
      },
      _hasResolve: {
        type: Boolean,
        computed: '_computeHasResolve(tree)',
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

    _calculateDuration(tree, alert) {
      let date = moment(alert.start_time * 1000).tz('America/Los_Angeles');
      let duration =  date.format('M/DD/YYYY, h:mm a z') +
                      ' (' + date.fromNow() + ')';
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

    _computeSnoozeTimeLeft: function(snoozeTime) {
      if (!snoozeTime) return '';
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
      return text + 'left';
    },

    _computeCssClass: function(snoozed) {
      return snoozed ? 'snoozed' : '';
    },

    _computeSnoozeIcon: function(snoozed) {
      return snoozed ? 'alarm-off' : 'alarm';
    },

    _isCrOSTree: function(tree) {
      return tree && (tree == 'chromeos' || tree == 'gardener');
    },

    _computeHasGroup: function(tree) {
      return this._isCrOSTree(tree);
    },

    _computeHasUngroup: function(alert) {
      return alert && !!alert.grouped;
    },

    _computeHasResolve: function(tree) {
      return this._isCrOSTree(tree);
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
      return (selected || !alert.grouped) &&
             alert && alert.links && alert.links.length > 0;
    },

    _hideActions: function(alertType, tree) {
      return tree != 'trooper' && this.isTrooperAlertType(alertType);
    },

    _hideExamine: function(alertType, examining, tree) {
      return examining || this._hideActions(alertType, tree);
    },

    _removeBug: function(evt) {
      let bugId = evt.model.bug;
      this.fire('remove-bug', {
        bug: bugId,
        summary: this._bugSummary(bugId, this.annotation.bugData),
        url: this._bugUrl(bugId),
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

      if (alert.grouped && alert.alerts) {
        // This alert is a group, search for the selected sub-alert.
        let subAlert = alert.alerts.find((a) => {
          return a.key == selected;
        });

        if (subAlert) {
          // Return the selected alert.
          return subAlert;
        }

        // Return the group extensions.
        return alert;
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
      this.selectedAlert = '';
      this.$.alertCollapse.updateSize(String(this.$.alertCollapse.scrollHeight) + 'px');
    },

    toggle: function(evt) {
      let path = evt.path;
      for (let i = 0; i < path.length; i++) {
        let itm = path[i];
        if (itm.classList && itm.classList.contains('no-toggle')) {
          // Clicking on a bug shouldn't affect toggled state.
          return;
        }
      }

      this.fire('opened-change', {value: !this.annotation.opened});
    },
  });
})();
