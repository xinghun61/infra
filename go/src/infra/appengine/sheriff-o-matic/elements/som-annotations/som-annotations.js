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
      _bugInput: {
        type: Object,
        value: function() {
          return this.$.bug;
        }
      },
      _bugModel: Object,
      bugQueueLabel: String,
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
      _filedBug: {
        type: Boolean,
        value: false,
      },
      _removeBugErrorMessage: String,
      _removeBugModel: Object,
      _snoozeErrorMessage: String,
      _snoozeModel: Object,
      _snoozeTimeInput: {
        type: Object,
        value: function() {
          return this.$.snoozeTime;
        }
      },
      _groupErrorMessage: String,
      _groupInput: {
        type: Object,
        value: function() {
          return this.$.groupID;
        }
      },
      _groupModel: Object,
      _ungroupErrorMessage: String,
      _ungroupInput: {
        type: Object,
        value: function() {
          return '';
        }
      },
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
          .postJSON(
              '/api/v1/annotations/' + encodeURIComponent(key) + '/' + type,
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
      if (!annotationsJson) {
        annotationsJson = [];
      }

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

    handleOpenedChange: function(evt) {
      this.setLocalStateKey(evt.target.alert.key, {opened: evt.detail.value});
    },

    handleAnnotation: function(evt) {
      this.annotationError.action = 'Fetching all annotations';
      this.sendAnnotation(
              evt.target.alert.key, evt.detail.type, evt.detail.change)
          .then((response) => {
            this.setLocalStateKey(response.key, {opened: false});
          })
          .catch((error) => {
            let old = this.annotationError;
            this.annotationError.message = error;
            this.notifyPath('annotationError.message');
          });
    },

    handleComment: function(evt) {
      this._commentsModel = evt.target.alert;
      this._commentsErrorMessage = '';
      this.$.commentsDialog.open();
    },

    handleLinkBug: function(evt) {
      this._bugModel = evt.target.alert;
      this.$.fileBugLink.href =
          'https://bugs.chromium.org/p/chromium/issues/entry?status=Available&labels=' +
          this.bugQueueLabel + '&summary=' + this._bugModel.title +
          '&comment=' + encodeURIComponent(this._commentForBug(this._bugModel));
      this._filedBug = false;
      this._bugErrorMessage = '';
      this.$.bugDialog.open();
    },

    handleRemoveBug: function(evt) {
      this.$.removeBugDialog.open();
      this._removeBugModel = Object.assign({alert: evt.target.alert},
        evt.detail);
      this._removeBugErrorMessage = '';
    },

    handleSnooze: function(evt) {
      this._snoozeModel = evt.target.alert;
      this.$.snoozeTime.value = this._defaultSnoozeTime;
      this._snoozeErrorMessage = '';
      this.$.snoozeDialog.open();
    },

    handleGroup: function(evt, targets) {
      this._groupModel = {alert: evt.target.alert, targets: targets};
      this._groupErrorMessage = '';
      this.$.groupDialog.open();
    },

    handleUngroup: function(evt) {
      this._ungroupModel = evt.target.alert;
      this._ungroupErrorMessage = '';
      this.$.ungroupDialog.open();
    },

    ////////////////////// Bugs ///////////////////////////

    _commentForBug: function(bugModel) {
      let result = bugModel.title + '\n\n';
      if (bugModel.extension) {
        if (bugModel.extension.builders &&
            bugModel.extension.builders.length > 0) {
          result += 'Builders failed on: ';
          for (let i in bugModel.extension.builders) {
            result += '\n- ' + bugModel.extension.builders[i].name + ': \n  ' +
                bugModel.extension.builders[i].url;
          }
          result += '\n\n';
        }
        if (bugModel.extension.reasons &&
            bugModel.extension.reasons.length > 0) {
          result += 'Reasons: ';
          for (let i in bugModel.extension.reasons) {
            result += '\n' + bugModel.extension.reasons[i].url;
            if (bugModel.extension.reasons[i].test_names) {
              result += '\n' +
                  'Tests:';
              if (bugModel.extension.reasons[i].test_names) {
                result += '\n* ' +
                    bugModel.extension.reasons[i].test_names.join('\n* ');
              }
            }
          }
          result += '\n\n';
        }
      }
      return result;
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
      // TODO(add proper error handling)
      let data = {bugs: [this.$.bug.value]};
      if (this.$.autosnooze.checked) {
        data.snoozeTime = Date.now() + ONE_MIN_MS * this._defaultSnoozeTime;
      }
      this.sendAnnotation(this._bugModel.key, 'add', data)
          .then(
              (response) => {
                this._bugErrorMessage = '';
                this.$.bug.value = '';
                this.$.bugDialog.close();

                this.setLocalStateKey(response.key, {opened: false});
              },
              (error) => {
                this._bugErrorMessage = error;
              });
    },

    ////////////////////// Snooze ///////////////////////////

    _snooze: function() {
      // TODO(add proper error handling)
      this.sendAnnotation(
              this._snoozeModel.key, 'add',
              {snoozeTime: Date.now() + ONE_MIN_MS * this.$.snoozeTime.value})
          .then(
              (response) => {
                this.$.snoozeTime.value = '';
                this.$.snoozeDialog.close();

                this.setLocalStateKey(response.key, {opened: false});
              },
              (error) => {
                this._snoozeErrorMessage = error;
              });
    },

    ////////////////////// Comments ///////////////////////////

    _addComment: function() {
      if (this._commentInFlight) return;

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
                this.setLocalStateKey(response.key, {opened: false});
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
      return this.computeAnnotation(annotations, model);
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
        request.then(
            (response) => {
              this.setLocalStateKey(response.key, {opened: false});
            },
            (error) => {
              this._commentsErrorMessage = error;
            });
      }
    },

    ////////////////////// Groups ///////////////////////////

    _group: function() {
      this._groupErrorMessage = '';

      // Group the current alert and all checked alerts.
      let alerts = this._groupModel.targets.filter((t) => {
        return t.checked;
      });
      alerts.push(this._groupModel.alert);

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
        this.sendAnnotation(
                alerts[i].key, 'add',
                {group_id: groupID})
            .then(
                (response) => {
                  this.$.groupDialog.close();
                  alerts[i].checked = false;

                  this.setLocalStateKey(response.key, {opened: false});
                },
                (error) => {
                  this._groupErrorMessage = error;
                });
      }
    },

    _ungroup: function() {
      // TODO(add proper error handling)
      for (let i in this._ungroupModel.alerts) {
        if (!this._ungroupErrorMessage && this._ungroupModel.alerts[i].checked) {
          this.sendAnnotation(
                  this._ungroupModel.alerts[i].key, 'remove',
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

  })
})();
