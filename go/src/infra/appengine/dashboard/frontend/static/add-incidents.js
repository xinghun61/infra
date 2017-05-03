// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
(function(window) {
  'use strict';

  // Alert matches alert values passed in by the pageData.
  const Alert = {
    RED: 0,
    YELLOW: 1,
  };

  const IconClass = {
    CIRCLE: 'circle',
    CENTER: 'center',
    RIGHT: 'right',
    LEFT: 'left',
  };

  const alertColorClass = new Map();
  alertColorClass.set(Alert.RED, 'red');
  alertColorClass.set(Alert.YELLOW, 'yellow');

  // TODO(jojwang): Make pageData object follow js naming guidelines.
  function addIncidents(pageData) {
    renderIncidents(
	pageData['ChopsServices'],
	pageData['Dates'][0],
	pageData['Dates'][6]);
  }

  function renderIncidents(services, firstDate, lastDate) {
    services.forEach((service) => {
      let serviceName = service['Service']['Name'];
      service['Incidents'].forEach((incident) => {
	if (incident['Open']) {
	  let statusCell = document.querySelector('.js-' + serviceName);
	  statusCell.appendChild(
	      createIcon(incident['Severity'], IconClass.CIRCLE));
	} else {
	  addIncident(incident, serviceName, firstDate, lastDate);
	}
      });
    });
  }

  function addIncident(incident, serviceName, firstDate, lastDate) {
    let startDateCell = getDateCell(incident['StartTime'], serviceName);
    if (!startDateCell) {
      startDateCell = getDateCell(firstDate, serviceName);
      startDateCell.appendChild(
	  createIcon(incident['Severity'], IconClass.CENTER));
    } else {
      startDateCell.appendChild(
	  createIcon(incident['Severity'], IconClass.LEFT));
    }

    let endDateCell = getDateCell(incident['EndTime'], serviceName);
    if (!endDateCell) {
      endDateCell = getDateCell(lastDate, serviceName);
      endDateCell.appendChild(
	  createIcon(incident['Severity'], IconClass.CENTER));
    } else {
      endDateCell.appendChild(
	  createIcon(incident['Severity'], IconClass.RIGHT));
    }
    // TODO(jojwang): Add red_rect/yellow_rect to fill in
    // space between startDateCell and endDateCell.
  }

  function getDateCell(date, serviceName) {
    let className = '.js-' + serviceName + '-' + fmtDate(date);
    return document.querySelector(className);
  }

  function createIcon(severity, iconClass) {
    let icon = document.createElement('i');
    icon.classList.add(alertColorClass.get(severity));
    icon.classList.add(iconClass);
    return icon;
  }

  function fmtDate(rawDate) {
    let date = new Date(rawDate);
    return (date.getMonth()+1) + '-' +
	date.getDate() + '-' + date.getFullYear();
  }

  window.__addIncidents = window.__addIncidents || addIncidents;
})(window);
