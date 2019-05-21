/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * This file contains JS functions that support various issue editing
 * features of Monorail.  These editing features include: selecting
 * issues on the issue list page, adding attachments, expanding and
 * collapsing the issue editing form, and starring issues.
 *
 * Browser compatability: IE6, IE7, FF1.0+, Safari.
 */


/**
 * Here are some string constants that are used repeatedly in the code.
 */
let TKR_SELECTED_CLASS = 'selected';
let TKR_UNDEF_CLASS = 'undef';
let TKR_NOVEL_CLASS = 'novel';
let TKR_EXCL_CONFICT_CLASS = 'exclconflict';
let TKR_QUESTION_MARK_CLASS = 'questionmark';
let TKR_ATTACHPROMPT_ID = 'attachprompt';
let TKR_ATTACHAFILE_ID = 'attachafile';
let TKR_ATTACHMAXSIZE_ID = 'attachmaxsize';
let TKR_CURRENT_TEMPLATE_INDEX_ID = 'current_template_index';
let TKR_PROMPT_MEMBERS_ONLY_CHECKBOX_ID = 'members_only_checkbox';
let TKR_PROMPT_SUMMARY_EDITOR_ID = 'summary_editor';
let TKR_PROMPT_SUMMARY_MUST_BE_EDITED_CHECKBOX_ID =
    'summary_must_be_edited_checkbox';
let TKR_PROMPT_CONTENT_EDITOR_ID = 'content_editor';
let TKR_PROMPT_STATUS_EDITOR_ID = 'status_editor';
let TKR_PROMPT_OWNER_EDITOR_ID = 'owner_editor';
let TKR_PROMPT_ADMIN_NAMES_EDITOR_ID = 'admin_names_editor';
let TKR_OWNER_DEFAULTS_TO_MEMBER_CHECKBOX_ID =
    'owner_defaults_to_member_checkbox';
let TKR_OWNER_DEFAULTS_TO_MEMBER_AREA_ID =
    'owner_defaults_to_member_area';
let TKR_COMPONENT_REQUIRED_CHECKBOX_ID =
    'component_required_checkbox';
let TKR_PROMPT_COMPONENTS_EDITOR_ID = 'components_editor';
let TKR_FIELD_EDITOR_ID_PREFIX = 'tmpl_custom_';
let TKR_PROMPT_LABELS_EDITOR_ID_PREFIX = 'label';
let TKR_CONFIRMAREA_ID = 'confirmarea';
let TKR_DISCARD_YOUR_CHANGES = 'Discard your changes?';
// Note, users cannot enter '<'.
let TKR_DELETED_PROMPT_NAME = '<DELETED>';
// Display warning if labels contain the following prefixes.
// The following list is the same as tracker_constants.RESERVED_PREFIXES except
// for the 'hotlist' prefix. 'hostlist' will be added when it comes a full
// feature and when projects that use 'Hostlist-*' labels are transitioned off.
let TKR_LABEL_RESERVED_PREFIXES = [
  'id', 'project', 'reporter', 'summary', 'status', 'owner', 'cc',
  'attachments', 'attachment', 'component', 'opened', 'closed',
  'modified', 'is', 'has', 'blockedon', 'blocking', 'blocked', 'mergedinto',
  'stars', 'starredby', 'description', 'comment', 'commentby', 'label',
  'rank', 'explicit_status', 'derived_status', 'explicit_owner',
  'derived_owner', 'explicit_cc', 'derived_cc', 'explicit_label',
  'derived_label', 'last_comment_by', 'exact_component',
  'explicit_component', 'derived_component'];

/**
 * Select all the issues on the issue list page.
 */
function TKR_selectAllIssues() {
  TKR_selectIssues(true);
}


/**
 * Function to deselect all the issues on the issue list page.
 */
function TKR_selectNoneIssues() {
  TKR_selectIssues(false);
}


/**
 * Function to select or deselect all the issues on the issue list page.
 * @param {boolean} checked True means select issues, False means deselect.
 */
function TKR_selectIssues(checked) {
  let table = $('resultstable');
  for (let r = 0; r < table.rows.length; ++r) {
    let row = table.rows[r];
    let firstCell = row.cells[0];
    if (firstCell.tagName == 'TD') {
      for (let e = 0; e < firstCell.childNodes.length; ++e) {
        let element = firstCell.childNodes[e];
        if (element.tagName == 'INPUT' && element.type == 'checkbox') {
          element.checked = checked ? 'checked' : '';
          if (checked) {
            row.classList.add(TKR_SELECTED_CLASS);
          } else {
            row.classList.remove(TKR_SELECTED_CLASS);
          }
        }
      }
    }
  }
}


/**
 * The ID number to append to the next dynamically created file upload field.
 */
let TKR_nextFileID = 1;


/**
 * Function to dynamically create a new attachment upload field add
 * insert it into the page DOM.
 * @param {string} id The id of the parent HTML element.
 *
 * TODO(lukasperaza): use different nextFileID for separate forms on same page,
 *  e.g. issue update form and issue description update form
 */
function TKR_addAttachmentFields(id, attachprompt_id,
  attachafile_id, attachmaxsize_id) {
  if (TKR_nextFileID >= 16) {
    return;
  }
  if (typeof attachprompt_id === 'undefined')
    {attachprompt_id = TKR_ATTACHPROMPT_ID;}
  if (typeof attachafile_id === 'undefined')
    {attachafile_id = TKR_ATTACHAFILE_ID;}
  if (typeof attachmaxsize_id === 'undefined')
    {attachmaxsize_id = TKR_ATTACHMAXSIZE_ID;}
  let el = $(id);
  el.style.marginTop = '4px';
  let div = document.createElement('div');
  var id = 'file' + TKR_nextFileID;
  let label = TKR_createChild(div, 'label', null, null, 'Attach file:');
  label.setAttribute('for', id);
  let input = TKR_createChild(
    div, 'input', null, id, null, 'width:auto;margin-left:17px');
  input.setAttribute('type', 'file');
  input.name = id;
  let removeLink = TKR_createChild(
    div, 'a', null, null, 'Remove', 'font-size:x-small');
  removeLink.href = '#';
  removeLink.addEventListener('click', function(event) {
    console.log(arguments);
    let target = event.target;
    $(attachafile_id).focus();
    target.parentNode.parentNode.removeChild(target.parentNode);
    event.preventDefault();
  });
  el.appendChild(div);
  el.querySelector('input').focus();
  ++TKR_nextFileID;
  if (TKR_nextFileID < 16) {
    $(attachafile_id).textContent = 'Attach another file';
  } else {
    $(attachprompt_id).style.display = 'none';
  }
  $(attachmaxsize_id).style.display = '';
}


/**
 * Function to display the form so that the user can update an issue.
 */
function TKR_openIssueUpdateForm() {
  TKR_showHidden($('makechangesarea'));
  TKR_goToAnchor('makechanges');
  TKR_forceProperTableWidth();
  window.setTimeout(
    function() {
document.getElementById('addCommentTextArea').focus();
},
    100);
}


/**
 * The index of the template that is currently selected for editing
 * on the administration page for issues.
 */
let TKR_currentTemplateIndex = 0;


/**
 * Array of field IDs that are defined in the current project, set by call to setFieldIDs().
 */
let TKR_fieldIDs = [];


function TKR_setFieldIDs(fieldIDs) {
  TKR_fieldIDs = fieldIDs;
}


/**
 * This function displays the appropriate template text in a text field.
 * It is called after the user has selected one template to view/edit.
 * @param {Element} widget The list widget containing the list of templates.
 */
