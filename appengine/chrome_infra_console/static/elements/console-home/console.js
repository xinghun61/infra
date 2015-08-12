/** 
 * Copyright 2015 The Chromium Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file 
 */

Polymer({
  is: 'console-home',
  properties: {
    projectId: {
      type: String,
      notify: true,
      value: ""
    },
    graphs: {
      type: Object,
      notify: true,
      value: {"": null},
    },
    spin: {
      type: Boolean,
      notify: true,
    },
    projectName: {
      type: String,
      notify: true,
      value: ""
    }
  },
  graphDrawing: function(params) {
    var linechart = c3.generate({
      data: {
        x: 'x',
        columns: params.columsData,
      },
      axis: {
        x: {
          type: 'timeseries',
          tick: {
            format: '%Y-%m-%d %H:%M:%S'
          }
        },
        y: {
          label: {
            text: params.labelText,
            position: 'outer-middle'
          }
        }
      }
    });
    return linechart;
  },
  projectChanged: function() {
    var graphs = this.graphs;
    var node = this.$$('#chart0');
    while (node.hasChildNodes()) {
      node.removeChild(node.firstChild);
    }; 

    if(graphs != undefined && graphs[this.projectId] != null){
      for(var i=0; i< graphs[this.projectId].length; i++){
        for(var f=0; f<graphs[this.projectId][i]["fields"].length; f++){
          var field = graphs[this.projectId][i]["fields"][f];
          var key = field.key;
          if(key != "project_id") {
            var line = key.concat(": ", field.value, "  ");
            var field_text = document.createTextNode(line);
            Polymer.dom(this.$$('#chart0')).appendChild(field_text);
          };
        };   
        var linechart = this.graphDrawing(graphs[this.projectId][i]["draw"]);
        Polymer.dom(this.$$('#chart0')).appendChild(linechart.element);
      };
    };
  },
});
