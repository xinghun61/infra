/* Copyright 2018 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * This file contains JS functions that support a dialog for adding and removing
 * issues from hotlists in Monorail.
 */

(function() {
  window.__hotlists_dialog = window.__hotlists_dialog || {};

  // An optional IssueRef.
  // If set, we will not check for selected issues, and only add/remove issueRef
  // instead.
  window.__hotlists_dialog.issueRef = null;
  // A function to be called with the modified hotlists. If issueRef is set, the
  // hotlists for which the user is owner and the issue is part of will be
  // passed as well.
  window.__hotlists_dialog.onResponse = () => {};
  // A function to be called if there was an error updating the hotlists.
  window.__hotlists_dialog.onFailure = () => {};

  /**
   * A function to show the hotlist dialog.
   * It is the only function exported by this module.
   */
  function ShowUpdateHotlistDialog() {
    _FetchHotlists().then(_BuildDialog);
  }

  async function _CreateNewHotlistWithIssues() {
    let selectedIssueRefs;
    if (window.__hotlists_dialog.issueRef) {
      selectedIssueRefs = [window.__hotlists_dialog.issueRef];
    } else {
      selectedIssueRefs = _GetSelectedIssueRefs();
    }

    const name = await _CheckNewHotlistName();
    if (!name) {
      return;
    }

    const message = {
      name: name,
      summary: 'Hotlist of bulk added issues',
      issueRefs: selectedIssueRefs,
    };
    try {
      await window.prpcClient.call(
          'monorail.Features', 'CreateHotlist', message);
    } catch (error) {
      window.__hotlists_dialog.onFailure(error);
      return;
    }

    const newHotlist = [name, window.CS_env.loggedInUserEmail];
    const newIssueHotlists = [];
    window.__hotlists_dialog._issueHotlists.forEach(
        hotlist => newIssueHotlists.push(hotlist.split('_')));
    newIssueHotlists.push(newHotlist);
    window.__hotlists_dialog.onResponse([newHotlist], newIssueHotlists);
  }

  async function _UpdateIssuesInHotlists() {
    const hotlistRefsAdd = _GetSelectedHotlists(
        window.__hotlists_dialog._userHotlists);
    const hotlistRefsRemove = _GetSelectedHotlists(
        window.__hotlists_dialog._issueHotlists);
    if (hotlistRefsAdd.length === 0 && hotlistRefsRemove.length === 0) {
      alert('Please select/un-select some hotlists');
      return;
    }

    let selectedIssueRefs;
    if (window.__hotlists_dialog.issueRef) {
      selectedIssueRefs = [window.__hotlists_dialog.issueRef];
    } else {
      selectedIssueRefs = _GetSelectedIssueRefs();
    }

    if (hotlistRefsAdd.length > 0) {
      const message = {
        hotlistRefs: hotlistRefsAdd,
        issueRefs: selectedIssueRefs,
      };
      try {
        await window.prpcClient.call(
            'monorail.Features', 'AddIssuesToHotlists', message);
      } catch (error) {
        window.__hotlists_dialog.onFailure(error);
        return;
      }
      hotlistRefsAdd.forEach(hotlist => {
        window.__hotlists_dialog._issueHotlists.add(
            hotlist.name + '_' + hotlist.owner.user_id);
      });
    }

    if (hotlistRefsRemove.length > 0) {
      const message = {
        hotlistRefs: hotlistRefsRemove,
        issueRefs: selectedIssueRefs,
      };
      try {
        await window.prpcClient.call(
            'monorail.Features', 'RemoveIssuesFromHotlists', message);
      } catch (error) {
        window.__hotlists_dialog.onFailure(error);
        return;
      }
      hotlistRefsRemove.forEach(hotlist => {
        window.__hotlists_dialog._issueHotlists.delete(
            hotlist.name + '_' + hotlist.owner.user_id);
      });
    }

    const modifiedHotlists = hotlistRefsAdd.concat(hotlistRefsRemove).map(
        hotlist => [hotlist.name, hotlist.owner.user_id]);
    const newIssueHotlists = [];
    window.__hotlists_dialog._issueHotlists.forEach(
        hotlist => newIssueHotlists.push(hotlist.split('_')));

    window.__hotlists_dialog.onResponse(modifiedHotlists, newIssueHotlists);
  }

  async function _FetchHotlists() {
    const userHotlistsMessage = {
      user: {
        display_name: window.CS_env.loggedInUserEmail,
      }
    };
    const userHotlistsResponse = await window.prpcClient.call(
        'monorail.Features', 'ListHotlistsByUser', userHotlistsMessage);

    // Here we have the list of all hotlists owned by the user. We filter out
    // the hotlists that already contain issueRef in the next paragraph of code.
    window.__hotlists_dialog._userHotlists = new Set();
    (userHotlistsResponse.hotlists || []).forEach(hotlist => {
      window.__hotlists_dialog._userHotlists.add(
          hotlist.name + '_' + hotlist.ownerRef.userId);
    });

    // Here we filter out the hotlists that are owned by the user, and that
    // contain issueRef from _userHotlists and save them into _issueHotlists.
    window.__hotlists_dialog._issueHotlists = new Set();
    if (window.__hotlists_dialog.issueRef) {
      const issueHotlistsMessage = {
        issue: window.__hotlists_dialog.issueRef,
      };
      const issueHotlistsResponse = await window.prpcClient.call(
          'monorail.Features', 'ListHotlistsByIssue', issueHotlistsMessage);
      (issueHotlistsResponse.hotlists || []).forEach(hotlist => {
        const hotlistRef = hotlist.name + '_' + hotlist.ownerRef.userId;
        if (window.__hotlists_dialog._userHotlists.has(hotlistRef)) {
          window.__hotlists_dialog._userHotlists.delete(hotlistRef);
          window.__hotlists_dialog._issueHotlists.add(hotlistRef);
        }
      });
    }
  }

  function _BuildDialog() {
    const table = $('js-hotlists-table');

    while (table.firstChild) {
      table.removeChild(table.firstChild);
    }

    if (window.__hotlists_dialog._issueHotlists.size > 0) {
      _UpdateRows(
          table, 'Remove issues from:',
          window.__hotlists_dialog._issueHotlists);
    }
    _UpdateRows(table, 'Add issues to:',
        window.__hotlists_dialog._userHotlists);
    _BuildCreateNewHotlist(table);

    $('update-issues-hotlists').style.display = 'block';
    $('save-issues-hotlists').addEventListener(
        'click', _UpdateIssuesInHotlists);
    $('cancel-update-hotlists').addEventListener('click', function() {
      $('update-issues-hotlists').style.display = 'none';
    });

  }

  function _BuildCreateNewHotlist(table) {
    const inputTr = document.createElement('tr');
    inputTr.classList.add('hotlist_rows');

    const inputCell = document.createElement('td');
    const input = document.createElement('input');
    input.setAttribute('id', 'text_new_hotlist_name');
    input.setAttribute('placeholder', 'New hotlist name');
    // Hotlist changes are automatic and should be ignored by
    // TKR_currentFormValues() and TKR_isDirty()
    input.setAttribute('ignore-dirty', true);
    input.addEventListener('input', _CheckNewHotlistName);
    inputCell.appendChild(input);
    inputTr.appendChild(inputCell);

    const buttonCell = document.createElement('td');
    const button = document.createElement('button');
    button.setAttribute('id', 'create-new-hotlist');
    button.addEventListener('click', _CreateNewHotlistWithIssues);
    button.textContent = 'Create New Hotlist';
    button.disabled = true;
    buttonCell.appendChild(button);
    inputTr.appendChild(buttonCell);

    table.appendChild(inputTr);

    const feedbackTr = document.createElement('tr');
    feedbackTr.classList.add('hotlist_rows');

    const feedbackCell = document.createElement('td');
    feedbackCell.setAttribute('colspan', '2');
    const feedback = document.createElement('span');
    feedback.classList.add('fielderror');
    feedback.setAttribute('id', 'hotlistnamefeedback');
    feedbackCell.appendChild(feedback);
    feedbackTr.appendChild(feedbackCell);

    table.appendChild(feedbackTr);
  }

  function _UpdateRows(table, title, hotlists) {
    const tr = document.createElement('tr');
    tr.classList.add('hotlist_rows');
    const addCell = document.createElement('td');
    const add = document.createElement('b');
    add.textContent = title;
    addCell.appendChild(add);
    tr.appendChild(addCell);
    table.appendChild(tr);

    hotlists.forEach(hotlist => {
      const hotlistParts = hotlist.split('_');
      const name = hotlistParts[0];

      const tr = document.createElement('tr');
      tr.classList.add('hotlist_rows');

      const cbCell = document.createElement('td');
      const cb = document.createElement('input');
      cb.classList.add('checkRangeSelect');
      cb.setAttribute('id', 'cb_hotlist_' + hotlist);
      cb.setAttribute('type', 'checkbox');
      // Hotlist changes are automatic and should be ignored by
      // TKR_currentFormValues() and TKR_isDirty()
      cb.setAttribute('ignore-dirty', true);
      cbCell.appendChild(cb);

      const nameCell = document.createElement('td');
      const label = document.createElement('label');
      label.htmlFor = cb.id;
      label.textContent = name;
      nameCell.appendChild(label);

      tr.appendChild(cbCell);
      tr.appendChild(nameCell);
      table.appendChild(tr);
    });
  }

  async function _CheckNewHotlistName() {
    const name = $('text_new_hotlist_name').value;
    const checkNameResponse = await window.prpcClient.call(
        'monorail.Features', 'CheckHotlistName', {name});

    if (checkNameResponse.error) {
      $('hotlistnamefeedback').textContent = checkNameResponse.error;
      $('create-new-hotlist').disabled = true;
      return null;
    }

    $('hotlistnamefeedback').textContent = '';
    $('create-new-hotlist').disabled = false;
    return name;
  }

  /**
  * Call GetSelectedIssuesRefs from tracker-editing.js and convert to an Array
  * of IssueRef PBs.
  */
  function _GetSelectedIssueRefs() {
    return GetSelectedIssuesRefs().map(issueRef => ({
      project_name: issueRef['project_name'],
      local_id: issueRef['id'],
    }));
  }

  /**
   * Get HotlistRef PBs for the hotlists that the user wants to add/remove the
   * selected issues to.
   */
  function _GetSelectedHotlists(hotlists) {
    const selectedHotlistRefs = [];
    hotlists.forEach(hotlist => {
      const checkbox = $('cb_hotlist_' + hotlist);
      const hotlistParts = hotlist.split('_');
      if (checkbox && checkbox.checked) {
        selectedHotlistRefs.push({
          name: hotlistParts[0],
          owner: {
            user_id: hotlistParts[1],
          }
        });
      }
    });
    return selectedHotlistRefs;
  }

  Object.assign(window.__hotlists_dialog, {ShowUpdateHotlistDialog});
})();
