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
  for (var key in attrs) {
    el.setAttribute(key, attrs[key]);
  }
}

// TODO(jojwang): readOnly is currently empty string, figure out what it should be
// ('True'/'False' 'yes'/'no'?).

/**
 * Helper function for creating a <td> element that contains the widgets of the row.
 * @param {dict} tableRow dictionary {'projectName': 'name', .. } of relevant row info.
 * @param {} readOnly.
 * @param {boolean} ownerEditorPerm does current viewer have owner/editor permissions.
 * @param {boolean} isCrossProject are issues in the table from more than one project.
 * @return an element containing the widget elements
 */
function createWidgets(tableRow, readOnly, ownerEditorPerm, isCrossProject) {
  var widgets = document.createElement('td');
  widgets.setAttribute('class', 'rowwidgets nowrap');

  // TODO(jojwang): put gripper on the same line as the other widgets
  var gripper = document.createElement('div');
  gripper.setAttribute('class', 'gripper');
  gripper.innerText = '\u2059';
  widgets.appendChild(gripper);

  if (!readOnly) {
    if (ownerEditorPerm) {
      if (!isCrossProject) {
        var checkbox = document.createElement('input');
        setAttributes(checkbox, {'name': 'checkRangeSelect',
                                 'id': 'cb_'+tableRow['localID'],
                                 'type': 'checkbox'});
        widgets.appendChild(checkbox);
      }
    }
    var star = document.createElement('a');
    var starColor = tableRow['isStarred'] ? 'cornflowerblue' : 'gray';
    var starred = tableRow['isStarred'] ? 'Un-s' : 'S' ;
    setAttributes(star, {'name': 'star',
                         'id': 'star-' + tableRow['projectName'] + tableRow['localID'],
                         'style': 'color:' + starColor,
                         'title': starred + 'tar this issue',
                         'data-project-name': tableRow['projectName'],
                         'data-local-id': tableRow['localID']});
    star.innerText = (tableRow['isStarred'] ? '\u2605' : '\u2606');
    widgets.appendChild(star);
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
  td.className += ' id';
  var aLink = document.createElement('a');
  aLink.setAttribute('href', tableRow['issueURL']);
  var aLinkContent = (isCrossProject ? (tableRow['projectName'] + ':') : '' ) + tableRow['localID'];
  aLink.innerText = aLinkContent;
  td.appendChild(aLink);
}


/**
 * Helper function to set attributes and add Nodes for an Summary cell.
 * @param {Element} td element to be added to current row in table.
 * @param {dict} cell dictionary {'projectName': 'name', .. } of relevant cell info.
*/
function createSummaryCell(td, cell) {
  td.setAttribute('width', '100%');
  fillValues(td, cell['values']);
  fillNonColumnLabels(td, cell['nonColLabels']);
}


/**
 * Helper function to set attributes and add Nodes for an Attribute or Unfilterable cell.
 * @param {Element} td element to be added to current row in table.
 * @param {dict} cell dictionary {'type': 'Summary', .. } of relevant cell info.
*/
function createAttrAndUnfiltCell(td, cell) {
  if(cell['noWrap'] == 'yes') {
    td.className += ' nowrap';
  }
  if(cell['align']) {
    td.setAttribute('align', cell['align']);
  }
  fillValues(td, cell['values']);
}


/**
 * Helper function to fill a td element with a cell's non-column labels.
 * @param {Element} td element to be added to current row in table.
 * @param {list} labels list of dictionaries with relevant (key, value) for each label
 */
function fillNonColumnLabels(td, labels) {
  labels.forEach( function(label) {
    var aLabel = document.createElement('a');
    setAttributes(aLabel, {'class': 'label', 'href': 'list?q=label:' + label['value']});
    if (label['isDerived']) {
      var i = document.createElement('i');
      i.innerText = label['value'];
      aLabel.appendChild(i);
    } else {
      aLabel.innerText = label['value'];
    }
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
      if (value['isDerived']) {
        var i = document.createElement('i');
        if (index == array.length-1) {
          i.innerText = value['item'];
        } else {
          i.innerText = (value['item'] + ',');
        }
        td.appendChild(i);
      } else {
        if (index == array.length-1) {
          td.innerText = td.innerText + value['item'];
        } else {
          td.innerText = td.innerText + value['item'] + ',';
        }
      }
    });
  } else {
    td.innerText = '---';
  }
}


