'use strict';

class SomLogDiff extends Polymer.mixinBehaviors([LinkifyBehavior],
    Polymer.Element) {

  static get is() {
    return 'som-log-diff';
  }

  static get properties() {
    return {
      tree: {
        value: 'chromium',
        notify: true,
      },
      _diffLines: {
        type: Array,
        default: function () {
        return [];
        },
      },
      loading: {
        type: Boolean,
        value: true,
      },
      key: {
        type: String,
      },
      master: {
        type: String,
        computed: '_computeMaster(key)',
      },
      builder: {
        type: String,
        computed: '_computeBuilder(key)',
      },
      buildNum1: {
        type: String,
        computed: '_computeBuildNum1(key)',
      },
      buildNum2: {
        type: String,
        computed: '_computeBuildNum2(key)',
      },
      url: {
        type: String,
        computed: '_computeURL(key)',
      },
      build1Url: {
        type: String,
        computed: '_computeBuildUrl(master, builder, buildNum1)',
      },
      build2Url: {
        type: String,
        computed: '_computeBuildUrl(master, builder, buildNum2)',
      },
    };
  }

  _computeBuildUrl(master, builder, buildNum) {
    return "https://build.chromium.org/p/" + master+ "/builders/"
        + builder + "/builds/" + buildNum;
  }

  _computeMaster(key) {
    let params = key.split('/');
    return params[0];
  }

  _computeBuilder(key) {
    let params = key.split('/');
    return params[1];
  }

  _computeBuildNum1(key) {
    let params = key.split('/');
    return params[2];
  }

  _computeBuildNum2(key) {
    let params = key.split('/');
    return params[3];
  }

  _isDel(delta) {
    return delta === 1;
  }

  _isCommon(delta) {
    return delta === 0;
  }

  _isAdd(delta) {
    return delta === 2;
  }

  _computeURL(key) {
    return "/api/v1/logdiff/" + key;
  }

  _computeDiffLength(payload) {
    return payload.split('\n').length;
  }

  _defaultOpen(payload) {
    return this._computeDiffLength(payload) < 10;
  }

  _changeStatus(evt) {
    evt.target.nextElementSibling.toggle();
  }

  _computeButtonText(payload) {
    return '● Collapse/Expand (' + this._computeDiffLength(payload) + ' common lines)';
  }
}

customElements.define(SomLogDiff.is, SomLogDiff);
