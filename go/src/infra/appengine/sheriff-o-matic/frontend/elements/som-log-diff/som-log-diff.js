(function() {
    'use strict';

    Polymer({
        is:'som-log-diff',
        properties: {
            tree: {
                value: 'chromium',
                notify:true,
            },
            url: {
                value: '/api/v1/logdiff/chromium',
            },
            _diffLines: {
                type: Array,
                default: function () {
                    return [];
                },
            },
        },

        isDel: function(delta) {
            return delta === 1;
        },

        isCommon: function(delta) {
            return delta === 0;
        },

        isAdd: function (delta) {
            return delta === 2;
        },

        _computeAdd: function(payload) {
            return '+ ' + payload;
        },

        _computeDel: function(payload) {
            return '- ' + payload;
        },
    });
})();