function TKR_selectTemplate(widget) {
  TKR_showHidden($('edit_panel'));
  TKR_currentTemplateIndex = widget.value;
  $(TKR_CURRENT_TEMPLATE_INDEX_ID).value = TKR_currentTemplateIndex;

  let content_editor = $(TKR_PROMPT_CONTENT_EDITOR_ID);
  TKR_makeDefined(content_editor);

  let can_edit = $('can_edit_' + TKR_currentTemplateIndex).value == 'yes';
  let disabled = can_edit ? '' : 'disabled';

  $(TKR_PROMPT_MEMBERS_ONLY_CHECKBOX_ID).disabled = disabled;
  $(TKR_PROMPT_MEMBERS_ONLY_CHECKBOX_ID).checked = $(
    'members_only_' + TKR_currentTemplateIndex).value == 'yes';
  $(TKR_PROMPT_SUMMARY_EDITOR_ID).disabled = disabled;
  $(TKR_PROMPT_SUMMARY_EDITOR_ID).value = $(
    'summary_' + TKR_currentTemplateIndex).value;
  $(TKR_PROMPT_SUMMARY_MUST_BE_EDITED_CHECKBOX_ID).disabled = disabled;
  $(TKR_PROMPT_SUMMARY_MUST_BE_EDITED_CHECKBOX_ID).checked = $(
    'summary_must_be_edited_' + TKR_currentTemplateIndex).value == 'yes';
  content_editor.disabled = disabled;
  content_editor.value = $('content_' + TKR_currentTemplateIndex).value;
  $(TKR_PROMPT_STATUS_EDITOR_ID).disabled = disabled;
  $(TKR_PROMPT_STATUS_EDITOR_ID).value = $(
    'status_' + TKR_currentTemplateIndex).value;
  $(TKR_PROMPT_OWNER_EDITOR_ID).disabled = disabled;
  $(TKR_PROMPT_OWNER_EDITOR_ID).value = $(
    'owner_' + TKR_currentTemplateIndex).value;
  $(TKR_OWNER_DEFAULTS_TO_MEMBER_CHECKBOX_ID).disabled = disabled;
  $(TKR_OWNER_DEFAULTS_TO_MEMBER_CHECKBOX_ID).checked = $(
    'owner_defaults_to_member_' + TKR_currentTemplateIndex).value == 'yes';
  $(TKR_COMPONENT_REQUIRED_CHECKBOX_ID).disabled = disabled;
  $(TKR_COMPONENT_REQUIRED_CHECKBOX_ID).checked = $(
    'component_required_' + TKR_currentTemplateIndex).value == 'yes';
  $(TKR_OWNER_DEFAULTS_TO_MEMBER_AREA_ID).disabled = disabled;
  $(TKR_OWNER_DEFAULTS_TO_MEMBER_AREA_ID).style.display =
      $(TKR_PROMPT_OWNER_EDITOR_ID).value ? 'none' : '';
  $(TKR_PROMPT_COMPONENTS_EDITOR_ID).disabled = disabled;
  $(TKR_PROMPT_COMPONENTS_EDITOR_ID).value = $(
    'components_' + TKR_currentTemplateIndex).value;

  // Blank out all custom field editors first, then fill them in during the next loop.
  for (var i = 0; i < TKR_fieldIDs.length; i++) {
    let fieldEditor = $(TKR_FIELD_EDITOR_ID_PREFIX + TKR_fieldIDs[i]);
    let holder = $('field_value_' + TKR_currentTemplateIndex + '_' + TKR_fieldIDs[i]);
    if (fieldEditor) {
      fieldEditor.disabled = disabled;
      fieldEditor.value = holder ? holder.value : '';
    }
  }

  var i = 0;
  while ($(TKR_PROMPT_LABELS_EDITOR_ID_PREFIX + i)) {
    $(TKR_PROMPT_LABELS_EDITOR_ID_PREFIX + i).disabled = disabled;
    $(TKR_PROMPT_LABELS_EDITOR_ID_PREFIX + i).value =
        $('label_' + TKR_currentTemplateIndex + '_' + i).value;
    i++;
  }

  $(TKR_PROMPT_ADMIN_NAMES_EDITOR_ID).disabled = disabled;
  $(TKR_PROMPT_ADMIN_NAMES_EDITOR_ID).value = $(
    'admin_names_' + TKR_currentTemplateIndex).value;

  let numNonDeletedTemplates = 0;
  for (var i = 0; i < TKR_templateNames.length; i++) {
    if (TKR_templateNames[i] != TKR_DELETED_PROMPT_NAME) {
      numNonDeletedTemplates++;
    }
  }
  if ($('delbtn')) {
    if (numNonDeletedTemplates > 1) {
      $('delbtn').disabled='';
    } else { // Don't allow the last template to be deleted.
      $('delbtn').disabled='disabled';
    }
  }
}


var TKR_templateNames = []; // Exported in tracker-onload.js


/**
 * Create a new issue template and add the needed form fields to the DOM.
 */
