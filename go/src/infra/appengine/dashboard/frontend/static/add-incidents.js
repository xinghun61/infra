// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
(function(window) {
  'use strict';

  // Alert matches alert values passed in by the pageData.
  const Alert = {
    RED: 0,
    YELLOW: 1,
    GREEN: 2,
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
  alertColorClass.set(Alert.GREEN, 'green');

  const RIGHT_BORDER_LIMIT_PCNT = 100;

  // TODO(jojwang): Make pageData object follow js naming guidelines.
  function addIncidents(pageData) {
    let dateHeaders = document.querySelectorAll('.js-date');
    let dateStrings = pageData['Dates'].map((date) => {return fmtDate(date);});
    setHeaderDates(dateHeaders, dateStrings)
    renderIncidents(
	pageData['ChopsServices'],
	dateStrings);
  }

  function setHeaderDates(dateHeaders, dateStrings) {
    dateStrings.forEach((date, index) => {
      dateHeaders[index].textContent = date;
    });
  }

  function renderIncidents(services, dateStrings) {
    services.forEach((service) => {
      let serviceName = service['Service']['Name'];
      let noIssues = true;
      service['Incidents'].forEach((incident) => {
	if (incident['Open']) {
	  noIssues = false;
	  let statusCell = document.querySelector('.js-' + serviceName);
	  statusCell.appendChild(
	      createIcon(incident['Severity'], IconClass.CIRCLE));
	} else {
	  let incidentCell = document.querySelector('.js-' + serviceName + '-incidents');
	  incidentCell.appendChild(addIncident(incident, dateStrings));
	}
      });
      if (noIssues) {
	let statusCell = document.querySelector('.js-' + serviceName);
	statusCell.appendChild(createIcon(Alert.GREEN, IconClass.CIRCLE));
      }
    });
  }

  function getDatePosition(rawDate, dateStrings) {
    let position;
    dateStrings.forEach((str, i) => {
      if (fmtDate(rawDate) === str) {
	position = i / 7;
	let time = new Date(rawDate).getHours();
	position = (position + time / 168) * 100;
      }
    });
    return position;
  }

  function addIncident(incident, dateStrings) {
    let startPosition = getDatePosition(incident['StartTime'], dateStrings);
    let leftEndIcon;
    if (!startPosition) {
      startPosition = 0;
      leftEndIcon = createIcon(incident['Severity'], IconClass.CENTER);
    } else {
      leftEndIcon = createIcon(incident['Severity'], IconClass.LEFT);
    }

    let endPosition = getDatePosition(incident['EndTime'], dateStrings);
    let rightEndIcon;
    if (!endPosition) {
      endPosition = RIGHT_BORDER_LIMIT_PCNT;
      rightEndIcon = createIcon(incident['Severity'], IconClass.CENTER);
    } else {
      rightEndIcon = createIcon(incident['Severity'], IconClass.RIGHT);
    }

    let container = document.createElement('div');
    container.classList.add('container');
    container.appendChild(buildIncidentIcon(
	incident['Severity'],
	leftEndIcon, startPosition,
	rightEndIcon, endPosition));
    return container;
  }

  function buildIncidentIcon(severity, leftEndIcon, startPos, rightEndIcon, endPos) {
    let incIcon = document.createElement('i');
    incIcon.classList.add('incident');
    incIcon.style.left = startPos + '%';
    incIcon.style.width = endPos - startPos + '%';
    incIcon.appendChild(leftEndIcon);
    let middle = createIcon(severity, IconClass.CENTER);
    incIcon.appendChild(middle);
    incIcon.appendChild(rightEndIcon);
    return incIcon;
  }

  function createIcon(severity, iconClass) {
    let icon = document.createElement('i');
    icon.classList.add(alertColorClass.get(severity));
    icon.classList.add(iconClass);
    return icon;
  }

  function fmtDate(rawDate) {
    let date = new Date(rawDate);
    return date.getFullYear() + '-' + (date.getMonth()+1) + '-' + date.getDate();
  }

  window.__addIncidents = window.__addIncidents || addIncidents;
})(window);
