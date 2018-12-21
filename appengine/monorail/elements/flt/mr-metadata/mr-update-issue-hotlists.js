'use strict';

class MrUpdateIssueHotlists extends ReduxMixin(Polymer.Element) {
  static get is() {
    return 'mr-update-issue-hotlists';
  }

  static get properties() {
    return {
      issueHotlists: {
        type: Array,
        statePath: 'issueHotlists',
      },
      userHotlists: {
        type: Array,
        statePath: 'userHotlists',
      },
      user: {
        type: Object,
        statePath: 'user',
      },
      error: String,
    };
  }

  _issueInHotlist(hotlist, issueHotlists) {
    return issueHotlists.some((issueHotlist) => {
      return (hotlist.ownerRef.userId === issueHotlist.ownerRef.userId
        && hotlist.name === issueHotlist.name);
    });
  }

  _getCheckboxTitle(isChecked) {
    return (isChecked ? 'Remove issue from' : 'Add issue to') + ' this hotlist';
  }

  _checkboxTitle(hotlist, issueHotlists, foo) {
    return this._getCheckboxTitle(this._issueInHotlist(hotlist, issueHotlists));
  }

  _updateCheckboxTitle(e) {
    e.target.title = this._getCheckboxTitle(e.target.checked);
  }

  get changes() {
    const changes = {
      added: [],
      removed: [],
    };
    this.userHotlists.forEach((hotlist) => {
      const issueInHotlist = this._issueInHotlist(hotlist, this.issueHotlists);
      const hotlistIsChecked = this.$.issueHotlistsForm[hotlist.name].checked;
      if (issueInHotlist && !hotlistIsChecked) {
        changes.removed.push({
          name: hotlist.name,
          owner: hotlist.ownerRef,
        });
      } else if (!issueInHotlist && hotlistIsChecked) {
        changes.added.push({
          name: hotlist.name,
          owner: hotlist.ownerRef,
        });
      }
    });
    if (this.$.issueHotlistsForm._newHotlistName.value) {
      changes.created = {
        name: this.$.issueHotlistsForm._newHotlistName.value,
        summary: 'Hotlist created from issue.',
      };
    }
    return changes;
  }

  reset() {
    this.$.issueHotlistsForm.reset();
    this.error = '';
  }

  discard() {
    this.dispatchEvent(new CustomEvent('discard'));
  }

  save() {
    this.dispatchEvent(new CustomEvent('save'));
  }
}

customElements.define(MrUpdateIssueHotlists.is, MrUpdateIssueHotlists);