function TKR_newTemplate() {
  let newIndex = TKR_templateNames.length;
  let templateName = prompt('Name of new template?', '');
  templateName = templateName.replace(
    /[&<>"]/g, '' // " help emacs highlighing
  );
  if (!templateName) return;

  for (let i = 0; i < TKR_templateNames.length; i++) {
    if (templateName == TKR_templateNames[i]) {
      alert('Please choose a unique name.');
      return;
    }
  }

  TKR_addTemplateHiddenFields(newIndex, templateName);
  TKR_templateNames.push(templateName);

  let templateOption = TKR_createChild(
    $('template_menu'), 'option', null, null, templateName);
  templateOption.value = newIndex;
  templateOption.selected = 'selected';

  let developerOption = TKR_createChild(
    $('default_template_for_developers'), 'option', null, null, templateName);
  developerOption.value = templateName;

  let userOption = TKR_createChild(
    $('default_template_for_users'), 'option', null, null, templateName);
  userOption.value = templateName;

  TKR_selectTemplate($('template_menu'));
}


/**
 * Private function to append HTML for new hidden form fields
 * for a new issue template to the issue admin form.
 */
function TKR_addTemplateHiddenFields(templateIndex, templateName) {
  let parentEl = $('adminTemplates');
  TKR_appendHiddenField(
    parentEl, 'template_id_' + templateIndex, 'template_id_' + templateIndex, '0');
  TKR_appendHiddenField(parentEl, 'name_' + templateIndex,
    'name_' + templateIndex, templateName);
  TKR_appendHiddenField(parentEl, 'members_only_' + templateIndex);
  TKR_appendHiddenField(parentEl, 'summary_' + templateIndex);
  TKR_appendHiddenField(parentEl, 'summary_must_be_edited_' + templateIndex);
  TKR_appendHiddenField(parentEl, 'content_' + templateIndex);
  TKR_appendHiddenField(parentEl, 'status_' + templateIndex);
  TKR_appendHiddenField(parentEl, 'owner_' + templateIndex);
  TKR_appendHiddenField(
    parentEl, 'owner_defaults_to_member_' + templateIndex,
    'owner_defaults_to_member_' + templateIndex, 'yes');
  TKR_appendHiddenField(parentEl, 'component_required_' + templateIndex);
  TKR_appendHiddenField(parentEl, 'components_' + templateIndex);

  var i = 0;
  while ($('label_0_' + i)) {
    TKR_appendHiddenField(parentEl, 'label_' + templateIndex,
      'label_' + templateIndex + '_' + i);
    i++;
  }

  for (var i = 0; i < TKR_fieldIDs.length; i++) {
    let fieldId = 'field_value_' + templateIndex + '_' + TKR_fieldIDs[i];
    TKR_appendHiddenField(parentEl, fieldId, fieldId);
  }

  TKR_appendHiddenField(parentEl, 'admin_names_' + templateIndex);
  TKR_appendHiddenField(
    parentEl, 'can_edit_' + templateIndex, 'can_edit_' + templateIndex,
    'yes');
}


/**
 * Utility function to append string parts for one hidden field
 * to the given array.
 */
function TKR_appendHiddenField(parentEl, name, opt_id, opt_value) {
  let input = TKR_createChild(parentEl, 'input', null, opt_id || name);
  input.setAttribute('type', 'hidden');
  input.name = name;
  input.value = opt_value || '';
}


/**
 * Delete the currently selected issue template, and mark its hidden
 * form field as deleted so that they will be ignored when submitted.
 */
function TKR_deleteTemplate() {
  // Mark the current template name as deleted.
  TKR_templateNames.splice(
    TKR_currentTemplateIndex, 1, TKR_DELETED_PROMPT_NAME);
  $('name_' + TKR_currentTemplateIndex).value = TKR_DELETED_PROMPT_NAME;
  _toggleHidden($('edit_panel'));
  $('delbtn').disabled = 'disabled';
  TKR_rebuildTemplateMenu();
  TKR_rebuildDefaultTemplateMenu('default_template_for_developers');
  TKR_rebuildDefaultTemplateMenu('default_template_for_users');
}

/**
 * Utility function to rebuild the template menu on the issue admin page.
 */
function TKR_rebuildTemplateMenu() {
  let parentEl = $('template_menu');
  while (parentEl.childNodes.length)
    {parentEl.removeChild(parentEl.childNodes[0]);}
  for (let i = 0; i < TKR_templateNames.length; i++) {
    if (TKR_templateNames[i] != TKR_DELETED_PROMPT_NAME) {
      let option = TKR_createChild(
        parentEl, 'option', null, null, TKR_templateNames[i]);
      option.value = i;
    }
  }
}


/**
 * Utility function to rebuild a default template drop-down.
 */
function TKR_rebuildDefaultTemplateMenu(menuID) {
  let defaultTemplateName = $(menuID).value;
  let parentEl = $(menuID);
  while (parentEl.childNodes.length)
    {parentEl.removeChild(parentEl.childNodes[0]);}
  for (let i = 0; i < TKR_templateNames.length; i++) {
    if (TKR_templateNames[i] != TKR_DELETED_PROMPT_NAME) {
      let option = TKR_createChild(
        parentEl, 'option', null, null, TKR_templateNames[i]);
      option.values = TKR_templateNames[i];
      if (defaultTemplateName == TKR_templateNames[i]) {
        option.setAttribute('selected', 'selected');
      }
    }
  }
}


/**
 * Change the issue template to the specified one.
 * TODO(jrobbins): move to an AJAX implementation that would not reload page.
 *
 * @param {string} projectName The name of the current project.
 * @param {string} templateName The name of the template to switch to.
 */
function TKR_switchTemplate(projectName, templateName) {
  let ok = true;
  if (TKR_isDirty()) {
    ok = confirm('Switching to a different template will lose the text you entered.');
  }
  if (ok) {
    TKR_initialFormValues = TKR_currentFormValues();
    window.location = '/p/' + projectName +
      '/issues/entry?template=' + templateName;
  }
}

/**
 * Function to remove a CSS class and initial tip from a text widget.
 * Some text fields or text areas display gray textual tips to help the user
 * make use of those widgets.  When the user focuses on the field, the tip
 * disappears and is made ready for user input (in the normal text color).
 * @param {Element} el The form field that had the gray text tip.
 */
function TKR_makeDefined(el) {
  if (el.classList.contains(TKR_UNDEF_CLASS)) {
    el.classList.remove(TKR_UNDEF_CLASS);
    el.value = '';
  }
}


/**
 * Save the contents of the visible issue template text area into a hidden
 * text field for later submission.
 * Called when the user has edited the text of a issue template.
 */
function TKR_saveTemplate() {
  if (TKR_currentTemplateIndex) {
    $('members_only_' + TKR_currentTemplateIndex).value =
        $(TKR_PROMPT_MEMBERS_ONLY_CHECKBOX_ID).checked ? 'yes' : '';
    $('summary_' + TKR_currentTemplateIndex).value =
        $(TKR_PROMPT_SUMMARY_EDITOR_ID).value;
    $('summary_must_be_edited_' + TKR_currentTemplateIndex).value =
        $(TKR_PROMPT_SUMMARY_MUST_BE_EDITED_CHECKBOX_ID).checked ? 'yes' : '';
    $('content_' + TKR_currentTemplateIndex).value =
        $(TKR_PROMPT_CONTENT_EDITOR_ID).value;
    $('status_' + TKR_currentTemplateIndex).value =
        $(TKR_PROMPT_STATUS_EDITOR_ID).value;
    $('owner_' + TKR_currentTemplateIndex).value =
        $(TKR_PROMPT_OWNER_EDITOR_ID).value;
    $('owner_defaults_to_member_' + TKR_currentTemplateIndex).value =
        $(TKR_OWNER_DEFAULTS_TO_MEMBER_CHECKBOX_ID).checked ? 'yes' : '';
    $('component_required_' + TKR_currentTemplateIndex).value =
        $(TKR_COMPONENT_REQUIRED_CHECKBOX_ID).checked ? 'yes' : '';
    $('components_' + TKR_currentTemplateIndex).value =
        $(TKR_PROMPT_COMPONENTS_EDITOR_ID).value;
    $(TKR_OWNER_DEFAULTS_TO_MEMBER_AREA_ID).style.display =
        $(TKR_PROMPT_OWNER_EDITOR_ID).value ? 'none' : '';

    for (var i = 0; i < TKR_fieldIDs.length; i++) {
      let fieldID = TKR_fieldIDs[i];
      let fieldEditor = $(TKR_FIELD_EDITOR_ID_PREFIX + fieldID);
      if (fieldEditor) {
        _saveFieldValue(fieldID, fieldEditor.value);
      }
    }

    var i = 0;
    while ($('label_' + TKR_currentTemplateIndex + '_' + i)) {
      $('label_' + TKR_currentTemplateIndex + '_' + i).value =
         $(TKR_PROMPT_LABELS_EDITOR_ID_PREFIX + i).value;
      i++;
    }

    $('admin_names_' + TKR_currentTemplateIndex).value =
        $(TKR_PROMPT_ADMIN_NAMES_EDITOR_ID).value;
  }
}


function _saveFieldValue(fieldID, val) {
  let fieldValId = 'field_value_' + TKR_currentTemplateIndex + '_' + fieldID;
  $(fieldValId).value = val;
}


/**
 * This is a json string encoding of an array of form values after the initial
 * page load. It is used for comparison on page unload to prompt the user
 * before abandoning changes. It is initialized in TKR_onload().
*/
let TKR_initialFormValues;


/**
 * Returns a json string encoding of an array of all the values from user
 * input fields of interest (omits search box, e.g.)
 */
function TKR_currentFormValues() {
  let inputs = document.querySelectorAll('input, textarea, select, checkbox');
  let values = [];

  for (i = 0; i < inputs.length; i++) {
    // Don't include blank inputs. This prevents a popup if the user
    // clicks "add a row" for new labels but doesn't actually enter any
    // text into them. Also ignore search box contents.
    if (inputs[i].value && !inputs[i].hasAttribute('ignore-dirty') &&
        inputs[i].name != 'token') {
      values.push(inputs[i].value);
    }
  }

  return JSON.stringify(values);
}


/**
 * This function returns true if the user has made any edits to fields of
 * interest.
 */
function TKR_isDirty() {
  return TKR_initialFormValues != TKR_currentFormValues();
}


/**
 * The user has clicked the 'Discard' button on the issue update form.
 * If the form has been edited, ask if he/she is sure about discarding
 * before then navigating to the given URL.  This can go up to some
 * other page, or reload the current page with a fresh form.
 * @param {string} nextUrl The page to show after discarding.
 */
function TKR_confirmDiscardUpdate(nextUrl) {
  if (!TKR_isDirty() || confirm(TKR_DISCARD_YOUR_CHANGES)) {
    document.location = nextUrl;
  }
}


/**
 * The user has clicked the 'Discard' button on the issue entry form.
 * If the form has been edited, this function asks if he/she is sure about
 * discarding before doing it.
 * @param {Element} discardButton The 'Discard' button.
 */
function TKR_confirmDiscardEntry(discardButton) {
  if (!TKR_isDirty() || confirm(TKR_DISCARD_YOUR_CHANGES)) {
    TKR_go('list');
  }
}


/**
 * Normally, we show 2 rows of label editing fields when updating an issue.
 * However, if the issue has more than that many labels already, we make sure to
 * show them all.
 */
function TKR_exposeExistingLabelFields() {
  if ($('label3').value ||
      $('label4').value ||
      $('label5').value) {
    if ($('addrow1')) {
      _showID('LF_row2');
      _hideID('addrow1');
    }
  }
  if ($('label6').value ||
      $('label7').value ||
      $('label8').value) {
    _showID('LF_row3');
    _hideID('addrow2');
  }
  if ($('label9').value ||
      $('label10').value ||
      $('label11').value) {
    _showID('LF_row4');
    _hideID('addrow3');
  }
  if ($('label12').value ||
      $('label13').value ||
      $('label14').value) {
    _showID('LF_row5');
    _hideID('addrow4');
  }
  if ($('label15').value ||
      $('label16').value ||
      $('label17').value) {
    _showID('LF_row6');
    _hideID('addrow5');
  }
  if ($('label18').value ||
      $('label19').value ||
      $('label20').value) {
    _showID('LF_row7');
    _hideID('addrow6');
  }
  if ($('label21').value ||
      $('label22').value ||
      $('label23').value) {
    _showID('LF_row8');
    _hideID('addrow7');
  }
}


/**
 * Flag to indicate when the user has not yet caused any input events.
 * We use this to clear the placeholder in the new issue summary field
 * exactly once.
 */
let TKR_firstEvent = true;


/**
 * This is called in response to almost any user input event on the
 * issue entry page.  If the placeholder in the new issue sumary field has
 * not yet been cleared, then this function clears it.
 */
function TKR_clearOnFirstEvent(initialSummary) {
  if (TKR_firstEvent && $('summary').value == initialSummary) {
    TKR_firstEvent = false;
    $('summary').value = TKR_keepJustSummaryPrefixes($('summary').value);
  }
}

/**
 * Clear the summary, except for any prefixes of the form "[bracketed text]"
 * or "keyword:".  If there were any, add a trailing space.  This is useful
 * to people who like to encode issue classification info in the summary line.
 */
function TKR_keepJustSummaryPrefixes(s) {
  let matches = s.match(/^(\[[^\]]+\])+|^(\S+:\s*)+/);
  if (matches == null) {
    return '';
  }

  let prefix = matches[0];
  if (prefix.substr(prefix.length - 1) != ' ') {
    prefix += ' ';
  }
  return prefix;
}

