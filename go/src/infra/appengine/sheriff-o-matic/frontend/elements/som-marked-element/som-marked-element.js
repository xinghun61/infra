(function() {
  'use strict';

  Polymer({
    is: 'som-marked-element',
    properties: {
      markdown: String,
    },
    ready: function() {
      this.$.element.renderer =
          (function(r) { r.link = this._getLinkRenderer(); }).bind(this);
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
