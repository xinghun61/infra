/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * This file contains JS functions used in rendering a hotlistissues table
 */


/**
 * Helper function to set several attributes of an element at once.
 * @param {Element} el element that is getting the attributes
 * @param {dict} attrs Dictionary of {attrName: attrValue, ..}
 */
function setAttributes(el, attrs) {
  for (let key in attrs) {
    el.setAttribute(key, attrs[key]);
  }
}

// TODO(jojwang): readOnly is currently empty string, figure out what it should be
// ('True'/'False' 'yes'/'no'?).

/**
 * Helper function for creating a <td> element that contains the widgets of the row.
 * @param {dict} tableRow dictionary {'projectName': 'name', .. } of relevant row info.
 * @param {} readOnly.
 * @param {boolean} userLoggedIn is the current user logged in.
 * @return an element containing the widget elements
 */
function createWidgets(tableRow, readOnly, userLoggedIn) {
  let widgets = document.createElement('td');
  widgets.setAttribute('class', 'rowwidgets nowrap');

  let gripper = document.createElement('a');
  gripper.setAttribute('class', 'gripper');
  gripper.textContent = '\u2059';
  widgets.appendChild(gripper);

  if (!readOnly) {
    if (userLoggedIn) {
      // TODO(jojwang): for bulk edit, only show a checkbox next to an issue that
      // the user has permission to edit.
      let checkbox = document.createElement('input');
      setAttributes(checkbox, {'class': 'checkRangeSelect',
        'id': 'cb_' + tableRow['issueRef'],
        'type': 'checkbox'});
      widgets.appendChild(checkbox);
      widgets.appendChild(document.createTextNode(' '));

      let star = document.createElement('a');
      let starColor = tableRow['isStarred'] ? 'cornflowerblue' : 'gray';
      let starred = tableRow['isStarred'] ? 'Un-s' : 'S';
      setAttributes(star, {'class': 'star',
        'id': 'star-' + tableRow['projectName'] + tableRow['localID'],
        'style': 'color:' + starColor,
        'title': starred + 'tar this issue',
        'data-project-name': tableRow['projectName'],
        'data-local-id': tableRow['localID']});
      star.textContent = (tableRow['isStarred'] ? '\u2605' : '\u2606');
      widgets.appendChild(star);
    }
  }
  return widgets;
}


/**
 * Helper function to set attributes and add Nodes for an ID cell.
 * @param {Element} td element to be added to current row in table.
 * @param {dict} tableRow dictionary {'projectName': 'name', .. } of relevant row info.
 * @param {boolean} isCrossProject are issues in the table from more than one project.
*/
function createIDCell(td, tableRow, isCrossProject) {
  td.classList.add('id');
  let aLink = document.createElement('a');
  aLink.setAttribute('href', tableRow['issueCleanURL']);
  aLink.setAttribute('class', 'computehref');
  let aLinkContent = (isCrossProject ? (tableRow['projectName'] + ':') : '' ) + tableRow['localID'];
  aLink.textContent = aLinkContent;
  td.appendChild(aLink);
}

function createProjectCell(td, tableRow) {
  td.classList.add('project');
  let aLink = document.createElement('a');
  aLink.setAttribute('href', tableRow['projectURL']);
  aLink.textContent = tableRow['projectName'];
  td.appendChild(aLink);
}

function createEditableNoteCell(td, cell, projectName, localID, hotlistID) {
  let textBox = document.createElement('textarea');
  setAttributes(textBox, {
    'id': `itemnote_${projectName}_${localID}`,
    'placeholder': '---',
    'class': 'itemnote rowwidgets',
    'projectname': projectName,
    'localid': localID,
    'style': 'height:15px',
  });
  if (cell['values'].length > 0) {
    textBox.value = cell['values'][0]['item'];
  }
  textBox.addEventListener('blur', function(e) {
    saveNote(e.target, hotlistID);
  });
  debouncedKeyHandler = debounce(function(e) {
    saveNote(e.target, hotlistID);
  });
  textBox.addEventListener('keyup', debouncedKeyHandler, false);
  td.appendChild(textBox);
}

function enter_detector(e) {
  if (e.which==13||e.keyCode==13) {
    this.blur();
  }
}


/**
 * Helper function to set attributes and add Nodes for an Summary cell.
 * @param {Element} td element to be added to current row in table.
 * @param {dict} cell dictionary {'projectName': 'name', .. } of relevant cell info.
*/
function createSummaryCell(td, cell) {
  // TODO(jojwang): detect when links are present and make clicking on cell go to
  // link, not issue details page
  td.setAttribute('style', 'width:100%');
  fillValues(td, cell['values']);
  fillNonColumnLabels(td, cell['nonColLabels']);
}


