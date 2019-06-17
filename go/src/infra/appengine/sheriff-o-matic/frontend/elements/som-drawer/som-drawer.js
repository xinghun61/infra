'use strict';

// Refresh delay for on-call rotations in milliseconds.
// This does not need to refresh very frequently.
const drawerRefreshDelayMs = 60 * 60 * 1000;

const ROTATIONS = {
  'android': [
    {
      name: 'Android Sheriff',
      url: 'https://rota-ng.appspot.com/legacy/sheriff_android.json',
    },
  ],
  'chromeos': [
    {
      name: 'Gardener',
      url: 'https://rota-ng.appspot.com/legacy/sheriff_cr_cros_gardeners.json',
    },
    {
      name: 'Infra Deputy',
      url: 'https://rotation.googleplex.com/json?id=5660790132572160',
    },
    {
      name: 'Morning Planner',
      url: 'https://rotation.googleplex.com/json?id=140009',
    },
    {
      name: 'Moblab Peeler',
      url: 'https://rotation.googleplex.com/json?id=6383984776839168',
    },
    {
      name: 'Jetstream Sheriff',
      url: 'https://rotation.googleplex.com/json?id=5186988682510336',
    },
  ],
  'chromium': [
    {
      name: 'Chromium Sheriff',
      url: 'https://rota-ng.appspot.com/legacy/sheriff.json',
    },
  ],
  'chromium.perf': [
    {
      name: 'Chromium Perf Sheriff',
      url: 'https://rota-ng.appspot.com/legacy/sheriff_perfbot.json',
    },
  ],
};

class SomDrawer extends Polymer.Element {

  static get is() {
    return 'som-drawer';
  }

  static get properties() {
    return {
      _defaultTree: String,
      path: {
        type: String,
        notify: true,
      },
      _rotations: {
        type: Array,
        value: null,
      },
      _staticPageList: {
        type: Array,
        computed: '_computeStaticPageList(staticPages)',
        value: function() {
          return [];
        },
      },
      tree: {
        type: Object,
        observer: '_treeChanged',
      },
      trees: Object,
      _treesList: {
        type: Array,
        computed: '_computeTreesList(trees)',
      },
      _trooperString: String,
      _troopers: {
        type: Array,
        computed: '_computeTroopers(_trooperString)',
        value: null,
      },
      // Settings.
      collapseByDefault: {
        type: Boolean,
        notify: true,
      },
      linkStyle: {
        type: String,
        notify: true,
      },
    };
  }

  static get observers() {
    return [
      '_navigateToDefaultTree(path, trees, _defaultTree)'
    ];
  }

  created() {
    super.created();

    this.async(this._refreshAsync, drawerRefreshDelayMs);
  }

  _refresh() {
    this.$.fetchTrooper.generateRequest();
  }

  _refreshAsync() {
    this._refresh();
    this.async(this._refreshAsync, drawerRefreshDelayMs);
  }

  _isCros(tree) {
    return tree && tree.name === 'chromeos';
  }

  _treeChanged(tree) {
    if (!(tree && ROTATIONS[tree.name])) {
      return;
    }

    this._rotations = [];
    const self = this;
    ROTATIONS[tree.name].forEach(function(rotation) {
      switch (rotation.url.split('/')[2]) {
      case 'rota-ng.appspot.com':
        fetch(rotation.url, {
          method: 'GET',
        }).then(function(response) {
          return response.json();
        }).then(function(response) {
          self.push('_rotations', {
            name: rotation.name,
            people: response.emails,
          });
        });
        break;
      case 'rotation.googleplex.com':
        fetch(rotation.url, {
          method: 'GET',
          credentials: 'include',
        }).then(function(response) {
          return response.json();
        }).then(function(response) {
          self.push('_rotations', {
            name: rotation.name,
            people: [response.primary],
          });
        });
        break;
      }
    });
  }

  _computeStaticPageList(staticPages) {
    let pageList = [];
    for (let key in staticPages) {
      let page = staticPages[key];
      page.name = key;
      pageList.push(page);
    }
    return pageList;
  }

  _computeTreesList(trees) {
    return Object.values(trees);
  }

  _computeTroopers(trooperString) {
    if (!trooperString) {
      return [];
    }

    let troopers = trooperString.split(',');
    troopers[0] = troopers[0] + ' (primary)';
    if (troopers.length == 1) {
      return troopers;
    }
    troopers.slice(1).forEach(function(trooper, i) {
      troopers[i + 1] = trooper + ' (secondary)';
    });
    return troopers;
  }

  _formatDate(date) {
    return date.toISOString().substring(0, 10);
  }

  _formatDateShort(date) {
    return moment(date).format('MMM D');
  }

  _navigateToDefaultTree(path, trees, defaultTree) {
    // Not a huge fan of watching path while also changing it, but without
    // watching path, this fires before path has completely initialized,
    // causing the default page to be overwritten.
    if (path == '/') {
      if (defaultTree && defaultTree in trees) {
        this.path = '/' + defaultTree;
      }
    }
  }

  _onSelected(evt) {
    let pathIdentifier = evt.srcElement.value;
    this.path = '/' + pathIdentifier;

    if (pathIdentifier && pathIdentifier in this.trees) {
      this._defaultTree = pathIdentifier;
    }
  }

  toggleMenu(e) {
    let path = Polymer.dom(e).path;
    let target = null;
    let collapseId = null;

    for (let i = 0; i < path.length && !collapseId; i++) {
      target = path[i];
      collapseId = target.getAttribute('data-toggle-target');
    }

    let collapse = this.$[collapseId];
    collapse.opened = !collapse.opened;

    let icons = target.getElementsByClassName('toggle-icon');
    for (let i = 0; i < icons.length; i++) {
      icons[i].icon = collapse.opened ? 'remove' : 'add';
    }
  }
}

customElements.define(SomDrawer.is, SomDrawer);
