(function() {
  'use strict';

  const DEFAULT_SNOOZE_TIME_MIN = 60;
  const ONE_MIN_MS = 1000 * 60;

  Polymer({
    is: 'som-annotations',
    behaviors: [AnnotationManagerBehavior],
    properties: {
      // All alert annotations. Includes values from localState.
      annotations: {
        notify: true,
        type: Object,
        value: function() {
          return {};
        },
        computed: '_computeAnnotations(_annotationsResp, localState)'
      },
      annotationError: {
        type: Object,
        value: function() {
          return {};
        },
      },
      // The raw response from the server of annotations.
      _annotationsResp: {
        type: Array,
        value: function() {
          return [];
        },
      },
      _bugErrorMessage: String,
      _fileBugInput: {
        type: Object,
        value: function() {
          return this.$.bug;
        },
      },
      collapseByDefault: Boolean,
      _commentInFlight: Boolean,
      _commentsErrorMessage: String,
      _commentsModel: Object,
      _commentsModelAnnotation: {
        type: Object,
        computed:
            '_computeCommentsModelAnnotation(annotations, _commentsModel)',
      },
      _commentsHidden: {
        type: Boolean,
        computed: '_computeCommentsHidden(_commentsModelAnnotation)',
      },
      _commentTextInput: {
        type: Object,
        value: function() {
          return this.$.commentText;
        }
      },
      // TODO(zhangtiff): Change snooze time per tree.
      _defaultSnoozeTime: {
        type: Number,
        value: DEFAULT_SNOOZE_TIME_MIN,
      },
      _fileBugModel: Object,
      _fileBugCallback: Function,
      _fileBugLabels: {
        type: Array,
        computed: '_computeFileBugLabels(tree)',
        value: function() {
          return [];
        },
      },
      _filedBug: {
        type: Boolean,
        value: false,
      },
      _groupErrorMessage: String,
      _groupModel: Object,
      _removeBugErrorMessage: String,
      _removeBugModel: Object,
      _snoozeErrorMessage: String,
      _snoozeModel: Object,
      _snoozeCallback: Function,
      _snoozeTimeInput: {
        type: Object,
        value: function() {
          return this.$.snoozeTime;
        }
      },
      tree: {
        type: Object,
        value: function() {
          return {};
        },
      },
      _ungroupErrorMessage: String,
      _ungroupModel: Object,
      user: String,
      xsrfToken: String,
    },

    ready: function() {
      this.fetchAnnotations();
    },

    fetch: function() {
      this.annotationError.action = 'Fetching all annotations';
      this.fetchAnnotations().catch((error) => {
        let old = this.annotationError;
        this.annotationError.message = error;
        this.notifyPath('annotationError.message');
      });
    },

    // Fetches new annotations from the server.
    fetchAnnotations: function() {
      return window.fetch('/api/v1/annotations', {credentials: 'include'})
          .then(jsonParsePromise)
          .then((req) => {
            this._annotationsResp = [];
            this._annotationsResp = req;
          });
    },

    // Send an annotation change. Also updates the in memory annotation
    // database.
    // Returns a promise of the POST request to the server to carry out the
    // annotation change.
    sendAnnotation: function(key, type, change) {
      return this
          .postJSON('/api/v1/annotations/' + encodeURIComponent(key) + '/' +
                        type,
                    change)
          .then(jsonParsePromise)
          .then(this._postResponse.bind(this));
    },

    // FIXME: Move to common behavior if other code does POST requests.
    postJSON: function(url, data, options) {
      options = options || {};
      options.body = JSON.stringify({
        xsrf_token: this.xsrfToken,
        data: data,
      });
      options.method = 'POST';
      options.credentials = 'include';
      return new Promise((resolve, reject) => {
        window.fetch(url, options).then((value) => {
          if (!value.ok) {
            value.text().then((txt) => {
              if (!(value.status == 403 && txt.includes('token expired'))) {
                reject(txt);
                return;
              }

              // We need to refresh our XSRF token!
              window.fetch('/api/v1/xsrf_token', {credentials: 'include'})
                  .then((respData) => {
                    return respData.json();
                  })
                  .then((jsonData) => {
                    // Clone options because sinon.spy args from different calls
                    // to window.fetch clobber each other in this scenario.
                    let opts = JSON.parse(JSON.stringify(options));
                    this.xsrfToken = jsonData['token'];
                    opts.body = JSON.stringify({
                      xsrf_token: this.xsrfToken,
                      data: data,
                    });
                    window.fetch(url, opts).then(resolve, reject);
                  });
            });
            return;
          }

          resolve(value);
        }, reject);
      })

    },

    _computeAnnotations: function(annotationsJson, localState) {
      let annotations = {};
      annotationsJson = annotationsJson || [];

      Object.keys(localState).forEach((key) => {
        key = decodeURIComponent(key);
        annotations[key] = localState[key];
      });
      annotationsJson.forEach((annotation) => {
        // If we've already added something here through local state, copy that
        // over.
        let key = decodeURIComponent(annotation.key);
        if (annotations[key]) {
          Object.assign(annotation, annotations[key]);
        }
        annotations[key] = annotation;
      });
      return annotations;
    },

    _haveAnnotationError: function(annotationError) {
      return !!annotationError.base.message;
    },

    // Handle the result of the response of a post to the server.
    _postResponse: function(response) {
      let annotations = this.annotations;
      annotations[decodeURIComponent(response.key)] = response;
      let newArray = [];
      Object.keys(annotations).forEach((k) => {
        k = decodeURIComponent(k);
        newArray.push(annotations[k]);
      });
      this._annotationsResp = newArray;

      return response;
    },

    ////////////////////// Handlers ///////////////////////////

    handleOpenedChange: function(alert, detail) {
      this.setLocalStateKey(alert.key, {opened: detail.value});
    },

    handleAnnotation: function(alert, detail) {
      this.annotationError.action = 'Fetching all annotations';
      this.sendAnnotation(alert.key, detail.type, detail.change)
          .then((response) => {})
          .catch((error) => {
            let old = this.annotationError;
            this.annotationError.message = error;
            this.notifyPath('annotationError.message');
          });
    },

    handleComment: function(alert) {
      this._commentsModel = alert;
      this._commentsErrorMessage = '';
      this.$.commentsDialog.open();
    },

    handleLinkBug: function(alerts, callback) {
      this._fileBugCallback = callback;
      this._fileBugModel = alerts;

      let bugSummary = 'Bug filed from Sheriff-o-Matic';
      if (alerts) {
        if (alerts.length > 1) {
          bugSummary = `${alerts[0].title} and ${alerts.length - 1} other alerts`;
        } else if (alerts.length > 0) {
          bugSummary = alerts[0].title;
        }
      }
      this.$.fileBugLink.href =
          'https://bugs.chromium.org/p/chromium/issues/entry?status=Available&labels=' +
          this._fileBugLabels.join(',') + '&summary=' + bugSummary +
          '&comment=' + encodeURIComponent(this._commentForBug(this._fileBugModel));
      this._filedBug = false;
      this._bugErrorMessage = '';
      this.$.bugDialog.open();
    },

    handleRemoveBug: function(alert, detail) {
      this.$.removeBugDialog.open();
      this._removeBugModel = Object.assign({alert: alert}, detail);
      this._removeBugErrorMessage = '';
    },

    handleSnooze: function(alerts, callback) {
      this._snoozeCallback = callback;
      this._snoozeModel = alerts;
      this.$.snoozeTime.value = this._defaultSnoozeTime;
      this._snoozeErrorMessage = '';
      this.$.snoozeDialog.open();
    },

    handleGroup: function(alert, targets) {
      this._groupModel = {alert: alert, targets: targets};
      this._groupErrorMessage = '';
      this.$.groupDialog.open();
    },

    handleUngroup: function(alert) {
      this._ungroupModel = alert;
      this._ungroupErrorMessage = '';
      this.$.ungroupDialog.open();
    },

    ////////////////////// Bugs ///////////////////////////

    _commentForBug: function(alerts) {
      return alerts.reduce((comment, alert) => {
        let result = alert.title + '\n\n';
        if (alert.extension) {
          if (alert.extension.builders &&
              alert.extension.builders.length > 0) {
            result += 'Builders failed on: ';
            for (let i in alert.extension.builders) {
              result += '\n- ' + alert.extension.builders[i].name + ': \n  ' +
                        alert.extension.builders[i].url;
            }
            result += '\n\n';
          }
          if (alert.extension.reasons &&
              alert.extension.reasons.length > 0) {
            result += 'Reasons: ';
            for (let i in alert.extension.reasons) {
              result += '\n' + alert.extension.reasons[i].url;
              if (alert.extension.reasons[i].test_names) {
                result += '\n' +
                          'Tests:';
                if (alert.extension.reasons[i].test_names) {
                  result += '\n* ' +
                            alert.extension.reasons[i].test_names.join('\n* ');
                }
              }
            }
            result += '\n\n';
          }
        }
        return comment + result;
      }, '');
    },

    _fileBugClicked: function() {
      this._filedBug = true;
    },

    _removeBug: function() {
      let model = this._removeBugModel;
      let data = {bugs: [model.bug]};
      this.sendAnnotation(model.alert.key, 'remove', data)
          .then(
              (response) => {
                this.$.removeBugDialog.close();
                this._removeBugErrorMessage = '';
              },
              (error) => {
                this._removeBugErrorMessage = error;
              });
    },

    _saveBug: function() {
      let data = {bugs: [this.$.bug.value.trim()]};
      if (this.$.autosnooze.checked) {
        data.snoozeTime = Date.now() + ONE_MIN_MS * this._defaultSnoozeTime;
      }
      let promises = this._fileBugModel.map((alert) => {
        return this.sendAnnotation(alert.key, 'add', data);
      });
      Promise.all(promises).then(
          (response) => {
            this._bugErrorMessage = '';
            this.$.bug.value = '';
            this.$.bugDialog.close();

            this.setLocalStateKey(response.key, {opened: false});

            if (this._fileBugCallback) {
              this._fileBugCallback();
            }
          },
          (error) => {
            this._bugErrorMessage = error;
          });
    },

    ////////////////////// Snooze ///////////////////////////

    _snooze: function() {
      let promises = this._snoozeModel.map(
          (alert) => {return this.sendAnnotation(alert.key, 'add', {
            snoozeTime: Date.now() + ONE_MIN_MS * this.$.snoozeTime.value
          })});
      Promise.all(promises).then(
          (response) => {
            this.$.snoozeTime.value = '';
            this.$.snoozeDialog.close();

            this.setLocalStateKey(response.key, {opened: false});

            if (this._snoozeCallback) {
              this._snoozeCallback();
            }
          },
          (error) => {
            this._snoozeErrorMessage = error;
          });
    },

    ////////////////////// Comments ///////////////////////////

    _addComment: function() {
      if (this._commentInFlight)
        return;

      let text = this.$.commentText.value;
      if (!(text && /[^\s]/.test(text))) {
        this._commentsErrorMessage = 'Comment text cannot be blank!';
        return;
      }
      this._commentInFlight = true;
      this.sendAnnotation(this._commentsModel.key, 'add', {
            comments: [text],
          })
          .then(
              (response) => {
                this.$.commentText.value = '';
                this._commentsErrorMessage = '';
                this._commentInFlight = false;
              },
              (error) => {
                this._commentsErrorMessage = error;
                this._commentInFlight = false;
              });
    },

    _computeCommentsHidden: function(annotation) {
      return !(annotation && annotation.comments);
    },

    // This is mostly to make sure the comments in the modal get updated
    // properly if changed.
    _computeCommentsModelAnnotation: function(annotations, model) {
      if (!annotations || !model) {
        return null;
      }
      return this.computeAnnotation(annotations, model, this.collapseByDefault);
    },

    _computeFileBugLabels: function(tree) {
      let labels = ['Filed-Via-SoM'];
      if (!tree) {
        return labels;
      }
      if (tree.name === 'android') {
        labels.push('Restrict-View-Google');
      }
      if (tree.bug_queue_label) {
        labels.push(tree.bug_queue_label);
      }
      return labels;
    },

    _computeHideDeleteComment(comment) {
      return comment.user != this.user;
    },

    _computeUsername(email) {
      if (!email) {
        return email;
      }
      let cutoff = email.indexOf('@');
      if (cutoff < 0) {
        return email;
      }
      return email.substring(0, cutoff);
    },

    _formatTimestamp: function(time) {
      if (!time) {
        return '';
      }
      return new Date(time).toLocaleString(false, {timeZoneName: 'short'});
    },

    _removeComment: function(evt) {
      let request = this.sendAnnotation(this._commentsModel.key, 'remove', {
        comments: [evt.model.comment.index],
      });
      if (request) {
        request.then((response) => {}, (error) => {
          this._commentsErrorMessage = error;
        });
      }
    },

    ////////////////////// Groups ///////////////////////////
    _group: function(evt) {
      // Group the current alert and all checked alerts.
      let alerts = this._groupModel.targets.filter((t) => {
        return t.checked;
      });
      alerts.push(this._groupModel.alert);

      this.group(alerts);
    },

    group: function(alerts) {
      this._groupErrorMessage = '';

      // Determine group ID.
      let groupAlert = null;
      for (let a in alerts) {
        if (alerts[a].grouped) {
          if (groupAlert) {
            this._groupErrorMessage = 'attempting to group multiple groups';
            return;
          }
          groupAlert = alerts[a];
        }
      }
      let groupID = groupAlert ? groupAlert.key : this._generateUUID();

      // Determine ungrouped alerts to group.
      alerts = alerts.filter((a) => {
        return !a.grouped;
      });

      // Create annotation for each ungrouped alert key.
      for (let i in alerts) {
        if (this._groupErrorMessage) {
          break;
        }
        this.sendAnnotation(alerts[i].key, 'add', {group_id: groupID})
            .then(
                (response) => {
                  this.$.groupDialog.close();
                  alerts[i].checked = false;
                },
                (error) => {
                  this._groupErrorMessage = error;
                });
      }
    },

    _ungroup: function() {
      // TODO(add proper error handling)
      for (let i in this._ungroupModel.alerts) {
        if (!this._ungroupErrorMessage &&
            this._ungroupModel.alerts[i].checked) {
          this.sendAnnotation(this._ungroupModel.alerts[i].key, 'remove',
                              {group_id: true})
              .then(
                  (response) => {
                    this.$.ungroupDialog.close();

                    this.setLocalStateKey(response.key, {opened: false});
                  },
                  (error) => {
                    this._ungroupErrorMessage = error;
                  });
          // TODO(davidriley): Figure out why things remain checked.
          this._ungroupModel.alerts[i].checked = false;
        }
      }
    },

    _haveSubAlerts: function(alert) {
      return alert.alerts && alert.alerts.length > 0;
    },

    _haveStages: function(alert) {
      return alert.extension && alert.extension.stages &&
             alert.extension.stages.length > 0;
    },

    _generateUUID: function() {
      // This is actually an rfc4122 version 4 compliant uuid taken from:
      // http://stackoverflow.com/questions/105034
      return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(
          /[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
          });
    },

    ////////////////////// Misc UX ///////////////////////////

    _checkAll: function(e) {
      let target = e.target;
      let checkboxSelector = target.getAttribute('data-checkbox-selector');
      let checkboxes = this.querySelectorAll(checkboxSelector);
      for (let i = 0; i < checkboxes.length; i++) {
        // Note: We are using .click() because otherwise the checkbox's change
        // event is not fired.
        if (checkboxes[i].checked != target.checked) {
          checkboxes[i].click();
        }
      }
    },

  })
})();
