(function() {
  'use strict';

  // Time, in milliseconds, between each refresh of data from the server.
  const refreshDelayMs = 60 * 1000;

  Polymer({
    is: 'som-app',
    behaviors: [AnnotationManagerBehavior, AlertTypeBehavior],
    properties: {
      _activeRequests: {
        type: Number,
        value: 0,
      },
      _alerts: {
        type: Array,
        value: function() {
          return [];
        },
        computed:
            '_computeAlerts(_alertsData.*, annotations, showInfraFailures, _isTrooperPage)',
      },
      // Map of stream to data, timestamp of latest updated data.
      _alertsData: {
        type: Object,
        value: function() {
          return {};
        },
      },
      _alertsTimes: {
        type: Object,
        value: function() {
          return {};
        },
      },
      _alertsGroups: {
        type: Array,
        computed: '_computeAlertsGroups(_tree, _trees)',
        observer: '_alertsGroupsChanged',
      },
      annotations: Object,
      _lastUpdated: {
        type: Date,
        computed: '_computeLastUpdated(_alertsTimes.*)',
      },
      _bugs: Array,
      _bugQueueLabel: {
        type: Array,
        computed: '_computeBugQueueLabel(_tree, _trees)',
      },
      _fetchAlertsError: String,
      _fetchingAlerts: {
        type: Boolean,
        computed: '_computeFetchingAlerts(_activeRequests)',
      },
      _fetchedAlerts: {
        type: Boolean,
        value: false,
      },
      _hideJulie: {
        type: Boolean,
        computed:
            '_computeHideJulie(_alerts, _fetchedAlerts, _fetchingAlerts, _fetchAlertsError, _tree)',
        value: true,
      },
      _isTrooperPage: {
        type: Boolean,
        computed: '_computeIsTrooperPage(_tree)',
        value: false,
      },
      logoutUrl: String,
      _pageTitleCount: {
        type: Number,
        computed: '_computePageTitleCount(_alerts, _bugs, _isTrooperPage)',
        observer: '_pageTitleCountChanged',
      },
      _path: {
        type: String,
      },
      _helpLink: {
        type: String,
        computed: '_computeHelpLink(_tree, _trees)',
      },
      _refreshEnabled: {
        type: Boolean,
        computed: '_computeRefreshEnabled(_selectedPage)',
      },
      _selectedPage: {
        type: String,
        computed: '_computeSelectedPage(_path)',
      },
      _showRotationCalendar: {
        type: Boolean,
        value: false,
      },
      showInfraFailures: Boolean,
      _showSwarmingAlerts: {
        type: Boolean,
        computed: '_computeShowSwarmingAlerts(_swarmingAlerts, _isTrooperPage)',
      },
      _swarmingAlerts: {
        type: Object,
        value: function() {
          return {};
        },
      },
      _trees: Object,
      _tree: {
        type: String,
        computed: '_computeTree(_path)',
        observer: '_treeChanged',
      },
      _treeDisplayName: {
        type: String,
        computed: '_computeTreeDisplayName(_tree, _trees)',
      },
      _treeLogo: {
        type: String,
        computed: '_computeTreeLogo(_tree, _trees)',
      },
      _sections: {
        type: Object,
        value: {
          // The order the sections appear in the array is the order they
          // appear on the page.
          'default': ['notifications', 'bugQueue', 'alertsList'],
          'trooper': ['notifications', 'bugQueue', 'swarmingBots', 'alertsList']
        },
      },
      _staticPages: {
        type: Object,
        value: {
          'help-som': {
            pageId: 'helpSOM',
            displayText: 'How to Use',
          },
          'calendar': {
            pageId: 'rotationCalendar',
            displayText: 'Rotation Calendar',
          }
        },
      },
      _examinedAlert: {
        type: Object,
        computed: '_computeExaminedAlert(_alerts, _examinedAlertKey)',
      },
      _examinedAlertKey: {
        type: String,
        computed: '_computeExaminedAlertKey(_path)',
      },
      user: String,
      useCompactView: Boolean,
      linkStyle: String,
      xsrfToken: String,
    },

    created: function() {
      this.async(this._refreshAsync, refreshDelayMs);
    },

    ////////////////////// Refresh ///////////////////////////

    _refresh: function() {
      if (!this._refreshEnabled) {
        return;
      }
      this.$.annotations.fetch();
      this.$.bugQueue.refresh();
      this.$.masterRestarts.refresh();
      this.$.treeStatus.refresh();
      this.$.drawer.refresh();
      this._alertsGroupsChanged(this._alertsGroups);
    },

    _refreshAsync: function() {
      this._refresh();
      this.async(this._refreshAsync, refreshDelayMs);
    },

    ////////////////////// Alerts and path ///////////////////////////

    _computeBugQueueLabel: function(tree, trees) {
      if (tree in trees) {
        return trees[tree].bug_queue_label;
      }
      return '';
    },

    _computeHelpLink: function(tree, trees) {
      if (tree in trees) {
        return trees[tree].help_link;
      }
      return '';
    },

    _computeIsTrooperPage: function(tree) {
      return tree === 'trooper';
    },

    _pageTitleCountChanged: function(count) {
      if (count > 0) {
        document.title = '(' + count + ') Sheriff-o-Matic';
      } else {
        document.title = 'Sheriff-o-Matic';
      }
    },

    _computePageTitleCount: function(alerts, bugs, isTrooperPage) {
      if (isTrooperPage && bugs) {
        return bugs.length;
      } else if (!isTrooperPage && alerts) {
        return alerts.length;
      }
      return 0;
    },

    _computeShowSwarmingAlerts: function(swarming, isTrooperPage) {
      return isTrooperPage && swarming &&
          (swarming.dead || swarming.quarantined);
    },

    _computeTree: function(path) {
      let pathParts = path.split('/');
      if (pathParts.length < 2 || pathParts[1] == '') {
        return '';
      }

      return pathParts[1];
    },

    _computeTreeLogo: function(tree, trees, errored) {
      if (!errored && tree in trees) {
        return `/logos/${tree}`;
      }
      return null;
    },

    _computeTreeDisplayName: function(tree, trees) {
      if (tree in trees) {
        return trees[tree].display_name;
      }
      return tree;
    },

    _treeChanged: function(tree) {
      this._alertsData = {};
      this._fetchedAlerts = false;

      // Reorder sections on page based on per tree priorities.
      let sections = this._sections[tree] || this._sections.default;
      for (let i in sections) {
        this.$$('#' + sections[i]).style.order = i;
      }
    },

    _computeAlertsGroups: function(tree, trees) {
      if (tree === '' || tree in this._staticPages ||
          Object.keys(trees).length == 0) {
        return [];
      }

      if (trees && trees[tree] && trees[tree].alert_streams) {
        return trees[tree].alert_streams
      }

      return [tree];
    },

    _computeRefreshEnabled: function(selectedPage) {
      return selectedPage == 'mainView';
    },

    _computeSelectedPage: function(path) {
      let pathParts = path.split('/');
      if (pathParts.length < 2 || pathParts[1] == '') {
        // Default page
        return 'help-som';
      }
      if (pathParts.length == 2) {
        if (pathParts[1] in this._staticPages) {
          if (pathParts[1] === 'calendar') {
            // Hide rotation calendar until visited because it's really big.
            this._showRotationCalendar = true;
          }
          return this._staticPages[pathParts[1]].pageId;
        } else {
          // On the page for a tree
          return 'mainView';
        }
      }
      if (pathParts[2] == 'examine') {
        return 'examineAlert';
      }
    },

    _computeExaminedAlertKey: function(path) {
      let pathParts = path.split('/');
      if (pathParts.length < 2) {
        console.error('error: pathParts < 2', pathParts);
      }

      if (pathParts.length < 3) {
        return '';
      }

      if (pathParts[2] == 'examine') {
        if (pathParts.length > 3) {
          // Let som-examine element deal with the rest of the path.
          return window.unescape(pathParts.slice(3).join('/'));
        }
      }
    },

    _computeExaminedAlert: function(alerts, examinedAlertKey) {
      let examinedAlert = alerts.find((alert) => {
        return alert.key == examinedAlertKey;
      });
      // Two possibilities if examinedAlert is undefined:
      // 1. The alert key is bad.
      // 2. Alerts has not been ajaxed in yet.
      if (examinedAlert) {
        return examinedAlert;
      }
      return {};
    },

    _computeLastUpdated: function(alertsTimes) {
      alertsTimes = alertsTimes.base;

      // Alert streams are assumed to be always older than right now.
      let oldestDate = new Date();
      Object.keys(alertsTimes).forEach((tree) => {
        if (alertsTimes[tree] < oldestDate) {
          oldestDate = alertsTimes[tree];
        }
      });

      // Assume it takes less than 1 millisecond to calculate that.
      if (Date.now() - oldestDate > 1) {
        let date = moment(oldestDate * 1000).tz('America/Los_Angeles');
        return {
          'time': date.format('M/DD/YYYY, h:mm a z'),
          'relativeTime': date.fromNow()
        };
      }
      return null;
    },

    _alertsGroupsChanged: function(alertsGroups) {
      this._fetchAlertsError = '';
      if (alertsGroups.length > 0) {
        this._fetchedAlerts = false;
        this._activeRequests += alertsGroups.length;

        alertsGroups.forEach((group) => {
          let base = '/api/v1/alerts/';
          if (window.location.href.indexOf('useMilo') != -1) {
            base = base + 'milo.';
          }
          window.fetch(base + group, {credentials: 'include'})
              .then(
                  (response) => {
                    this._activeRequests -= 1;
                    if (response.status == 404) {
                      this._fetchAlertsError = 'Server responded with 404: ' +
                          group + ' not found. ';
                      return false;
                    }
                    if (!response.ok) {
                      this._fetchAlertsError = 'Server responded with ' +
                          response.status + ': ' + response.statusText;
                      return false;
                    }
                    return response.json();
                  },
                  (error) => {
                    this._activeRequests -= 1;
                    this._fetchAlertsError =
                        'Could not connect to the server. ' + error;
                  })
              .then((json) => {
                if (json) {
                  this.set('_swarmingAlerts', json.swarming);
                  this.set(
                      ['_alertsData', this._alertGroupVarName(group)],
                      json.alerts);

                  this._alertsTimes = {};
                  this.set(
                      ['_alertsTimes', this._alertGroupVarName(group)],
                      json.timestamp);
                }
              });
        });
      }
    },

    _alertGroupVarName(group) {
      return group.replace('.', '_');
    },

    _computeFetchingAlerts: function(activeRequests) {
      return activeRequests !== 0;
    },

    _countBuilders: function(alert) {
      if (alert.grouped && alert.alerts) {
        let count = 0;
        for (let i in alert.alerts) {
          count += this._countBuilders(alert.alerts[i]);
        }
        return count;
      } else if (alert.extension && alert.extension.builders) {
        return alert.extension.builders.length;
      } else {
        return 1;
      }
    },

    _computeAlerts: function(
        alertsData, annotations, showInfraFailures, isTrooperPage) {
      if (!alertsData || !alertsData.base) {
        return [];
      }
      alertsData = alertsData.base;

      let allAlerts = [];
      for (let tree in alertsData) {
        let alerts = alertsData[tree];
        if (!alerts) {
          continue;
        }

        if (!isTrooperPage && !showInfraFailures) {
          alerts = alerts.filter(function(alert) {
            return alert.type !== 'infra-failure';
          });
        }

        let alertItems = [];
        let groups = {};
        for (let i in alerts) {
          let alert = alerts[i];
          let ann = this.computeAnnotation(annotations, alert);
          if (ann.groupID) {
            if (!(ann.groupID in groups)) {
              let group = {
                key: ann.groupID,
                title: ann.groupID,
                body: ann.groupID,
                severity: alert.severity,
                time: alert.time,
                start_time: alert.start_time,
                links: [],
                tags: [],
                type: alert.type,
                extension: {stages: [], builders: [], grouped: true},
                grouped: true,
                alerts: [],
              }

              // Group name is stored using the groupID annotation.
              let groupAnn = this.computeAnnotation(annotations, group);
              if (groupAnn.groupID) {
                group.title = groupAnn.groupID;
              }

              groups[ann.groupID] = group;
              alertItems.push(group);
            }
            let group = groups[ann.groupID];
            if (alert.severity < group.severity) {
              group.severity = alert.severity;
            }
            if (alert.time > group.time) {
              group.time = alert.time;
            }
            if (alert.start_time < group.start_time) {
              group.start_time = alert.start_time;
            }
            group.links = group.links.concat(alert.links);
            group.tags = group.tags.concat(alert.tags);
            if (alert.extension) {
              this._mergeStages(group.extension.stages, alert.extension.stages,
                                alert.extension.builders);
              this._mergeBuilders(group.extension.builders,
                                  alert.extension.builders,
                                  alert.extension.stages);
            }
            group.alerts.push(alert);
          } else {
            // Ungrouped alert.
            alertItems.push(alert);
          }
        }
        allAlerts = allAlerts.concat(alertItems);
      }

      if (!allAlerts) {
        return [];
      }

      allAlerts.sort((a, b) => {
        let aAnn = this.computeAnnotation(annotations, a);
        let bAnn = this.computeAnnotation(annotations, b);

        let aHasBugs = aAnn.bugs && aAnn.bugs.length > 0;
        let bHasBugs = bAnn.bugs && bAnn.bugs.length > 0;

        let aBuilders = this._countBuilders(a);
        let bBuilders = this._countBuilders(b);

        let aHasSuspectedCLs = a.extension && a.extension.suspected_cls;
        let bHasSuspectedCLs = b.extension && b.extension.suspected_cls;
        let aHasFindings = a.extension && a.extension.has_findings;
        let bHasFindings = b.extension && b.extension.has_findings;

        if (a.severity != b.severity) {
          // Note: 3 is the severity number for Infra Failures.
          // We want these at the bottom of the severities for sheriffs.
          if (a.severity == AlertSeverity.InfraFailure) {
            return 1;
          } else if (b.severity == AlertSeverity.InfraFailure) {
            return -1;
          }

          // 7 is the severity for offline builders. Note that we want these to
          // appear above infra failures.
          if (a.severity == 7) {
            return 1;
          } else if (b.severity == 7) {
            return -1;
          }
          return a.severity - b.severity;
        }

        // TODO(davidriley): Handle groups.

        if (aAnn.snoozed == bAnn.snoozed && aHasBugs == bHasBugs) {
          // We want to show alerts with Findit results above.
          // Show alerts with revert CL from Findit first;
          // the alerts with suspected_cls;
          // then alerts with flaky tests;
          // then alerts with no Findit results.
          if (aHasSuspectedCLs && bHasSuspectedCLs) {
            for (let key in b.extension.suspected_cls) {
              if (b.extension.suspected_cls[key].reverting_cl_url) {
                return 1;
              }
            }
            return -1;
          } else if (aHasSuspectedCLs) {
            return -1;
          } else if (bHasSuspectedCLs) {
            return 1;
          } else if (aHasFindings) {
            return -1;
          } else if (bHasFindings) {
            return 1;
          }

          if (aBuilders < bBuilders) {
            return 1;
          }
          if (aBuilders > bBuilders) {
            return -1;
          }
          if (a.title < b.title) {
            return -1;
          }
          if (a.title > b.title) {
            return 1;
          }
          return 0;
        } else if (aAnn.snoozed == bAnn.snoozed) {
          return aHasBugs ? 1 : -1;
        }

        return aAnn.snoozed ? 1 : -1;
      });

      // Wait for alerts to be loaded
      setTimeout(() => {
        this._fetchedAlerts = true;
      }, 200);
      return allAlerts;
    },

    _mergeExtensions: function(extension) {
      if (!this._haveGrouped(extension)) {
        return extension;
      }

      // extension is a list of extensions.
      let mergedExtension = {stages: [], builders:[]};
      for (let i in extension) {
        let subExtension = extension[i];
        this._mergeStages(mergedExtension.stages, subExtension.stages,
                          subExtension.builders);
        this._mergeBuilders(mergedExtension.builders, subExtension.builders,
                            subExtension.stages);
      }

      return mergedExtension;
    },

    _mergeStages: function(mergedStages, stages, builders) {
      for (let i in stages) {
        this._mergeStage(mergedStages, stages[i], builders);
      }
    },

    _mergeStage: function(mergedStages, stage, builders) {
      let merged = mergedStages.find((s) => {
        return s.name == stage.name;
      });

      if (!merged) {
        merged = {
          name: stage.name,
          status: stage.status,
          logs: [],
          links: [],
          notes: stage.notes,
          builders: [],
        };

        mergedStages.push(merged);
      }
      if (stage.status != merged.status && stage.status == 'failed') {
        merged.status = 'failed';
      }

      // Only keep notes that are in common between all builders.
      merged.notes = merged.notes.filter(function(n) {
        return stage.notes.indexOf(n) !== -1;
      });

      merged.builders = merged.builders.concat(builders);
    },

    _mergeBuilders: function(mergedBuilders, builders, stages) {
      for (let i in builders) {
        this._mergeBuilder(mergedBuilders, builders[i], stages);
      }
    },

    _mergeBuilder: function(mergedBuilders, builder, stages) {
      let merged = mergedBuilders.find((b) => {
        // TODO: In the future actually merge these into a single entry.
        return b.name == builder.name &&
               b.first_failure == builder.first_failure &&
               b.latest_failure == builder.latest_failure;
      });

      if (!merged) {
        merged = Object.assign({stages: []}, builder);
        mergedBuilders.push(merged);
      }

      merged.start_time = Math.min(merged.start_time, builder.start_time);
      merged.first_failure = Math.min(merged.first_failure,
                                      builder.first_failure);
      if (builder.latest_failure > merged.latest_failure) {
        merged.url = builder.url;
        merged.latest_failure = builder.latest_failure;
      }

      merged.stages = merged.stages.concat(stages);
    },


    _computeHideJulie: function(
        alerts, fetchedAlerts, fetchingAlerts, fetchAlertsError, tree) {
      if (fetchingAlerts || !fetchedAlerts || !alerts ||
          fetchAlertsError !== '' || tree === '') {
        return true;
      }
      return alerts.length > 0;
    },

    ////////////////////// Alert Categories ///////////////////////////

    _alertItemsWithCategory: function(
        alerts, annotations, category, isTrooperPage) {
      return alerts.filter(function(alert) {
        if (isTrooperPage) {
          return alert.tree == category;
        } else if (category == AlertSeverity.InfraFailure) {
          // Put trooperable alerts into "Infra failures" on sheriff views
          return this.isTrooperAlertType(alert.type) || alert.severity == category;
        }
        return alert.severity == category;
      }, this);
    },

    _computeCategories: function(alerts, isTrooperPage) {
      let categories = [];
      alerts.forEach(function(alert) {
        let cat = alert.severity;
        if (isTrooperPage) {
          cat = alert.tree;
        } else if (this.isTrooperAlertType(alert.type)) {
          // When not on /trooper, collapse all of the trooper alerts into
          // the "Infra failures" category.
           cat = AlertSeverity.InfraFailure;
        }
        if (!categories.includes(cat)) {
          categories.push(cat);
        }
      }, this);

      return categories;
    },

    _getCategoryTitle: function(category, isTrooperPage) {
      if (isTrooperPage) {
        return this._computeTreeDisplayName(category, this._trees)
          + ' infra failures';
      }
      return {
        0: 'Tree closers',
        1: 'Stale masters',
        2: 'Probably hung builders',
        3: 'Infra failures',
        4: 'Consistent failures',
        5: 'New failures',
        6: 'Idle builders',
        7: 'Offline builders',
        // Chrome OS alerts
        1000: 'CQ failures',
        1001: 'PFQ failures',
        1002: 'Canary failures',
        1003: 'Release branch failures',
        1004: 'Chrome PFQ informational failures',
        1005: 'Chromium PFQ informational failures',
      }[category];
    },

    _getCategoryCount: function(alerts, category, isTrooperPage) {
      let count = 0;
      alerts.forEach(function(alert) {
        let cat = alert.severity;
        if (isTrooperPage) {
          cat = alert.tree;
        } else if (this.isTrooperAlertType(alert.type)) {
          // Collapse all of these into "Infra failures".
          cat = AlertSeverity.InfraFailure;
        }
        if (category == cat) {
          count++;
        }
      }, this);
      return count;
    },


    ////////////////////// Annotations ///////////////////////////

    collapseAll: function(evt) {
      if (!this.useCompactView) {
        return;
      }

      this.mutateLocalState((newState) => {
        let cat = evt.model.dataHost.dataHost.cat;
        this._alertItemsWithCategory(this._alerts, this.annotations,
                                     cat, this._isTrooperPage)
            .forEach((alr) => {
              newState[alr.key] =
                  Object.assign(newState[alr.key] || {}, {opened: false});
            });
      });
    },

    expandAll: function(evt) {
      if (!this.useCompactView) {
        return;
      }

      this.mutateLocalState((newState) => {
        let cat = evt.model.dataHost.dataHost.cat;
        this._alertItemsWithCategory(this._alerts, this.annotations, 
                                     cat, this._isTrooperPage)
            .forEach((alr) => {
              newState[alr.key] =
                  Object.assign(newState[alr.key] || {}, {opened: true});
            });
      });
    },

    _computeGroupTargets: function(alert, alerts) {
      // Valid group targets:
      // - must be of same type
      // - must not be with itself
      // - must not consist of two groups
      return alerts.filter((a) => {
        return a.type == alert.type && a.key != alert.key &&
               (!alert.grouped || !a.grouped);
      });
    },

    _handleOpenedChange: function(evt) {
      this.$.annotations.handleOpenedChange(evt);
    },

    _handleAnnotation: function(evt) {
      this.$.annotations.handleAnnotation(evt);
    },

    _handleComment: function(evt) {
      this.$.annotations.handleComment(evt);
    },

    _handleLinkBug: function(evt) {
      this.$.annotations.handleLinkBug(evt);
    },

    _handleSnooze: function(evt) {
      this.$.annotations.handleSnooze(evt);
    },

    _handleGroup: function(evt) {
      this.$.annotations.handleGroup(
          evt, this._computeGroupTargets(evt.target.alert, this._alerts));
    },

    _handleUngroup: function(evt) {
      this.$.annotations.handleUngroup(evt);
    },

    _handleResolve: function(evt) {
      if (evt.target.alert.grouped) {
        this._resolveAlerts(evt.target.tree, evt.target.alert.alerts);
      } else {
        this._resolveAlerts(evt.target.tree, [evt.target.alert]);
      }
    },

    _resolveAlerts: function(tree, alerts) {
      let url = '/api/v1/resolve/' + encodeURIComponent(tree);
      let keys = alerts.map((a) => {
        return a.key;
      });
      let request = {
        'keys': keys,
        'resolved': true,
      }
      this.$.annotations
          .postJSON(url, request)
          .then(jsonParsePromise)
          .then(this._resolveResponse.bind(this));
    },

    _resolveResponse: function(response) {
      if (response.resolved) {
        let alerts = this._alertsData[response.tree];
        alerts = alerts.filter(function(alert) {
          return !response.keys.find((key) => {
            return alert.key == key;
          });
        });
        // Ensure that the modification is captured.
        this.set(['_alertsData', response.tree], alerts);
      }
      return response;
    },

  });
})();