/**
 * An array of label <input>s that start with reserved prefixes.
 */
let TKR_labelsWithReservedPrefixes = [];

/**
 * An array of label <input>s that are equal to reserved words.
 */
let TKR_labelsConflictingWithReserved = [];

/**
 * An array of novel issue status values entered by the user on the
 * current page. 'Novel' means that they are not well known and are
 * likely to be typos.  Note that this list will always have zero or
 * one element, but a list is used for consistency with the list of
 * novel labels.
 */
let TKR_novelStatuses = [];

/**
 * An array of novel issue label values entered by the user on the
 * current page. 'Novel' means that they are not well known and are
 * likely to be typos.
 */
let TKR_novelLabels = [];

/**
 * A boolean that indicates whether the entered owner value is valid or not.
 */
let TKR_invalidOwner = false;

/**
 * The user has changed the issue status text field.  This function
 * checks whether it is a well-known status value.  If not, highlight it
 * as a potential typo.
 * @param {Element} textField The issue status text field.
 * @return Always returns true to indicate that the browser should
 * continue to process the user input event normally.
 */
function TKR_confirmNovelStatus(textField) {
  let v = textField.value.trim().toLowerCase();
  let isNovel = (v !== '');
  let wellKnown = TKR_statusWords;
  for (let i = 0; i < wellKnown.length && isNovel; ++i) {
    let wk = wellKnown[i];
    if (v == wk.toLowerCase()) {
      isNovel = false;
    }
  }
  if (isNovel) {
    if (TKR_novelStatuses.indexOf(textField) == -1) {
      TKR_novelStatuses.push(textField);
    }
    textField.classList.add(TKR_NOVEL_CLASS);
  } else {
    if (TKR_novelStatuses.indexOf(textField) != -1) {
      TKR_novelStatuses.splice(TKR_novelStatuses.indexOf(textField), 1);
    }
    textField.classList.remove(TKR_NOVEL_CLASS);
  }
  TKR_updateConfirmBeforeSubmit();
  return true;
}


/**
 * The user has changed a issue label text field.  This function checks
 * whether it is a well-known label value.  If not, highlight it as a
 * potential typo.
 * @param {Element} textField An issue label text field.
 * @return Always returns true to indicate that the browser should
 * continue to process the user input event normally.
 *
 * TODO(jrobbins): code duplication with function above.
 */
function TKR_confirmNovelLabel(textField) {
  let v = textField.value.trim().toLowerCase();
  if (v.search('-') == 0) {
    v = v.substr(1);
  }
  let isNovel = (v !== '');
  if (v.indexOf('?') > -1) {
    isNovel = false; // We don't count labels that the user must edit anyway.
  }
  let wellKnown = TKR_labelWords;
  for (var i = 0; i < wellKnown.length && isNovel; ++i) {
    let wk = wellKnown[i];
    if (v == wk.toLowerCase()) {
      isNovel = false;
    }
  }

  let containsReservedPrefix = false;
  var textFieldWarningDisplayed = TKR_labelsWithReservedPrefixes.indexOf(textField) != -1;
  for (var i = 0; i < TKR_LABEL_RESERVED_PREFIXES.length; ++i) {
    if (v.startsWith(TKR_LABEL_RESERVED_PREFIXES[i] + '-')) {
      if (!textFieldWarningDisplayed) {
        TKR_labelsWithReservedPrefixes.push(textField);
      }
      containsReservedPrefix = true;
      break;
    }
  }
  if (!containsReservedPrefix && textFieldWarningDisplayed) {
    TKR_labelsWithReservedPrefixes.splice(
      TKR_labelsWithReservedPrefixes.indexOf(textField), 1);
  }

  let conflictsWithReserved = false;
  var textFieldWarningDisplayed =
      TKR_labelsConflictingWithReserved.indexOf(textField) != -1;
  for (var i = 0; i < TKR_LABEL_RESERVED_PREFIXES.length; ++i) {
    if (v == TKR_LABEL_RESERVED_PREFIXES[i]) {
      if (!textFieldWarningDisplayed) {
        TKR_labelsConflictingWithReserved.push(textField);
      }
      conflictsWithReserved = true;
      break;
    }
  }
  if (!conflictsWithReserved && textFieldWarningDisplayed) {
    TKR_labelsConflictingWithReserved.splice(
      TKR_labelsConflictingWithReserved.indexOf(textField), 1);
  }

  if (isNovel) {
    if (TKR_novelLabels.indexOf(textField) == -1) {
      TKR_novelLabels.push(textField);
    }
    textField.classList.add(TKR_NOVEL_CLASS);
  } else {
    if (TKR_novelLabels.indexOf(textField) != -1) {
      TKR_novelLabels.splice(TKR_novelLabels.indexOf(textField), 1);
    }
    textField.classList.remove(TKR_NOVEL_CLASS);
  }
  TKR_updateConfirmBeforeSubmit();
  return true;
}

/**
 * Dictionary { prefix:[textField,...], ...} for all the prefixes of any
 * text that has been entered into any label field.  This is used to find
 * duplicate labels and multiple labels that share an single exclusive
 * prefix (e.g., Priority).
 */
