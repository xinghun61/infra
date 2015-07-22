/** 
 * Copyright 2015 The Chromium Authors. All rights reserved.
 * Use of this source code is governed by a BSD-style license that can be
 * found in the LICENSE file 
 */

Polymer({
  is: 'console-home',
  properties: {
    projectName: {
      type: String,
      notify: true,
      value: "",
      observer: '_projectChanged'
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
            format: '%Y-%m-%d'
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
  _projectChanged: function() {
    //demo
    graphs = {"chromium": [{columsData:[
            ['x', '2013-01-01', '2013-01-02', '2013-01-03', '2013-01-04', 
             '2013-01-05', '2013-01-06'],
            ['CPU usage', 0.76, 0.85, 0.83, 0.67, 0.93, 0.79],
            ], labelText: 'CPU usage'}, {columsData: [
            ['x', '2013-01-01', '2013-01-02', '2013-01-03', '2013-01-04', 
             '2013-01-05', '2013-01-06'],
            ['Memory Usage', 0.8, 0.85, 0.9, 0.83, 0.93, 0.95],
            ], labelText: 'Memory Usage'}],

            "infra": [{columsData:[
             ['x', '2013-01-01', '2013-01-02', '2013-01-03', '2013-01-04', 
              '2013-01-05', '2013-01-06'],
             ['RPS', 400, 800, 526, 642, 215, 800],
             ], labelText:  'RPS'}, {columsData: [
             ['x', '2013-01-01', '2013-01-02', '2013-01-03', '2013-01-04', 
              '2013-01-05', '2013-01-06'],
             ['Memory Usage', 0.5, 0.85, 0.9, 0.56, 0.73, 0.85],
             ], labelText:'Memory Usage'}], 

            "naclports": [{columsData:[
             ['x', '2013-01-01', '2013-01-02', '2013-01-03', '2013-01-04', 
              '2013-01-05', '2013-01-06'],
             ['RPS', 588, 400, 526, 642, 715, 500],
             ], labelText:'RPS'}, {columsData: [
             ['x', '2013-01-01', '2013-01-02', '2013-01-03', '2013-01-04', 
              '2013-01-05', '2013-01-06'],
             ['Memory Usage', 0.45, 0.55, 0.9, 0.56, 0.73, 0.85],
             ], labelText:'Memory Usage'}], 
    
    };

    var node = this.$$('#chart0');
    while (node.hasChildNodes()) {
      node.removeChild(node.firstChild);
    }; 

    if(graphs[this.projectName] != null){
      for(var i=0; i< graphs[this.projectName].length; i++){
        var linechart = this.graphDrawing(graphs[this.projectName][i]);
        Polymer.dom(this.$$('#chart0')).appendChild(linechart.element);
      };
    }
  },
});
