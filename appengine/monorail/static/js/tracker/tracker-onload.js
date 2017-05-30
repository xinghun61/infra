/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * This file contains the Monorail onload() function that is called
 * when each page loads.
 */



/**
 * This code is run on every DIT page load.  It registers a handler
 * for autocomplete on four different types of text fields based on the
 * name of that text field.
 */
function TKR_onload() {
  _ac_install();

  _ac_register(function (input, event) {
     if (input.id.startsWith('hotlists')) return TKR_hotlistsStore;
     if (input.id.startsWith('search')) return TKR_searchStore;
     if (input.id.startsWith('query_') || input.id.startsWith('predicate_'))
       return TKR_projectQueryStore;
     if (input.id.startsWith('cmd')) return TKR_quickEditStore;
     if (input.id.startsWith('label')) return TKR_labelStore;
     if (input.id.startsWith('component')) return TKR_componentListStore;
     if (input.id.startsWith('status')) return TKR_statusStore;
     if (input.id.startsWith('member')) return TKR_memberListStore;
     if (input.id == 'admin_names_editor') return TKR_memberListStore;
     if (input.id.startsWith('owner')) return TKR_ownerStore;
     if (input.name == 'needs_perm' || input.name == 'grants_perm') {
       return TKR_customPermissionsStore;
     }
     if (input.id == 'owner_editor') return TKR_ownerStore;
     if (input.className.indexOf('userautocomplete') != -1) {
       var customFieldIDStr = input.name;
       var uac = TKR_userAutocompleteStores[customFieldIDStr];
       if (uac) return uac;
       return TKR_ownerStore;
     }
     if (input.className.indexOf('autocomplete') != -1) {
       return TKR_autoCompleteStore;
     }
     if (input.id.startsWith('copy_to') || input.id.startsWith('move_to') ||
         input.id.startsWith('new_savedquery_projects') ||
         input.id.startsWith('savedquery_projects')) {
       return TKR_projectStore;
     }
   });

 _PC_Install();
 TKR_allColumnNames = _allColumnNames;
 TKR_labelFieldIDPrefix = _lfidprefix;
 TKR_allOrigLabels = _allOrigLabels;
 TKR_initialFormValues = TKR_currentFormValues();
}

// External names for functions that are called directly from HTML.
// JSCompiler does not rename functions that begin with an underscore.
// They are not defined with "var" because we want them to be global.

// TODO(jrobbins): the underscore names could be shortened by a
// cross-file search-and-replace script in our build process.

_selectAllIssues = TKR_selectAllIssues;
_selectNoneIssues = TKR_selectNoneIssues;

_toggleRows = TKR_toggleRows;
_toggleColumn = TKR_toggleColumn;
_toggleColumnUpdate = TKR_toggleColumnUpdate;
_addGroupBy = TKR_addGroupBy;
_addcol = TKR_addColumn;
_checkRangeSelect = TKR_checkRangeSelect;
_makeIssueLink = TKR_makeIssueLink;

_onload = TKR_onload;

_handleListActions = TKR_handleListActions;
_handleDetailActions = TKR_handleDetailActions;

_fetchOptions = TKR_fetchOptions;
_fetchUserProjects = TKR_fetchUserProjects;
_setACOptions = TKR_setUpAutoCompleteStore;
_openIssueUpdateForm = TKR_openIssueUpdateForm;
_addAttachmentFields = TKR_addAttachmentFields;

_acstore = _AC_SimpleStore;
_accomp = _AC_Completion;
_acreg = _ac_register;

_formatContextQueryArgs = TKR_formatContextQueryArgs;
_ctxArgs = "";
_ctxCan = undefined;
_ctxQuery = undefined;
_ctxSortspec = undefined;
_ctxGroupBy = undefined;
_ctxDefaultColspec = undefined;
_ctxStart = undefined;
_ctxNum = undefined;
_ctxResultsPerPage = undefined;

_filterTo = TKR_filterTo;
_sortUp = TKR_sortUp;
_sortDown = TKR_sortDown;

_closeAllPopups = TKR_closeAllPopups;
_closeSubmenus = TKR_closeSubmenus;
_showRight = TKR_showRight;
_showBelow = TKR_showBelow;
_highlightRow = TKR_highlightRow;
_floatMetadata = TKR_floatMetadata;
_floatVertically = TKR_floatVertically;

_setFieldIDs = TKR_setFieldIDs;
_selectTemplate = TKR_selectTemplate;
_saveTemplate = TKR_saveTemplate;
_newTemplate = TKR_newTemplate;
_deleteTemplate = TKR_deleteTemplate;
_switchTemplate = TKR_switchTemplate;
_templateNames = TKR_templateNames;

_confirmNovelStatus = TKR_confirmNovelStatus;
_confirmNovelLabel = TKR_confirmNovelLabel;
_vallab = TKR_validateLabel;
_exposeExistingLabelFields = TKR_exposeExistingLabelFields;
_confirmDiscardEntry = TKR_confirmDiscardEntry;
_confirmDiscardUpdate = TKR_confirmDiscardUpdate;
_lfidprefix = undefined;
_allOrigLabels = undefined;
_checkPlusOne = TKR_checkPlusOne;
_checkUnrestrict = TKR_checkUnrestrict;

_clearOnFirstEvent = TKR_clearOnFirstEvent;
_forceProperTableWidth = TKR_forceProperTableWidth;

_initialFormValues = TKR_initialFormValues;
_currentFormValues = TKR_currentFormValues;

_acof = _ac_onfocus;
_acmo = _ac_mouseover;
_acse = _ac_select;
_acrob = _ac_real_onblur;

// Variables that are given values in the HTML file.
_allColumnNames = [];

_go = TKR_go;
_getColspec = TKR_getColspecElement;
_getSearchColspec = TKR_getSearchColspecElement;

function closeAutocompleteAndIssuePreview(e) {
  _ac_fake_onblur(e);
}

if (BR_hasExcessBlurEvents()) {
  document.addEventListener('click', closeAutocompleteAndIssuePreview, false);
}
// Make the document actually listen for click events, otherwise the
// event handlers above would never get called.
if (document.captureEvents) document.captureEvents(Event.CLICK);

_setPeoplePrefs = TKR_setPeoplePrefs

_setupKibblesOnEntryPage = TKR_setupKibblesOnEntryPage;
_setupKibblesOnListPage = TKR_setupKibblesOnListPage;
_setupKibblesOnDetailPage = TKR_setupKibblesOnDetailPage;

_checkFieldNameOnServer = TKR_checkFieldNameOnServer;
_checkLeafName = TKR_checkLeafName;

_addMultiFieldValueWidget = TKR_addMultiFieldValueWidget;
_removeMultiFieldValueWidget = TKR_removeMultiFieldValueWidget;
_trimCommas = TKR_trimCommas;

_initDragAndDrop = TKR_initDragAndDrop;