let TKR_usedPrefixes = {};

/**
 * This is a prefix to the HTML ids of each label editing field.
 * It varied by page, so it is set in the HTML page.  Needed to initialize
 * our validation across label input text fields.
 */
let TKR_labelFieldIDPrefix = '';

/**
 * Initialize the set of all used labels on forms that allow users to
 * enter issue labels.  Some labels are supplied in the HTML page
 * itself, and we do not want to offer duplicates of those.
 */
function TKR_prepLabelAC() {
  let i = 0;
  while ($('label'+i)) {
    TKR_validateLabel($('label'+i));
    i++;
  }
}

/**
 * Reads the owner field and determines if the current value is a valid member.
 */
function TKR_prepOwnerField(validOwners) {
  if ($('owneredit')) {
    currentOwner = $('owneredit').value;
    if (currentOwner == '') {
      // Empty owner field is not an invalid owner.
      invalidOwner = false;
      return;
    }
    invalidOwner = true;
    for (let i = 0; i < validOwners.length; i++) {
      let owner = validOwners[i].name;
      if (currentOwner == owner) {
        invalidOwner = false;
        break;
      }
    }
    TKR_invalidOwner = invalidOwner;
  }
}

/**
 * Keep track of which label prefixes have been used so that
 * we can not offer the same label twice and so that we can highlight
 * multiple labels that share an exclusive prefix.
 */
function TKR_updateUsedPrefixes(textField) {
  if (textField.oldPrefix != undefined) {
    DeleteArrayElement(TKR_usedPrefixes[textField.oldPrefix], textField);
  }

  let prefix = textField.value.split('-')[0].toLowerCase();
  if (TKR_usedPrefixes[prefix] == undefined) {
    TKR_usedPrefixes[prefix] = [textField];
  } else {
    TKR_usedPrefixes[prefix].push(textField);
  }
  textField.oldPrefix = prefix;
}

/**
 * Go through all the label entry fields in our prefix-oriented
 * data structure and highlight any that are part of a conflict
 * (multiple labels with the same exclusive prefix).  Unhighlight
 * any label text entry fields that are not in conflict.  And, display
 * a warning message to encourage the user to correct the conflict.
 */
function TKR_highlightExclusiveLabelPrefixConflicts() {
  let conflicts = [];
  for (let prefix in TKR_usedPrefixes) {
    let textFields = TKR_usedPrefixes[prefix];
    if (textFields == undefined || textFields.length == 0) {
      delete TKR_usedPrefixes[prefix];
    } else if (textFields.length > 1 &&
        FindInArray(TKR_exclPrefixes, prefix) != -1) {
      conflicts.push(prefix);
      for (var i = 0; i < textFields.length; i++) {
        var tf = textFields[i];
        tf.classList.add(TKR_EXCL_CONFICT_CLASS);
      }
    } else {
      for (var i = 0; i < textFields.length; i++) {
        var tf = textFields[i];
        tf.classList.remove(TKR_EXCL_CONFICT_CLASS);
      }
    }
  }
  if (conflicts.length > 0) {
    let severity = TKR_restrict_to_known ? 'Error' : 'Warning';
    let confirm_area = $(TKR_CONFIRMAREA_ID);
    if (confirm_area) {
      $('confirmmsg').textContent = (severity +
          ': Multiple values for: ' + conflicts.join(', '));
      confirm_area.className = TKR_EXCL_CONFICT_CLASS;
      confirm_area.style.display = '';
    }
  }
}

/**
 * Keeps track of any label text fields that have a value that
 * is bad enough to prevent submission of the form.  When this
 * list is non-empty, the submit button gets disabled.
 */
let TKR_labelsBlockingSubmit = [];

/**
 * Look for any "?" characters in the label and, if found,
 * make the label text red, prevent form submission, and
 * display on-page help to tell the user to edit those labels.
 * @param {Element} textField An issue label text field.
 */
function TKR_highlightQuestionMarks(textField) {
  let tfIndex = TKR_labelsBlockingSubmit.indexOf(textField);
  if (textField.value.indexOf('?') > -1 && tfIndex == -1) {
    TKR_labelsBlockingSubmit.push(textField);
    textField.classList.add(TKR_QUESTION_MARK_CLASS);
  } else if (textField.value.indexOf('?') == -1 && tfIndex > -1) {
    TKR_labelsBlockingSubmit.splice(tfIndex, 1);
    textField.classList.remove(TKR_QUESTION_MARK_CLASS);
  }

  let block_submit_msg = $('blocksubmitmsg');
  if (block_submit_msg) {
    if (TKR_labelsBlockingSubmit.length > 0) {
      block_submit_msg.textContent = 'You must edit labels that contain "?".';
    } else {
      block_submit_msg.textContent = '';
    }
  }
}

/**
 * The user has edited a label.  Display a warning if the label is
 * not a well known label, or if there are multiple labels that
 * share an exclusive prefix.
 * @param {Element} textField An issue label text field.
 */
function TKR_validateLabel(textField) {
  if (textField == undefined) return;
  TKR_confirmNovelLabel(textField);
  TKR_updateUsedPrefixes(textField);
  TKR_highlightExclusiveLabelPrefixConflicts();
  TKR_highlightQuestionMarks(textField);
}

// TODO(jrobbins): what about typos in owner and cc list?

/**
 * If there are any novel status or label values, we display a message
 * that explains that to the user so that they can catch any typos before
 * submitting them.  If the project is restricting input to only the
 * well-known statuses and labels, then show these as an error instead.
 * In that case, on-page JS will prevent submission.
 */
function TKR_updateConfirmBeforeSubmit() {
  let severity = TKR_restrict_to_known ? 'Error' : 'Note';
  let novelWord = TKR_restrict_to_known ? 'undefined' : 'uncommon';
  let msg = '';
  let labels = TKR_novelLabels.map(function(item) {
    return item.value;
  });
  if (TKR_novelStatuses.length > 0 && TKR_novelLabels.length > 0) {
    msg = severity + ': You are using an ' + novelWord + ' status and ' + novelWord + ' label(s): ' + labels.join(', ') + '.'; // TODO: i18n
  } else if (TKR_novelStatuses.length > 0) {
    msg = severity + ': You are using an ' + novelWord + ' status value.';
  } else if (TKR_novelLabels.length > 0) {
    msg = severity + ': You are using ' + novelWord + ' label(s): ' + labels.join(', ') + '.';
  }

  for (var i = 0; i < TKR_labelsWithReservedPrefixes.length; ++i) {
    msg += '\nNote: The label ' + TKR_labelsWithReservedPrefixes[i].value +
           ' starts with a reserved word. This is not recommended.';
  }
  for (var i = 0; i < TKR_labelsConflictingWithReserved.length; ++i) {
    msg += '\nNote: The label ' + TKR_labelsConflictingWithReserved[i].value +
           ' conflicts with a reserved word. This is not recommended.';
  }
  // Display the owner is no longer a member note only if an owner error is not
  // already shown on the page.
  if (TKR_invalidOwner && !$('ownererror')) {
    msg += '\nNote: Current owner is no longer a project member.';
  }

  let confirm_area = $(TKR_CONFIRMAREA_ID);
  if (confirm_area) {
    $('confirmmsg').textContent = msg;
    if (msg != '') {
      confirm_area.className = TKR_NOVEL_CLASS;
      confirm_area.style.display = '';
    } else {
      confirm_area.style.display = 'none';
    }
  }
}


/**
 * The user has selected a command from the 'Actions...' menu
 * on the issue list.  This function checks the selected value and carry
 * out the requested action.
 * @param {Element} actionsMenu The 'Actions...' <select> form element.
 */
