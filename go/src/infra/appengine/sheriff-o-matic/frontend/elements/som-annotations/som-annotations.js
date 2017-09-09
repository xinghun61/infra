'use strict';

// Default snooze times per tree in minutes.
const DefaultSnoozeTimes = {
  'chromium.perf': 60 * 24,
  '*': 60,
};

const ONE_MIN_MS = 1000 * 60;

class SomAnnotations extends Polymer.mixinBehaviors(
    [AnnotationManagerBehavior, PostBehavior, AlertTypeBehavior], Polymer.Element) {

  static get is() {
    return 'som-annotations';
  }

  static get properties() {
    return {
      // All alert annotations. Includes values from localState.
      annotations: {
        notify: true,
        type: Object,
        value: function() {
          return {};
        },
        computed: '_computeAnnotations(_annotationsResp)',
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
      _fileBugInput: Object,
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
      _commentTextInput: Object,
      _defaultSnoozeTime: {
        type: Number,
        computed: '_computeDefaultSnoozeTime(tree.name)',
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
      _snoozeTimeInput: Object,
      tree: {
        type: Object,
        value: function() {
          return {};
        },
      },
      _ungroupErrorMessage: String,
      _ungroupModel: Object,
      user: String,
    };
  }

  ready() {
    super.ready();

    this._fileBugInput = this.$.bug;
    this._commentTextInput = this.$.commentText;
    this._snoozeTimeInput = this.$.snoozeTime;

    this.fetchAnnotations();
  }

  fetch() {
    this.annotationError.action = 'Fetching all annotations';
    this.fetchAnnotations().catch((error) => {
      let old = this.annotationError;
      this.annotationError.message = error;
      this.notifyPath('annotationError.message');
    });
  }

  // Fetches new annotations from the server.
  fetchAnnotations() {
    return window.fetch('/api/v1/annotations', {credentials: 'include'})
        .then(jsonParsePromise)
        .then((req) => {
          this._annotationsResp = [];
          this._annotationsResp = req;
        });
  }

  // Send an annotation change. Also updates the in memory annotation
  // database.
  // Returns a promise of the POST request to the server to carry out the
  // annotation change.
  sendAnnotation(key, type, change) {
    return this
        .postJSON('/api/v1/annotations/' + encodeURIComponent(key) + '/' +
                      type,
                  change)
        .then(jsonParsePromise)
        .then(this._postResponse.bind(this));
  }

  _computeAnnotations(annotationsJson) {
    let annotations = {};
    annotationsJson = annotationsJson || [];

    annotationsJson.forEach((ann) => {
      let key = decodeURIComponent(ann.key);
      annotations[key] = ann;
    });
    return annotations;
  }

  _haveAnnotationError(annotationError) {
    return !!annotationError.base.message;
  }

  // Handle the result of the response of a post to the server.
  _postResponse(response) {
    let annotations = this.annotations;
    annotations[decodeURIComponent(response.key)] = response;
    let newArray = [];
    Object.keys(annotations).forEach((k) => {
      k = decodeURIComponent(k);
      newArray.push(annotations[k]);
    });
    this._annotationsResp = newArray;

    return response;
  }

  ////////////////////// Handlers ///////////////////////////

  handleAnnotation(alert, detail) {
    this.annotationError.action = 'Fetching all annotations';
    this.sendAnnotation(alert.key, detail.type, detail.change)
        .then((response) => {})
        .catch((error) => {
          let old = this.annotationError;
          this.annotationError.message = error;
          this.notifyPath('annotationError.message');
        });
  }

  handleComment(alert) {
    this._commentsModel = alert;
    this._commentsErrorMessage = '';
    this.$.commentsDialog.open();
  }

  handleLinkBug(alerts, callback) {
    this._fileBugCallback = callback;
    this._fileBugModel = alerts;

    let bugSummary = 'Bug filed from Sheriff-o-Matic';
    let trooperBug = false;

    if (alerts) {
      trooperBug = alerts.some((alert) => {
        return this.isTrooperAlertType(alert.type);
      });
      if (alerts.length > 1) {
        bugSummary = `${alerts[0].title} and ${alerts.length - 1} other alerts`;
      } else if (alerts.length > 0) {
        bugSummary = alerts[0].title;
      }
    }

    let extras = '';
    if (trooperBug) {
      extras = '&template=Build%20Infrastructure';
    }

    this.$.fileBugLink.href =
        'https://bugs.chromium.org/p/chromium/issues/entry?status=Available&labels=' +
        this._fileBugLabels.join(',') + '&summary=' + bugSummary +
        '&comment=' + encodeURIComponent(this._commentForBug(this._fileBugModel)) + extras;
    this._filedBug = false;
    this._bugErrorMessage = '';

    let autosnoozeTime = parseInt(this.$.autosnoozeTime.value, 10);
    this.$.autosnoozeTime.value = autosnoozeTime || this._defaultSnoozeTime;
    this.$.bugDialog.open();
  }

  handleRemoveBug(alert, detail) {
    this.$.removeBugDialog.open();
    this._removeBugModel = Object.assign({alert: alert}, detail);
    this._removeBugErrorMessage = '';
  }

  handleSnooze(alerts, callback) {
    this._snoozeCallback = callback;
    this._snoozeModel = alerts;
    this._snoozeErrorMessage = '';
    this.$.snoozeDialog.open();
  }

  handleGroup(alert, targets, resolveAlerts) {
    this._groupModel = {
        alert: alert,
        targets: targets,
        resolveAlerts: resolveAlerts,
    };
    this._groupErrorMessage = '';
    this.$.groupDialog.open();
  }

  handleUngroup(alert) {
    this._ungroupModel = alert;
    this._ungroupErrorMessage = '';
    this.$.ungroupDialog.open();
  }

  ////////////////////// Bugs ///////////////////////////

  _commentForBug(alerts) {
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
  }

  _fileBugClicked() {
    this._filedBug = true;
  }

  _removeBug() {
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
  }

  _saveBug() {
    let data = {bugs: [this.$.bug.value.trim()]};
    if (this.$.autosnooze.checked) {
      let autosnoozeTime = parseInt(this.$.autosnoozeTime.value, 10);
      if (isNaN(autosnoozeTime)) {
        this._bugErrorMessage = 'Please enter a valid snooze time.';
        return;
      }
      let snoozeTime = autosnoozeTime || this._defaultSnoozeTime;
      data.snoozeTime = Date.now() + ONE_MIN_MS * snoozeTime;
    }
    let promises = this._fileBugModel.map((alert) => {
      return this.sendAnnotation(alert.key, 'add', data);
    });
    Promise.all(promises).then(
        (response) => {
          this._bugErrorMessage = '';
          this.$.bug.value = '';
          this.$.bugDialog.close();

          if (this._fileBugCallback) {
            this._fileBugCallback();
          }
        },
        (error) => {
          this._bugErrorMessage = error;
        });
  }

  ////////////////////// Snooze ///////////////////////////

  _snooze() {
    let promises = this._snoozeModel.map(
        (alert) => {return this.sendAnnotation(alert.key, 'add', {
          snoozeTime: Date.now() + ONE_MIN_MS * this.$.snoozeTime.value
        })});
    Promise.all(promises).then(
        (response) => {
          this.$.snoozeDialog.close();

          if (this._snoozeCallback) {
            this._snoozeCallback();
          }
        },
        (error) => {
          this._snoozeErrorMessage = error;
        });
  }

  ////////////////////// Comments ///////////////////////////

  _addComment() {
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
  }

  _computeCommentsHidden(annotation) {
    return !(annotation && annotation.comments);
  }

  // This is mostly to make sure the comments in the modal get updated
  // properly if changed.
  _computeCommentsModelAnnotation(annotations, model) {
    if (!annotations || !model) {
      return null;
    }
    return this.computeAnnotation(annotations, model, this.collapseByDefault);
  }

  _computeDefaultSnoozeTime(treeName) {
    if (treeName in DefaultSnoozeTimes) {
      return DefaultSnoozeTimes[treeName];
    }
    return DefaultSnoozeTimes['*'];
  }

  _computeFileBugLabels(tree) {
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
  }

  _computeHideDeleteComment(comment) {
    return comment.user != this.user;
  }

  _computeUsername(email) {
    if (!email) {
      return email;
    }
    let cutoff = email.indexOf('@');
    if (cutoff < 0) {
      return email;
    }
    return email.substring(0, cutoff);
  }

  _formatTimestamp(timestamp) {
    if (!timestamp) {
      return '';
    }
    let time = moment.tz(new Date(timestamp), 'Atlantic/Reykjavik');
    let result = time.tz('America/Los_Angeles').format('ddd, DD MMM Y hh:mm z');
    return result + ` (${time.fromNow()})`;
  }

  _removeComment(evt) {
    let request = this.sendAnnotation(this._commentsModel.key, 'remove', {
      comments: [evt.model.comment.index],
    });
    if (request) {
      request.then((response) => {}, (error) => {
        this._commentsErrorMessage = error;
      });
    }
  }

  ////////////////////// Groups ///////////////////////////
  _group(evt) {
    // Group the current alert and all checked alerts.
    let alerts = this._groupModel.targets.filter((t) => {
      return t.checked;
    });
    alerts.push(this._groupModel.alert);

    this.group(alerts);
  }

  group(alerts) {
    this._groupErrorMessage = '';

    // Determine group ID.
    let groupAlert = null;
    for (let i in alerts) {
      if (alerts[i].grouped) {
        if (groupAlert) {
          this._groupErrorMessage = 'attempting to group multiple groups';
          return;
        }
        groupAlert = alerts[i];
      }
    }
    let groupID = groupAlert ? groupAlert.key : this._generateUUID();

    // Determine ungrouped alerts to group.
    alerts = alerts.filter((a) => {
      return !a.grouped;
    });

    // Data cleanup: If the group is resolved, ensure that all subalerts
    // are resolved too.
    if (groupAlert && groupAlert.resolved) {
      for (let i in groupAlert.alerts) {
        let subAlert = groupAlert.alerts[i];
        if (!subAlert.resolved) {
          this._groupModel.resolveAlerts([subAlert], true);
        }
      }
    } else if (groupAlert && !groupAlert.resolved) {
      for (let i in alerts) {
        if (alerts[i].resolved) {
          this._groupErrorMessage =
              'attempting to group resolved alert with unresolved group';
          return;
        }
      }
    }

    // Create annotation for each ungrouped alert key.
    for (let i in alerts) {
      // Grouping with a resolved group will resolve all unresolved issues.
      if (groupAlert && groupAlert.resolved && !alerts[i].resolved) {
        this._groupModel.resolveAlerts([alerts[i]], true);
      }

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
  }

  _ungroup() {
    // TODO(add proper error handling)
    for (let i in this._ungroupModel.alerts) {
      if (!this._ungroupErrorMessage &&
          this._ungroupModel.alerts[i].checked) {
        this.sendAnnotation(this._ungroupModel.alerts[i].key, 'remove',
                            {group_id: true})
            .then(
                (response) => {
                  this.$.ungroupDialog.close();
                },
                (error) => {
                  this._ungroupErrorMessage = error;
                });
        // TODO(davidriley): Figure out why things remain checked.
        this._ungroupModel.alerts[i].checked = false;
      }
    }
  }

  _haveSubAlerts(alert) {
    return alert.alerts && alert.alerts.length > 0;
  }

  _haveStages(alert) {
    return alert.extension && alert.extension.stages &&
           alert.extension.stages.length > 0;
  }

  _generateUUID() {
    // This is actually an rfc4122 version 4 compliant uuid taken from:
    // http://stackoverflow.com/questions/105034
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(
        /[xy]/g, function(c) {
          var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
          return v.toString(16);
        });
  }

  ////////////////////// Misc UX ///////////////////////////

  _checkAll(e) {
    let target = e.target;
    let checkboxSelector = target.getAttribute('data-checkbox-selector');
    let checkboxes = Polymer.dom(this.root).querySelectorAll(checkboxSelector);
    for (let i = 0; i < checkboxes.length; i++) {
      // Note: We are using .click() because otherwise the checkbox's change
      // event is not fired.
      if (checkboxes[i].checked != target.checked) {
        checkboxes[i].click();
      }
    }
  }
}

customElements.define(SomAnnotations.is, SomAnnotations);
