// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
(function(window) {
  'use strict';

  const Alert = {
    RED: 1,
    YELLOW: 2
  };

  function addIncidents(pageData) {
    renderIncidents(pageData['ChopsServices']);
    renderIncidents(pageData['NonSLAServices']);
  }

  function renderIncidents(services) {
    for (let i = 0; i < services.length; i++) {
      let service = services[i];
      let serviceName = service['name'];
      for (let j = 0; j < service['incidents'].length; j++) {
	let incident = service['incidents'][j];
	let tdClass = '.js-' + serviceName + '-' + incident['start_time'];
	let dateCell = document.querySelector(tdClass);
	let img = document.createElement('img');
	img.className = 'light';
	if (incident['severity'] == Alert.RED) {
          img.src = '../static/red.png';
	}
	if (incident['severity'] == Alert.YELLOW) {
          img.src = '../static/yellow.png';
	}
	dateCell.appendChild(img);
      }
    }
  }

  window.__addIncidents = window.__addIncidents || addIncidents;
})(window);