function TKR_handleListActions(actionsMenu) {
  switch (actionsMenu.value) {
    case 'bulk':
      TKR_HandleBulkEdit();
      break;
    case 'colspec':
      TKR_closeAllPopups(actionsMenu);
      _showID('columnspec');
      _hideID('addissuesspec');
      break;
    case 'flagspam':
      TKR_flagSpam(true);
      break;
    case 'unflagspam':
      TKR_flagSpam(false);
      break;
    case 'addtohotlist':
      TKR_addToHotlist();
      break;
    case 'addissues':
      _showID('addissuesspec');
      _hideID('columnspec');
      setCurrentColSpec();
      break;
    case 'removeissues':
      HTL_removeIssues();
      break;
    case 'issuesperpage':
      break;
    case 'deletehotlist':
      HTL_deleteHotlist($('deletehotlistform'));
      break;
  }
  actionsMenu.value = 'moreactions';
}


async function TKR_handleDetailActions(localId) {
  let moreActions = $('more_actions');

  if (moreActions.value == 'delete') {
    $('copy_issue_form_fragment').style.display = 'none';
    $('move_issue_form_fragment').style.display = 'none';
    let ok = confirm(
      'Normally, you should just close issues by setting their status ' +
      'to a closed value.\n' +
      'Are you sure you want to delete this issue?');
    if (ok) {
      await window.prpcClient.call('monorail.Issues', 'DeleteIssue', {
        issueRef: {
          projectName: window.CS_env.projectName,
          localId: localId,
        },
        delete: true,
      });
      location.reload(true);
      return;
    }
  }

  if (moreActions.value == 'move') {
    $('move_issue_form_fragment').style.display = '';
    $('copy_issue_form_fragment').style.display = 'none';
    return;
  }
  if (moreActions.value == 'copy') {
    $('copy_issue_form_fragment').style.display = '';
    $('move_issue_form_fragment').style.display = 'none';
    return;
  }

  // If no action was taken, reset the dropdown to the 'More actions...' item.
  moreActions.value = '0';
}

/**
 * The user has selected the "Flag as spam..." menu item.
 */
async function TKR_flagSpam(isSpam) {
  const selectedIssueRefs = [];
  issueRefs.forEach((issueRef) => {
    const checkbox = $('cb_' + issueRef.id);
    if (checkbox && checkbox.checked) {
      selectedIssueRefs.push({
        projectName: issueRef.project_name,
        localId: issueRef.id,
      });
    }
  });
  if (selectedIssueRefs.length > 0) {
    if (!confirm((isSpam ? 'Flag' : 'Un-flag') +
        ' all selected issues as spam?')) {
      return;
    }
    await window.prpcClient.call('monorail.Issues', 'FlagIssues', {
      issueRefs: selectedIssueRefs,
      flag: isSpam,
    });
    location.reload(true);
  } else {
    alert('Please select some issues to flag as spam');
  }
}

function TKR_addToHotlist() {
  const selectedIssueRefs = GetSelectedIssuesRefs();
  if (selectedIssueRefs.length > 0) {
    window.__hotlists_dialog.ShowUpdateHotlistDialog();
  } else {
    alert('Please select some issues to add to a hotlist');
  }
}


function GetSelectedIssuesRefs() {
  let selectedIssueRefs = [];
  for (let i = 0; i < issueRefs.length; i++) {
    let checkbox = document.getElementById('cb_' + issueRefs[i]['id']);
    if (checkbox == null) {
      checkbox = document.getElementById(
        'cb_' + issueRefs[i]['project_name'] + ':' + issueRefs[i]['id']);
    }
    if (checkbox && checkbox.checked) {
      selectedIssueRefs.push(issueRefs[i]);
    }
  }
  return selectedIssueRefs;
}

function onResponseUpdateUI(modifiedHotlists, remainingHotlists) {
  const list = $('user-hotlists-list');
  while (list.firstChild) {
    list.removeChild(list.firstChild);
  }
  remainingHotlists.forEach((hotlist) => {
    const name = hotlist[0];
    const userId = hotlist[1];
    const url = `/u/${userId}/hotlists/${name}`;
    const hotlistLink = document.createElement('a');
    hotlistLink.setAttribute('href', url);
    hotlistLink.textContent = name;
    list.appendChild(hotlistLink);
    list.appendChild(document.createElement('br'));
  });
  $('user-hotlists').style.display = 'block';
  onAddIssuesResponse(modifiedHotlists);
}

function onAddIssuesResponse(modifiedHotlists) {
  const hotlistNames = modifiedHotlists.map((hotlist) => hotlist[0]).join(', ');
  $('notice').textContent = 'Successfully updated ' + hotlistNames;
  $('update-issues-hotlists').style.display = 'none';
  $('alert-table').style.display = 'table';
}

function onAddIssuesFailure(reason) {
  $('notice').textContent =
      'Some hotlists were not updated: ' + reason.description;
  $('update-issues-hotlists').style.display = 'none';
  $('alert-table').style.display = 'table';
}

/**
 * The user has selected the "Bulk Edit..." menu item.  Go to a page that
 * offers the ability to edit all selected issues.
 */
// TODO(jrobbins): cross-project bulk edit
function TKR_HandleBulkEdit() {
  let selectedIssueRefs = GetSelectedIssuesRefs();
  let selectedLocalIDs = [];
  for (let i = 0; i < selectedIssueRefs.length; i++) {
    selectedLocalIDs.push(selectedIssueRefs[i]['id']);
  }
  if (selectedLocalIDs.length > 0) {
    let selectedLocalIDString = selectedLocalIDs.join(',');
    let url = 'bulkedit?ids=' + selectedLocalIDString;
    TKR_go(url + _ctxArgs);
  } else {
    alert('Please select some issues to edit');
  }
}

/**
 * Clears the selected status value when the 'clear' operator is chosen.
 */
function TKR_ignoreWidgetIfOpIsClear(selectEl, inputID) {
  if (selectEl.value == 'clear') {
    document.getElementById(inputID).value = '';
  }
}

/**
 * Array of original labels on the served page, so that we can notice
 * when the used submits a form that has any Restrict-* labels removed.
 */
let TKR_allOrigLabels = [];


/**
 * Prevent users from easily entering "+1" comments.
 */
function TKR_checkPlusOne() {
  let c = $('addCommentTextArea').value;
  let instructions = (
    '\nPlease use the star icon instead.\n' +
      'Stars show your interest without annoying other users.');
  if (new RegExp('^\\s*[-+]+[0-9]+\\s*.{0,30}$', 'm').test(c) &&
      c.length < 150) {
    alert('This looks like a "+1" comment.' + instructions);
    return false;
  }
  if (new RegExp('^\\s*me too.{0,30}$', 'i').test(c)) {
    alert('This looks like a "me too" comment.' + instructions);
    return false;
  }
  return true;
}


/**
 * If the user removes Restrict-* labels, ask them if they are sure.
 */
function TKR_checkUnrestrict(prevent_restriction_removal) {
  let removedRestrictions = [];

  for (let i = 0; i < TKR_allOrigLabels.length; ++i) {
    let origLabel = TKR_allOrigLabels[i];
    if (origLabel.indexOf('Restrict-') == 0) {
      let found = false;
      let j = 0;
      while ($('label' + j)) {
        let newLabel = $('label' + j).value;
        if (newLabel == origLabel) {
          found = true;
          break;
        }
        j++;
      }
      if (!found) {
        removedRestrictions.push(origLabel);
      }
    }
  }

  if (removedRestrictions.length == 0) {
    return true;
  }

  if (prevent_restriction_removal) {
    let msg = 'You may not remove restriction labels.';
    alert(msg);
    return false;
  }

  let instructions = (
    'You are removing these restrictions:\n   ' +
      removedRestrictions.join('\n   ') +
      '\nThis may allow more people to access this issue.' +
      '\nAre you sure?');
  return confirm(instructions);
}


/**
 * Add a column to a list view by updating the colspec form element and
 * submiting an invisible <form> to load a new page that includes the column.
 * @param {string} colname The name of the column to start showing.
 */