/**
 * Helper function to create a table row.
 * @param {dict} tableRow dictionary {'projectName': 'name', .. } of relevant row info.
 * @param {dict} pageSettings dict of relevant settings for the hotlist and user viewing the page.
 */
function renderHotlistRow(tableRow, pageSettings) {
  var tr = document.createElement('tr');
  if (pageSettings['cursor'] || tableRow['issueRef']) {
    tr.setAttribute('class', 'ifOpened hoverTarget cursor_on drag_item');
  } else {
    tr.setAttribute('class', 'ifOpened hoverTarget cursor_off drag_item');
  }

  setAttributes(tr, {'data-idx': tableRow['idx'], 'data-id': tableRow['issueID']});
  widgets = createWidgets(tableRow, pageSettings['readOnly'],
                          ((pageSettings['ownerPerm'] == 'True') || (pageSettings['editorPerm'] == 'True')),
                          (pageSettings['isCrossProject'] == 'True'));
  tr.appendChild(widgets);
  tableRow['cells'].forEach(function(cell) {
    var td = document.createElement('td');
    td.setAttribute('class', 'col_' + cell['colIndex']);
    if (cell['type'] == 'ID') {
      createIDCell(td, tableRow, (pageSettings['isCrossProject'] == 'True'));
    } else if (cell['type'] == 'summary') {
      createSummaryCell(td, cell);
    } else{
      createAttrAndUnfiltCell(td, cell);
    }
    tr.appendChild(td);
  });
  spacing = document.createElement('td');
  spacing.innerText = '\xa0';
  tr.appendChild(spacing);
  return tr;
}


/**
 * Helper function to create the group header row
 * @param {dict} group dict of relevant values for the current group
 * @returns a <tr> element to be added to the current <tbody>
 */
function renderGroupRow(group) {
  var tr = document.createElement('tr');
  tr.setAttribute('class', 'group_row');
  var td = document.createElement('td');
  setAttributes(td, {'colspan': '100', 'class': 'toggleHidden',});
  var whenClosedImg = document.createElement('img');
  setAttributes(whenClosedImg, {'class': 'ifClosed', 'src': '/static/images/plus.gif',});
  td.appendChild(whenClosedImg);
  var whenOpenImg = document.createElement('img');
  setAttributes(whenOpenImg, {'class': 'ifOpened', 'src': '/static/images/minus.gif'});
  td.appendChild(whenOpenImg);
  tr.appendChild(td);

  div = document.createElement('div');
  div.innerText += group['rowsInGroup'];

  div.innerText += (group['rowsInGroup'] == '1' ? ' issue:': ' issues:')

  group['cells'].forEach(function(cell) {
    var hasValue = false;
    cell['values'].forEach(function(value) {
      if (value['item'] !== 'None') {
        hasValue = true;
      }
    });
    if (hasValue) {
      cell.values.forEach(function(value) {
        div.innerText += (' ' + cell['groupName'] + '=' + value['item']);
      });
    } else {
      div.innerText += (' -has:' + cell['groupName']);
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
  var tbody;
  var table = $('resultstable');

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
    if (tableRow['group'] !== 'no'){
      //add current tbody to table, need a new tbody with group row
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
  table.appendChild(tbody);
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
function activateDragDrop(tableData, pageSettings, hotlistID){
  function onHotlistRerank(srcID, targetID, position) {
    var data = {
      target_id: targetID,
      moved_ids: srcID,
      split_above: position == 'above',
    }
    CS_doPost(hotlistID + '/rerank.do', onHotlistResponse, data);
  }

  function onHotlistResponse(event) {
    var xhr = event.target;
    if (xhr.readyState != 4) {
      return;
    }
    if (xhr.status != 200) {
      window.console.error('200 page error')
      // TODO(jojwang): fill this in more
      return;
    }
    var response = CS_parseJSON(xhr);
    renderHotlistTable(
        (response['table_data'] == '' ? tableData : response['table_data']),
        pageSettings);
    // TODO(jojwang): pass pagination state to server
    _initDragAndDrop($('resultstable'), onHotlistRerank, true);
  }
  _initDragAndDrop($('resultstable'), onHotlistRerank, true);
}
