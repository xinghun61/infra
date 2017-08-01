(function() {
  'use strict';

  Polymer({
    is: 'som-marked-element',
    properties: {
      markdown: {
        type: String,
        observer: 'render',
      },
      _attached: {
        type: Boolean,
        value: false,
      },
      _markdownElement: Object,
    },

    ready: function() {
      this._markdownElement = this.$.markdownElement;
    },

    attached: function() {
      this._attached = true;
      this.render();
    },

    render: function() {
      // Don't render if the element isn't visible yet.
      if (!this._attached) return;

      if (!this.markdown) {
        Polymer.dom(this._markdownElement).innerHTML = '';
        return;
      }
      let renderer = new marked.Renderer();
      renderer.link = this._getLinkRenderer();

      let opts = {
        renderer: renderer,
        breaks: true,
        sanitize: true,
        pedantic: false,
        smartypants: false
      };
      Polymer.dom(this._markdownElement).innerHTML = marked(this.markdown, opts);
      this.fire('marked-render-complete', {}, {composed: true});
    },

    _hrefIsAllowed: function(href) {
      // Marked does some URL sanitization in their default link renderer.
      // This copies Marked's sanitization for URLs so there is
      // not a loss in security.
      try {
        let prot = decodeURIComponent(unescape(href))
                       .replace(/[^\w:]/g, '')
                       .toLowerCase();
        if (prot.indexOf('javascript:') === 0 ||
            prot.indexOf('vbscript:') === 0 || prot.indexOf('data:') === 0) {
          return false;
        }
      } catch (e) {
        return false;
      }
      return true;
    },

    _getLinkRenderer: function() {
      return (href, title, text) => {
        if (!this._hrefIsAllowed(href))
          return text;
        return `<a href="${href}" target="_blank">${text}</a>`;
      };
    },
  });
})();