function TKR_addColumn(colname) {
  let colspec = TKR_getColspecElement();
  colspec.value = colspec.value + ' ' + colname;
  $('colspecform').submit();
}


/**
 * Allow members to shift-click to select multiple issues.  This keeps
 * track of the last row that the user clicked a checkbox on.
 */
let TKR_lastSelectedRow = undefined;


/**
 * Return true if an event had the shift-key pressed.
 * @param {Event} evt The mouse click event.
 */
function TKR_hasShiftKey(evt) {
  evt = (evt) ? evt : (window.event) ? window.event : '';
  if (evt) {
    if (evt.modifiers) {
      return evt.modifiers & Event.SHIFT_MASK;
    } else {
      return evt.shiftKey;
    }
  }
  return false;
}


/**
 * Select one row: check the checkbox and use highlight color.
 * @param {Element} row the row containing the checkbox that the user clicked.
 * @param {boolean} checked True if the user checked the box.
 */
function TKR_rangeSelectRow(row, checked) {
  if (!row) {
    return;
  }
  if (checked) {
    row.classList.add('selected');
  } else {
    row.classList.remove('selected');
  }

  let td = row.firstChild;
  while (td && td.tagName != 'TD') {
    td = td.nextSibling;
  }
  if (!td) {
    return;
  }

  let checkbox = td.firstChild;
  while (checkbox && checkbox.tagName != 'INPUT') {
    checkbox = checkbox.nextSibling;
  }
  if (!checkbox) {
    return;
  }

  checkbox.checked = checked;
}


/**
 * If the user shift-clicked a checkbox, (un)select a range.
 * @param {Event} evt The mouse click event.
 * @param {Element} el The checkbox that was clicked.
 */
function TKR_checkRangeSelect(evt, el) {
  let clicked_row = el.parentNode.parentNode.rowIndex;
  if (clicked_row == TKR_lastSelectedRow) {
    return;
  }
  if (TKR_hasShiftKey(evt) && TKR_lastSelectedRow != undefined) {
    let results_table = $('resultstable');
    let delta = (clicked_row > TKR_lastSelectedRow) ? 1 : -1;
    for (let i = TKR_lastSelectedRow; i != clicked_row; i += delta) {
      TKR_rangeSelectRow(results_table.rows[i], el.checked);
    }
  }
  TKR_lastSelectedRow = clicked_row;
}


/**
 * Make a link to a given issue that includes context parameters that allow
 * the user to see the same list columns, sorting, query, and pagination state
 * if he/she ever navigates up to the list again.
 * @param {{issue_url: string}} issueRef The dict with info about an issue,
 *     including a url to the issue detail page.
 */
function TKR_makeIssueLink(issueRef) {
  return '/p/' + issueRef['project_name'] + '/issues/detail?id=' + issueRef['id'] + _ctxArgs;
}


/**
 * Hide or show a list column in the case where we already have the
 * data for that column on the page.
 * @param {number} colIndex index of the column that is being shown or hidden.
 */
function TKR_toggleColumnUpdate(colIndex) {
  let shownCols = TKR_getColspecElement().value.split(' ');
  let filteredCols = [];
  for (let i=0; i< shownCols.length; i++) {
    if (_allColumnNames[colIndex] != shownCols[i].toLowerCase()) {
      filteredCols.push(shownCols[i]);
    }
  }

  TKR_getColspecElement().value = filteredCols.join(' ');
  TKR_getSearchColspecElement().value = filteredCols.join(' ');
  TKR_toggleColumn('hide_col_' + colIndex);
}


/**
 * Convert a column into a groupby clause by removing it from the column spec
 * and adding it to the groupby spec, then reloading the page.
 * @param {number} colIndex index of the column that is being shown or hidden.
 */
function TKR_addGroupBy(colIndex) {
  let colName = _allColumnNames[colIndex];
  let shownCols = TKR_getColspecElement().value.split(' ');
  let filteredCols = [];
  for (var i=0; i < shownCols.length; i++) {
    if (shownCols[i] && colName != shownCols[i].toLowerCase()) {
      filteredCols.push(shownCols[i]);
    }
  }

  TKR_getColspecElement().value = filteredCols.join(' ');

  let groupSpec = $('groupbyspec');
  let shownGroupings = groupSpec.value.split(' ');
  let filteredGroupings = [];
  for (i=0; i < shownGroupings.length; i++) {
    if (shownGroupings[i] && colName != shownGroupings[i].toLowerCase()) {
      filteredGroupings.push(shownGroupings[i]);
    }
  }
  filteredGroupings.push(colName);
  groupSpec.value = filteredGroupings.join(' ');
  $('colspecform').submit();
}


/**
 * Add a multi-valued custom field editing widget.
 */
function TKR_addMultiFieldValueWidget(
  el, field_id, field_type, opt_validate_1, opt_validate_2, field_phase_name) {
  let widget = document.createElement('INPUT');
  widget.name = (field_phase_name && (
    field_phase_name != '')) ? `custom_${field_id}_${field_phase_name}`
    : `custom_${field_id}`;
  if (field_type == 'str' || field_type =='url') {
    widget.size = 90;
  }
  if (field_type == 'user') {
    widget.style = 'width:12em';
    widget.classList.add('userautocomplete');
    widget.classList.add('customfield');
    widget.classList.add('multivalued');
    widget.addEventListener('focus', function(event) {
      _acrob(null);
      _acof(event);
    });
  }
  if (field_type == 'int' || field_type == 'date') {
    widget.style.textAlign = 'right';
    widget.style.width = '12em';
    widget.min = opt_validate_1;
    widget.max = opt_validate_2;
  }
  if (field_type == 'int') {
    widget.type = 'number';
  } else if (field_type == 'date') {
    widget.type = 'date';
  }

  el.parentNode.insertBefore(widget, el);

  let del_button = document.createElement('U');
  del_button.onclick = function(event) {
    _removeMultiFieldValueWidget(event.target);
  };
  del_button.textContent = 'X';
  el.parentNode.insertBefore(del_button, el);
}


function TKR_removeMultiFieldValueWidget(el) {
  let target = el.previousSibling;
  while (target && target.tagName != 'INPUT') {
    target = target.previousSibling;
  }
  if (target) {
    el.parentNode.removeChild(target);
  }
  el.parentNode.removeChild(el); // the X itself
}


/**
 * Trim trailing commas and spaces off <INPUT type="email" multiple> fields
 * before submitting the form.
 */
function TKR_trimCommas() {
  let ccField = $('memberccedit');
  if (ccField) {
    ccField.value = ccField.value.replace(/,\s*$/, '');
  }
  ccField = $('memberenter');
  if (ccField) {
    ccField.value = ccField.value.replace(/,\s*$/, '');
  }
}


/**
 * Identify which issues have been checkedboxed for removal from hotlist.
 */
function HTL_removeIssues() {
  let selectedLocalIDs = [];
  for (let i = 0; i < issueRefs.length; i++) {
    issueRef = issueRefs[i]['project_name']+':'+issueRefs[i]['id'];
    let checkbox = document.getElementById('cb_' + issueRef);
    if (checkbox && checkbox.checked) {
      selectedLocalIDs.push(issueRef);
    }
  }

  if (selectedLocalIDs.length > 0) {
    if (!confirm('Remove all selected issues?')) {
      return;
    }
    let selectedLocalIDString = selectedLocalIDs.join(',');
    $('bulk_remove_local_ids').value = selectedLocalIDString;
    $('bulk_remove_value').value = 'true';
    setCurrentColSpec();

    let form = $('bulkremoveissues');
    form.submit();
  } else {
    alert('Please select some issues to remove');
  }
}

function setCurrentColSpec() {
  $('current_col_spec').value = TKR_getColspecElement().value;
}


