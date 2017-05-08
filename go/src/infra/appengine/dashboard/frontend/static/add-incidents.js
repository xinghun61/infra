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

  const CELL_WIDTH_PX = 120;

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
    let startPosition;
    let leftEndIcon;
    if (!startDateCell) {
      startDateCell = getDateCell(firstDate, serviceName);
      startPosition = 0;
      leftEndIcon = createIcon(incident['Severity'], IconClass.CENTER);
    } else {
      startPosition = getTimePosition(incident['StartTime']);
      leftEndIcon = createIcon(incident['Severity'], IconClass.LEFT);
    }

    let endDateCell = getDateCell(incident['EndTime'], serviceName);
    let endPosition;
    let rightEndIcon;
    if (!endDateCell) {
      endDateCell = getDateCell(lastDate, serviceName);
      endPosition = CELL_WIDTH_PX;
      rightEndIcon = createIcon(incident['Severity'], IconClass.CENTER);
    } else {
      endPosition = getTimePosition(incident['EndTime']);
      rightEndIcon = createIcon(incident['Severity'], IconClass.RIGHT);
    }
    positionIcons(
	incident['Severity'],
	startDateCell, leftEndIcon, startPosition,
	endDateCell, rightEndIcon, endPosition);
  }

  function positionIcons(
      severity, startDateCell, leftEndIcon, startPos, endDateCell, rightEndIcon, endPos) {
    if (startDateCell != endDateCell) {
      positionIcons(
	  severity,
	  startDateCell.nextElementSibling, createIcon(severity, IconClass.CENTER), 0,
	  endDateCell, rightEndIcon, endPos);
      endPos = CELL_WIDTH_PX;
      rightEndIcon = createIcon(severity, IconClass.CENTER);
    }
    startDateCell.appendChild(
        buildIncidentIcon(severity, leftEndIcon, startPos, rightEndIcon, endPos));
  }

  function buildIncidentIcon(severity, leftEndIcon, startPos, rightEndIcon, endPos) {
    let incIcon = document.createElement('i');
    incIcon.classList.add('incident');
    incIcon.style.left = startPos + 'px';
    incIcon.style.width = endPos - startPos + 'px';
    incIcon.appendChild(leftEndIcon);
    let middle = createIcon(severity, IconClass.CENTER);
    incIcon.appendChild(middle);
    incIcon.appendChild(rightEndIcon);
    return incIcon;
  }

  function getTimePosition(rawTime) {
    let time = new Date(rawTime);
    return 5 * time.getHours();
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