/**
 * Helper function to set attributes and add Nodes for an Attribute or Unfilterable cell.
 * @param {Element} td element to be added to current row in table.
 * @param {dict} cell dictionary {'type': 'Summary', .. } of relevant cell info.
*/
function createAttrAndUnfiltCell(td, cell) {
  if (cell['noWrap'] == 'yes') {
    td.className += ' nowrapspan';
  }
  if (cell['align']) {
    td.setAttribute('align', cell['align']);
  }
  fillValues(td, cell['values']);
}

function createUrlCell(td, cell) {
  td.classList.add('url');
  cell.values.forEach((value) => {
    let aLink = document.createElement('a');
    aLink.href = value['item'];
    aLink.target = '_blank';
    aLink.rel = 'nofollow';
    aLink.textContent = value['item'];
    aLink.classList.add('fieldvalue_url');
    td.appendChild(aLink);
  });
}

function createIssuesCell(td, cell) {
  td.classList.add('url');
  if (cell.values.length > 0) {
    cell.values.forEach( function(value, index, array) {
      const span = document.createElement('span');
      if (value['isDerived']) {
        span.className = 'derived';
      }
      const a = document.createElement('a');
      a.href = value['href'];
      a.rel = 'nofollow"';
      if (value['title']) {
        a.title = value['title'];
      }
      if (value['closed']) {
        a.style.textDecoration = 'line-through';
      }
      a.textContent = value['id'];
      span.appendChild(a);
      td.appendChild(span);
      if (index != array.length-1) {
        td.appendChild(document.createTextNode(', '));
      }
    });
  } else {
    td.textContent = '---';
  }
}

/**
 * Helper function to fill a td element with a cell's non-column labels.
 * @param {Element} td element to be added to current row in table.
 * @param {list} labels list of dictionaries with relevant (key, value) for each label
 */
function fillNonColumnLabels(td, labels) {
  labels.forEach( function(label) {
    let aLabel = document.createElement('a');
    setAttributes(aLabel, {'class': 'label', 'href': 'list?q=label:' + label['value']});
    if (label['isDerived']) {
      let i = document.createElement('i');
      i.textContent = label['value'];
      aLabel.appendChild(i);
    } else {
      aLabel.textContent = label['value'];
    }
    td.appendChild(document.createTextNode(' '));
    td.appendChild(aLabel);
  });
}


/**
 * Helper function to fill a td element with a cell's value(s).
 * @param {Element} td element to be added to current row in table.
 * @param {list} values list of dictionaries with relevant (key, value) for each value
 */
function fillValues(td, values) {
  if (values.length > 0) {
    values.forEach( function(value, index, array) {
      let span = document.createElement('span');
      if (value['isDerived']) {
        span.className = 'derived';
      }
      span.textContent = value['item'];
      td.appendChild(span);
      if (index != array.length-1) {
        td.appendChild(document.createTextNode(', '));
      }
    });
  } else {
    td.textContent = '---';
  }
}


/**
 * Helper function to create a table row.
 * @param {dict} tableRow dictionary {'projectName': 'name', .. } of relevant row info.
 * @param {dict} pageSettings dict of relevant settings for the hotlist and user viewing the page.
 */
function renderHotlistRow(tableRow, pageSettings) {
  let tr = document.createElement('tr');
  if (pageSettings['cursor'] == tableRow['issueRef']) {
    tr.setAttribute('class', 'ifOpened hoverTarget cursor_on drag_item');
  } else {
    tr.setAttribute('class', 'ifOpened hoverTarget cursor_off drag_item');
  }

  setAttributes(tr, {'data-idx': tableRow['idx'], 'data-id': tableRow['issueID'], 'issue-context-url': tableRow['issueContextURL']});
  widgets = createWidgets(tableRow, pageSettings['readOnly'],
    pageSettings['userLoggedIn']);
  tr.appendChild(widgets);
  tableRow['cells'].forEach(function(cell) {
    let td = document.createElement('td');
    td.setAttribute('class', 'col_' + cell['colIndex']);
    if (cell['type'] == 'ID') {
      createIDCell(td, tableRow, (pageSettings['isCrossProject'] == 'True'));
    } else if (cell['type'] == 'summary') {
      createSummaryCell(td, cell);
    } else if (cell['type'] == 'note') {
      if (pageSettings['ownerPerm'] || pageSettings['editorPerm']) {
        createEditableNoteCell(
          td, cell, tableRow['projectName'], tableRow['localID'],
          pageSettings['hotlistID']);
      } else {
        createSummaryCell(td, cell);
      }
    } else if (cell['type'] == 'project') {
      createProjectCell(td, tableRow);
    } else if (cell['type'] == 'url') {
      createUrlCell(td, cell);
    } else if (cell['type'] == 'issues') {
      createIssuesCell(td, cell);
    } else {
      createAttrAndUnfiltCell(td, cell);
    }
    tr.appendChild(td);
  });
  let directLinkURL = tableRow['issueCleanURL'];
  let directLink = document.createElement('a');
  directLink.setAttribute('class', 'directlink material-icons');
  directLink.setAttribute('href', directLinkURL);
  directLink.textContent = 'link'; // Renders as a link icon.
  let lastCol = document.createElement('td');
  lastCol.appendChild(directLink);
  tr.appendChild(lastCol);
  return tr;
}