async function saveNote(textBox, hotlistID) {
  const projectName = textBox.getAttribute('projectname');
  const localId = textBox.getAttribute('localid');
  await window.prpcClient.call(
    'monorail.Features', 'UpdateHotlistIssueNote', {
      hotlistRef: {
        hotlistId: hotlistID,
      },
      issueRef: {
        projectName: textBox.getAttribute('projectname'),
        localId: textBox.getAttribute('localid'),
      },
      note: textBox.value,
    });
  $(`itemnote_${projectName}_${localId}`).value = textBox.value;
}

// TODO(jojwang): monorail:4291, integrate this into autocomplete process
// to prevent calling ListStatuses twice.
/**
 * Load the status select element with possible project statuses.
 */
function TKR_loadStatusSelect(projectName, selectId, selected, isBulkEdit=false) {
  const projectRequestMessage = {
    project_name: projectName};
  const statusesPromise = window.prpcClient.call(
    'monorail.Projects', 'ListStatuses', projectRequestMessage);
  statusesPromise.then((statusesResponse) => {
    const jsonData = TKR_convertStatuses(statusesResponse);
    const statusSelect = document.getElementById(selectId);
    // An initial option with value='selected' had to be added in HTML
    // to prevent TKR_isDirty() from registering a change in the select input
    // even when the user has not selected a different value.
    // That option needs to be removed otherwise, screenreaders will announce
    // its existence.
    while (statusSelect.firstChild) {
      statusSelect.removeChild(statusSelect.firstChild);
    }
    // Add unrecognized status (can be empty status) to open statuses.
    let selectedFound = false;
    jsonData.open.concat(jsonData.closed).forEach((status) => {
      if (status.name === selected) {
        selectedFound = true;
      }
    });
    if (!selectedFound) {
      jsonData.open.unshift({name: selected});
    }
    // Add open statuses.
    if (jsonData.open.length > 0) {
      const openGroup =
          statusSelect.appendChild(createStatusGroup('Open', jsonData.open, selected, isBulkEdit));
    }
    if (jsonData.closed.length > 0) {
      statusSelect.appendChild(createStatusGroup('Closed', jsonData.closed, selected));
    }
  });
}

function createStatusGroup(groupName, options, selected, isBulkEdit=false) {
  const groupElement = document.createElement('optgroup');
  groupElement.label = groupName;
  options.forEach((option) => {
    const opt = document.createElement('option');
    opt.value = option.name;
    opt.selected = (selected === option.name) ? true : false;
    // Special case for when opt represents an empty status.
    if (opt.value === '') {
      if (isBulkEdit) {
        opt.textContent = '--- (no change)';
        opt.setAttribute('aria-label', 'no change');
      } else {
        opt.textContent = '--- (empty status)';
        opt.setAttribute('aria-label', 'empty status');
      }
    } else {
      opt.textContent = option.doc ? `${option.name} = ${option.doc}` : option.name;
    }
    groupElement.appendChild(opt);
  });
  return groupElement;
}

/**
 * Generate DOM for a filter rules preview section.
 */
function renderFilterRulesSection(section_id, heading, value_why_list) {
  let section = $(section_id);
  while (section.firstChild) {
    section.removeChild(section.firstChild);
  }
  if (value_why_list.length == 0) return false;

  section.appendChild(document.createTextNode(heading + ': '));
  for (let i = 0; i < value_why_list.length; ++i) {
    if (i > 0) {
      section.appendChild(document.createTextNode(', '));
    }
    let value = value_why_list[i].value;
    let why = value_why_list[i].why;
    let span = section.appendChild(
      document.createElement('span'));
    span.textContent = value;
    if (why) span.setAttribute('title', why);
  }
  return true;
}


/**
 * Generate DOM for a filter rules preview section bullet list.
 */
function renderFilterRulesListSection(section_id, heading, value_why_list) {
  let section = $(section_id);
  while (section.firstChild) {
    section.removeChild(section.firstChild);
  }
  if (value_why_list.length == 0) return false;

  section.appendChild(document.createTextNode(heading + ': '));
  let bulletList = document.createElement('ul');
  section.appendChild(bulletList);
  for (let i = 0; i < value_why_list.length; ++i) {
    let listItem = document.createElement('li');
    bulletList.appendChild(listItem);
    let value = value_why_list[i].value;
    let why = value_why_list[i].why;
    let span = listItem.appendChild(
      document.createElement('span'));
    span.textContent = value;
    if (why) span.setAttribute('title', why);
  }
  return true;
}


/**
 * Ask server to do a presubmit check and then display and warnings
 * as the user edits an issue.
 */
function TKR_presubmit() {
  const issue_form = (
    document.forms.create_issue_form || document.forms.issue_update_form);
  if (!issue_form) {
    return;
  }

  const inputs = issue_form.querySelectorAll(
    'input:not([type="file"]), textarea, select');
  if (!inputs) {
    return;
  }

  const valuesByName = new Map();
  for (const key in inputs) {
    if (!inputs.hasOwnProperty(key)) {
      continue;
    }
    const input = inputs[key];
    if (input.type === 'checkbox' && !input.checked) {
      continue;
    }
    if (!valuesByName.has(input.name)) {
      valuesByName.set(input.name, []);
    }
    valuesByName.get(input.name).push(input.value);
  }

  const issueDelta = TKR_buildIssueDelta(valuesByName);
  const issueRef = {project_name: window.CS_env.projectName};
  if (valuesByName.has('id')) {
    issueRef.local_id = valuesByName.get('id')[0];
  }

  const presubmitMessage = {
    issue_ref: issueRef,
    issue_delta: issueDelta,
  };
  const presubmitPromise = window.prpcClient.call(
    'monorail.Issues', 'PresubmitIssue', presubmitMessage);

  presubmitPromise.then((response) => {
    $('owner_avail_state').style.display = (
      response.ownerAvailabilityState ? '' : 'none');
    $('owner_avail_state').className = (
      'availability_' + response.ownerAvailabilityState);
    $('owner_availability').textContent = response.ownerAvailability;

    let derived_labels;
    if (response.derivedLabels) {
      derived_labels = renderFilterRulesSection(
        'preview_filterrules_labels', 'Labels', response.derivedLabels);
    }
    let derived_owner_email;
    if (response.derivedOwners) {
      derived_owner_email = renderFilterRulesSection(
        'preview_filterrules_owner', 'Owner', response.derivedOwners[0]);
    }
    let derived_cc_emails;
    if (response.derivedCcs) {
      derived_cc_emails = renderFilterRulesSection(
        'preview_filterrules_ccs', 'Cc', response.derivedCcs);
    }
    let warnings;
    if (response.warnings) {
      warnings = renderFilterRulesListSection(
        'preview_filterrules_warnings', 'Warnings', response.warnings);
    }
    let errors;
    if (response.errors) {
      errors = renderFilterRulesListSection(
        'preview_filterrules_errors', 'Errors', response.errors);
    }

    if (derived_labels || derived_owner_email || derived_cc_emails ||
        warnings || errors) {
      $('preview_filterrules_area').style.display = '';
    } else {
      $('preview_filterrules_area').style.display = 'none';
    }
  });
}

function HTL_deleteHotlist(form) {
  if (confirm('Are you sure you want to delete this hotlist? This cannot be undone.')) {
    $('delete').value = 'true';
    form.submit();
  }
}

function HTL_toggleIssuesShown(toggleIssuesButton) {
  const can = toggleIssuesButton.value;
  const hotlist_name = $('hotlist_name').value;
  let url = `${hotlist_name}?can=${can}`;
  const hidden_cols = $('colcontrol').classList.value;
  if (window.location.href.includes('&colspec') || hidden_cols) {
    const col_spec = TKR_getColspecElement().value;
    let sort = '';
    if ($('sort')) {
      sort = $('sort').value.split(' ').join('+');
    }
    url += `&sort=${sort}&colspec=${TKR_getColspecElement().value}`;
  }
  TKR_go(url);
}
