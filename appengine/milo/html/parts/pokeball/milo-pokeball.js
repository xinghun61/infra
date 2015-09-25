Polymer({
  is: "milo-pokeball",

  properties: {
    attempt: {
      type: Object,
      value: {
        steps: [
          {
            display: 'item 1',
            status: 'error'
          }, {
            display: 'item 2',
            status: 'success'
          }, {
            display: 'Bottom',
          }
        ]
      },
    },
    collapsed: {
      type: Boolean,
      value: true
    },
    circle: {
      type: Number,
      computed: 'getCircle(attempt)',
    },
    top: {
      type: String,
      value: "Title",
      computed: 'getTitle(attempt)',
    },
    bottom: {
      type: String,
      value: "Bottom",
      computed: 'getBottom(attempt)',
    },
    middleItems: {
      type: Array,
      value: [],
      computed: 'getMiddleItems(collapsed, attempt)'
    }
  },

  listeners: {
    'pokeball-container.tap': 'toggleMenu'
  },

  toggleMenu: function(e) {
    this.collapsed = !this.collapsed;
  },

  getTitle: function(attempt) {
    return attempt.display_name;
  },

  getBottom: function(attempt) {
    return attempt.steps.slice(-1)[0];
  },

  getCircle: function(attempt) {
    return attempt.steps.length;
  },

  getMiddleItems: function(collapsed, attempt) {
    if (collapsed) {
      return [];
    } else {
      return attempt.steps.slice(0, -1);
    }
  }

});