/**
 * Helper function to create the group header row
 * @param {dict} group dict of relevant values for the current group
 * @return a <tr> element to be added to the current <tbody>
 */
function renderGroupRow(group) {
  let tr = document.createElement('tr');
  tr.setAttribute('class', 'group_row');
  let td = document.createElement('td');
  setAttributes(td, {'colspan': '100', 'class': 'toggleHidden'});
  let whenClosedImg = document.createElement('img');
  setAttributes(whenClosedImg, {'class': 'ifClosed', 'src': '/static/images/plus.gif'});
  td.appendChild(whenClosedImg);
  let whenOpenImg = document.createElement('img');
  setAttributes(whenOpenImg, {'class': 'ifOpened', 'src': '/static/images/minus.gif'});
  td.appendChild(whenOpenImg);
  tr.appendChild(td);

  div = document.createElement('div');
  div.textContent += group['rowsInGroup'];

  div.textContent += (group['rowsInGroup'] == '1' ? ' issue:': ' issues:');

  group['cells'].forEach(function(cell) {
    let hasValue = false;
    cell['values'].forEach(function(value) {
      if (value['item'] !== 'None') {
        hasValue = true;
      }
    });
    if (hasValue) {
      cell.values.forEach(function(value) {
        div.textContent += (' ' + cell['groupName'] + '=' + value['item']);
      });
    } else {
      div.textContent += (' -has:' + cell['groupName']);
    }
  });
  td.appendChild(div);
  return tr;
}


/**
 * Builds the body of a hotlistissues table.
 * @param {dict} tableData dict of relevant values from 'table_data'
 * @param {dict} pageSettings dict of relevant settings for the hotlist and user viewing the page.
 */
function renderHotlistTable(tableData, pageSettings) {
  let tbody;
  let table = $('resultstable');

  // TODO(jojwang): this would not work if grouping did not require a page refresh
  // that wiped the table of all its children. This should be redone to be more
  // robust.
  // This loop only does anything when reranking is enabled.
  for (i=0; i < table.childNodes.length; i++) {
    if (table.childNodes[i].tagName == 'TBODY') {
      table.removeChild(table.childNodes[i]);
    }
  }

  tableData.forEach(function(tableRow) {
    if (tableRow['group'] !== 'no') {
      // add current tbody to table, need a new tbody with group row
      if (typeof tbody !== 'undefined') {
        table.appendChild(tbody);
      }
      tbody = document.createElement('tbody');
      tbody.setAttribute('class', 'opened');
      tbody.appendChild(renderGroupRow(tableRow['group']));
    }
    if (typeof tbody == 'undefined') {
      tbody = document.createElement('tbody');
    }
    tbody.appendChild(renderHotlistRow(tableRow, pageSettings));
  });
  tbody.appendChild(document.createElement('tr'));
  table.appendChild(tbody);

  let stars = document.getElementsByClassName('star');
  for (var i = 0; i < stars.length; ++i) {
    let star = stars[i];
    star.addEventListener('click', function(event) {
      let projectName = event.target.getAttribute('data-project-name');
      let localID = event.target.getAttribute('data-local-id');
      _TKR_toggleStar(event.target, projectName, localID, null, null, null);
    });
  }
}


/**
 * Activates the drag and drop functionality of the hotlistissues table.
 * @param {dict} tableData dict of relevant values from the 'table_data' of
 *  hotlistissues servlet. This is used when a drag and drop motion does not
 *  result in any changes in the ordering of the issues.
 * @param {dict} pageSettings dict of relevant settings for the hotlist and user
 *  viewing the page.
 * @param {str} hotlistID the number ID of the current hotlist
*/
function activateDragDrop(tableData, pageSettings, hotlistID) {
  function onHotlistRerank(srcID, targetID, position) {
    let data = {
      target_id: targetID,
      moved_ids: srcID,
      split_above: position == 'above',
      colspec: pageSettings['colSpec'],
      can: pageSettings['can'],
    };
    CS_doPost(hotlistID + '/rerank.do', onHotlistResponse, data);
  }

  function onHotlistResponse(event) {
    let xhr = event.target;
    if (xhr.readyState != 4) {
      return;
    }
    if (xhr.status != 200) {
      window.console.error('200 page error');
      // TODO(jojwang): fill this in more
      return;
    }
    let response = CS_parseJSON(xhr);
    renderHotlistTable(
      (response['table_data'] == '' ? tableData : response['table_data']),
      pageSettings);
    // TODO(jojwang): pass pagination state to server
    _initDragAndDrop($('resultstable'), onHotlistRerank, true);
  }
  _initDragAndDrop($('resultstable'), onHotlistRerank, true);
}
