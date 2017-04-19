// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
(function(window) {
  'use strict';

  const Alert = {
    RED: 0,
    YELLOW: 1,
  };

  let alertImgsMap = new Map();
  alertImgsMap.set(Alert.RED, 'static/red.png');
  alertImgsMap.set(Alert.YELLOW, 'static/yellow.png');

  function addIncidents(pageData) {
    renderIncidents(pageData['ChopsServices']);
    renderIncidents(pageData['NonSLAServices']);
  }

  function renderIncidents(services) {
    for (let i = 0; i < services.length; i++) {
      let service = services[i];
      let serviceName = service['Service']['Name'];
      for (let j = 0; j < service['Incidents'].length; j++) {
	let incident = service['Incidents'][j];
	let img = getIncidentImg(incident['Severity']);
	if (incident['Open']) {
	  let statusCell = document.querySelector('.js-' + serviceName)
	  statusCell.appendChild(img)
	} else {
	  let prettyDate = fmtDate(incident['StartTime']);
	  let tdClass = '.js-' + serviceName + '-' + prettyDate;
	  let dateCell = document.querySelector(tdClass);
	  dateCell.appendChild(img);
	}
      }
    }
  }

  function getIncidentImg(severity) {
    let img = document.createElement('img');
    img.classList.add('light');
    img.src = alertImgsMap.get(severity);
    return img;
  }

  function fmtDate(rawDate) {
    let date = new Date(rawDate);
    return (date.getMonth()+1) + '-' +
	date.getDate() + '-' + date.getFullYear();
  }

  window.__addIncidents = window.__addIncidents || addIncidents;
})(window);
