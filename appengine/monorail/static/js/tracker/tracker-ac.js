/* Copyright 2016 The Chromium Authors. All Rights Reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

/**
 * This file contains the autocomplete configuration logic that is
 * specific to the issue fields of Monorail.  It depends on ac.js, our
 * modified version of the autocomplete library.
 */

/**
 * This is an autocomplete store that holds the hotlists of the current user.
 */
var TKR_hotlistsStore;

/**
 * This is an autocomplete store that holds well-known issue label
 * values for the current project.
 */
var TKR_labelStore;

/**
 * This is an autocomplete store that holds issue components.
 */
var TKR_componentListStore;

/**
 * This is an autocomplete store that holds many different kinds of
 * items that can be shown in the artifact search autocomplete.
 */
var TKR_searchStore;

/**
 * This is similar to TKR_searchStore, but does not include any suggestions
 * to use the "me" keyword. Using "me" is not a good idea for project canned
 * queries and filter rules.
 */
var TKR_projectQueryStore;

/**
 * This is an autocomplete store that holds items for the quick edit
 * autocomplete.
 */
// TODO(jrobbins): add options for fields and components.
var TKR_quickEditStore;

/**
 * This is a list of label prefixes that each issue should only use once.
 * E.g., each issue should only have one Priority-* label.  We do not prevent
 * the user from using multiple such labels, we just warn the user before
 * he/she submits.
 */
var TKR_exclPrefixes = [];

/**
 * This is an autocomplete store that holds custom permission names that
 * have already been used in this project.
 */
var TKR_customPermissionsStore;


/**
 * This is an autocomplete store that holds well-known issue status
 * values for the current project.
 */
var TKR_statusStore;


/**
 * This is an autocomplete store that holds the usernames of all the
 * members of the current project.  This is used for autocomplete in
 * the cc-list of an issue, where many user names can entered with
 * commas between them.
 */
var TKR_memberListStore;


/**
 * This is an autocomplete store that holds the projects that the current
 * user is contributor/member/owner of.
 */
var TKR_projectStore;

/**
 * This is an autocomplete store that holds the usernames of possible
 * issue owners in the current project.  The list of possible issue
 * owners is the same as the list of project members, but the behavior
 * of this autocompete store is different because the issue owner text
 * field can only accept one value.
 */
var TKR_ownerStore;


/**
 * This is an autocomplete store that holds any list of string for choices.
 */
var TKR_autoCompleteStore;


/**
 * An array of autocomplete stores used for user-type custom fields.
 */
var TKR_userAutocompleteStores = [];


/**
 * This boolean controls whether odd-ball status and labels are treated as
 * a warning or an error.  Normally, it is False.
 */
// TODO(jrobbins): split this into one option for statuses and one for labels.
var TKR_restrict_to_known;

/**
 * This substitute function should be used for multi-valued autocomplete fields
 * that are delimited by commas. When we insert an autocomplete value, replace
 * an entire search term. Add a comma and a space after it if it is a complete
 * search term.
 */
function TKR_acSubstituteWithComma(inputValue, caret, completable, completion) {
  var nextTerm = caret;
  while (inputValue.charAt(nextTerm) != ' ' && nextTerm < inputValue.length) {
    nextTerm++;
  }
  while (inputValue.charAt(nextTerm) == ' ' && nextTerm < inputValue.length) {
    nextTerm++;
  }
  return inputValue.substring(0, caret - completable.length) +
         completion.value + ', ' + inputValue.substring(nextTerm);
}

/**
 * When the prefix starts with '*', return the complete set of all
 * possible completions.
 * @param {string} prefix If this starts with '*', return all possible
 * completions.  Otherwise return null.
 * @param {Array} labelDefs The array of label names and docstrings.
 * @returns Array of new _AC_Completions for each possible completion, or null.
 */
function TKR_fullComplete(prefix, labelDefs) {
  if (!prefix.startsWith('*')) return null;
  var out = [];
  for (var i = 0; i < labelDefs.length; i++) {
    out.push(new _AC_Completion(labelDefs[i].name,
                                labelDefs[i].name,
                                labelDefs[i].doc));
  }
  return out;
}


/**
 * Constucts a list of all completions for both open and closed
 * statuses, with a header for each group.
 * @param {string} prefix If starts with '*', return all possible completions,
 * else return null.
 * @param {Array} openStatusDefs The array of open status values and
 * docstrings.
 * @param {Array} closedStatusDefs The array of closed status values
 * and docstrings.
 * @returns Array of new _AC_Completions for each possible completion, or null.
 */
function TKR_openClosedComplete(prefix, openStatusDefs, closedStatusDefs) {
  if (!prefix.startsWith('*')) return null;
  var out = [];
  out.push({heading:'Open Statuses:'}); // TODO: i18n
  for (var i = 0; i < openStatusDefs.length; i++) {
    out.push(new _AC_Completion(openStatusDefs[i].name,
                                openStatusDefs[i].name,
                                openStatusDefs[i].doc));
  }
  out.push({heading:'Closed Statuses:'});  // TODO: i18n
  for (var i = 0; i < closedStatusDefs.length; i++) {
    out.push(new _AC_Completion(closedStatusDefs[i].name,
                                closedStatusDefs[i].name,
                                closedStatusDefs[i].doc));
  }
  return out;
}


function TKR_setUpHotlistsStore(hotlists) {
  var docdict = {};
  var ref_strs = [];

  for (var i = 0; i < hotlists.length; i++) {
    ref_strs.push(hotlists[i]['ref_str']);
    docdict[hotlists[i]['ref_str']] = hotlists[i]['summary'];
  }

  TKR_hotlistsStore = new _AC_SimpleStore(ref_strs, docdict);
  TKR_hotlistsStore.substitute = TKR_acSubstituteWithComma;
}


/**
 * An array of definitions of all well-known issue statuses.  Each
 * definition has the name of the status value, and a docstring that
 * describes its meaning.
 */
var TKR_statusWords = [];


/**
 * Constuct a new autocomplete store with all the well-known issue
 * status values.  The store has some DIT-specific methods.
 * TODO(jrobbins): would it be easier to define my own class to use
 * instead of _AC_Simple_Store?
 * @param {Array} openStatusDefs An array of definitions of the
 * well-known open status values.  Each definition has a name and
 * docstring.
 * @param {Array} closedStatusDefs An array of definitions of the
 * well-known closed status values.  Each definition has a name and
 * docstring.
 */
function TKR_setUpStatusStore(openStatusDefs, closedStatusDefs) {
  var docdict = {};
  TKR_statusWords = [];
  for (var i = 0; i < openStatusDefs.length; i++) {
   var status = openStatusDefs[i];
   TKR_statusWords.push(status.name);
   docdict[status.name] = status.doc;
  }
  for (var i = 0; i < closedStatusDefs.length; i++) {
   var status = closedStatusDefs[i];
   TKR_statusWords.push(status.name);
   docdict[status.name] = status.doc;
  }

  TKR_statusStore = new _AC_SimpleStore(TKR_statusWords, docdict);

  TKR_statusStore.commaCompletes = false;

  TKR_statusStore.substitute =
  function(inputValue, cursor, completable, completion) {
    return completion.value;
  };

  TKR_statusStore.completable = function(inputValue, cursor) {
    if (!ac_everTyped) return '*status';
    return inputValue;
  }

  TKR_statusStore.completions = function(prefix, tofilter) {
    var fullList = TKR_openClosedComplete(prefix,
                                          openStatusDefs,
                                          closedStatusDefs);
    if (fullList) return fullList;
    return _AC_SimpleStore.prototype.completions.call(this, prefix, tofilter);
  }

}


/**
 * Simple function to add a given item to the list of items used to construct
 * an "autocomplete store", and also update the docstring that describes
 * that item.  They are stored separately for backward compatability with
 * autocomplete store logic that preceeded the introduction of descriptions.
 */
function TKR_addACItem(items, docDict, item, docStr) {
   items.push(item);
   docDict[item] = docStr;
}

/**
 * Adds a group of three items related to a date field.
 */
function TKR_addACDateItems(items, docDict, fieldName, humanReadable) {
  var today = new Date();
  var todayStr = (today.getFullYear() + '-' + (today.getMonth() + 1) + '-' +
    today.getDate());
  TKR_addACItem(items, docDict, fieldName + '>today-1',
    humanReadable + ' within the last N days');
  TKR_addACItem(items, docDict, fieldName + '>' + todayStr,
    humanReadable + ' after the specified date');
  TKR_addACItem(items, docDict, fieldName + '<today-1',
    humanReadable + ' more than N days ago');
}

/**
 * Add several autocomplete items to a word list that will be used to construct
 * an autocomplete store.  Also, keep track of description strings for each
 * item.  A search operator is prepended to the name of each item.  The opt_old
 * and opt_new parameters are used to transform Key-Value labels into Key=Value
 * search terms.
 */
function TKR_addACItemList(
    items, docDict, searchOp, acDefs, opt_old, opt_new) {
  var item;
  for (var i = 0; i < acDefs.length; i++) {
    var nameAndDoc = acDefs[i];
    item = searchOp + nameAndDoc.name;
    if (opt_old) {
      // Preserve any leading minus-sign.
      item = item.slice(0, 1) + item.slice(1).replace(opt_old, opt_new);
    }
    TKR_addACItem(items, docDict, item, nameAndDoc.doc)
  }
}


/**
 * Use information from an options feed to populate the artifact search
 * autocomplete menu.  The order of sections is: custom fields, labels,
 * components, people, status, special, dates.  Within each section,
 * options are ordered semantically where possible, or alphabetically
 * if there is no semantic ordering.  Negated options all come after
 * all normal options.
 */
function TKR_setUpSearchStore(
  labelDefs, memberDefs, openDefs, closedDefs, componentDefs, fieldDefs,
  indMemberDefs) {
  var searchWords = [];
  var searchWordsNeg = [];
  var docDict = {};

  // Treat Key-Value and OneWord labels separately.
  var keyValueLabelDefs = [];
  var oneWordLabelDefs = [];
  for (var i = 0; i < labelDefs.length; i++) {
    var nameAndDoc = labelDefs[i];
    if (nameAndDoc.name.indexOf('-') == -1) {
      oneWordLabelDefs.push(nameAndDoc)
    } else {
      keyValueLabelDefs.push(nameAndDoc)
    }
  }

  // Autocomplete for custom fields.
  for (i = 0; i < fieldDefs.length; i++) {
    var fieldName = fieldDefs[i]['field_name'];
    var fieldType = fieldDefs[i]['field_type'];
    if (fieldType == 'ENUM_TYPE') {
      var choices = fieldDefs[i]['choices'];
      TKR_addACItemList(searchWords, docDict, fieldName + '=', choices);
      TKR_addACItemList(searchWordsNeg, docDict, '-' + fieldName + '=', choices);
    } else if (fieldType == 'STR_TYPE') {
      TKR_addACItem(searchWords, docDict, fieldName + ':',
          fieldDefs[i]['docstring']);
    } else if (fieldType == 'DATE_TYPE') {
      TKR_addACItem(searchWords, docDict, fieldName + ':',
          fieldDefs[i]['docstring']);
      TKR_addACDateItems(searchWords, docDict, fieldName, fieldName);
    } else {
      TKR_addACItem(searchWords, docDict, fieldName + '=',
          fieldDefs[i]['docstring']);
    }
    TKR_addACItem(searchWords, docDict, 'has:' + fieldName,
        'Issues with any ' + fieldName + ' value');
    TKR_addACItem(searchWordsNeg, docDict, '-has:' + fieldName,
        'Issues with no ' + fieldName + ' value');
  }

  // Add suggestions with "me" first, because otherwise they may be impossible
  // to reach in a project that has a lot of members with emails starting with
  // "me".
  if (CS_env['loggedInUserEmail']) {
    TKR_addACItem(searchWords, docDict, 'owner:me', 'Issues owned by me');
    TKR_addACItem(searchWordsNeg, docDict, '-owner:me', 'Issues not owned by me');
    TKR_addACItem(searchWords, docDict, 'cc:me', 'Issues that CC me');
    TKR_addACItem(searchWordsNeg, docDict, '-cc:me', 'Issues that don\'t CC me');
    TKR_addACItem(searchWords, docDict, 'reporter:me', 'Issues I reported');
    TKR_addACItem(searchWordsNeg, docDict, '-reporter:me', 'Issues reported by others');
    TKR_addACItem(searchWords, docDict, 'commentby:me',
                  'Issues that I commented on');
    TKR_addACItem(searchWordsNeg, docDict, '-commentby:me',
                  'Issues that I didn\'t comment on');
  }

  TKR_addACItemList(searchWords, docDict, '', keyValueLabelDefs, '-', '=');
  TKR_addACItemList(searchWordsNeg, docDict, '-', keyValueLabelDefs, '-', '=');
  TKR_addACItemList(searchWords, docDict, 'label:', oneWordLabelDefs);
  TKR_addACItemList(searchWordsNeg, docDict, '-label:', oneWordLabelDefs);

  TKR_addACItemList(searchWords, docDict, 'component:', componentDefs);
  TKR_addACItemList(searchWordsNeg, docDict, '-component:', componentDefs);
  TKR_addACItem(searchWords, docDict, 'has:component',
      'Issues with any components specified');
  TKR_addACItem(searchWordsNeg, docDict, '-has:component',
      'Issues with no components specified');

  TKR_addACItemList(searchWords, docDict, 'owner:', indMemberDefs);
  TKR_addACItemList(searchWordsNeg, docDict, '-owner:', indMemberDefs);
  TKR_addACItemList(searchWords, docDict, 'cc:', memberDefs);
  TKR_addACItemList(searchWordsNeg, docDict, '-cc:', memberDefs);
  TKR_addACItem(searchWords, docDict, 'has:cc',
      'Issues with any cc\'d users');
  TKR_addACItem(searchWordsNeg, docDict, '-has:cc',
      'Issues with no cc\'d users');
  TKR_addACItemList(searchWords, docDict, 'reporter:', memberDefs);
  TKR_addACItemList(searchWordsNeg, docDict, '-reporter:', memberDefs);
  TKR_addACItemList(searchWords, docDict, 'status:', openDefs);
  TKR_addACItemList(searchWordsNeg, docDict, '-status:', openDefs);
  TKR_addACItemList(searchWords, docDict, 'status:', closedDefs);
  TKR_addACItemList(searchWordsNeg, docDict, '-status:', closedDefs);
  TKR_addACItem(searchWords, docDict, 'has:status',
      'Issues with any status');
  TKR_addACItem(searchWordsNeg, docDict, '-has:status',
      'Issues with no status');

  TKR_addACItem(searchWords, docDict, 'is:blocked',
                'Issues that are blocked');
  TKR_addACItem(searchWordsNeg, docDict, '-is:blocked',
                'Issues that are not blocked');
  TKR_addACItem(searchWords, docDict, 'has:blockedon',
                'Issues that are blocked');
  TKR_addACItem(searchWordsNeg, docDict, '-has:blockedon',
                'Issues that are not blocked');
  TKR_addACItem(searchWords, docDict, 'has:blocking',
                'Issues that are blocking other issues');
  TKR_addACItem(searchWordsNeg, docDict, '-has:blocking',
                'Issues that are not blocking other issues');
  TKR_addACItem(searchWords, docDict, 'has:mergedinto',
                'Issues that were merged into other issues');
  TKR_addACItem(searchWordsNeg, docDict, '-has:mergedinto',
                'Issues that were not merged into other issues');

  TKR_addACItem(searchWords, docDict, 'is:starred',
                'Starred by me');
  TKR_addACItem(searchWordsNeg, docDict, '-is:starred',
                'Not starred by me');
  TKR_addACItem(searchWords, docDict, 'stars>10',
                'More than 10 stars');
  TKR_addACItem(searchWords, docDict, 'stars>100',
                'More than 100 stars');
  TKR_addACItem(searchWords, docDict, 'summary:',
                'Search within the summary field');

  TKR_addACItemList(searchWords, docDict, 'commentby:', memberDefs);
  TKR_addACItem(searchWords, docDict, 'attachment:',
                'Search within attachment names');
  TKR_addACItem(searchWords, docDict, 'attachments>5',
                'Has more than 5 attachments');
  TKR_addACItem(searchWords, docDict, 'is:open', 'Issues that are open');
  TKR_addACItem(searchWordsNeg, docDict, '-is:open', 'Issues that are closed');
  TKR_addACItem(searchWords, docDict, 'has:owner',
                'Issues with some owner');
  TKR_addACItem(searchWordsNeg, docDict, '-has:owner',
                'Issues with no owner');
  TKR_addACItem(searchWords, docDict, 'has:attachments',
                'Issues with some attachments');
  TKR_addACItem(searchWords, docDict, 'id:1,2,3',
                'Match only the specified issues');
  TKR_addACItem(searchWords, docDict, 'id<100000',
                'Issues with IDs under 100,000');
  TKR_addACItem(searchWords, docDict, 'blockedon:1',
                'Blocked on the specified issues');
  TKR_addACItem(searchWords, docDict, 'blocking:1',
                'Blocking the specified issues');
  TKR_addACItem(searchWords, docDict, 'mergedinto:1',
                'Merged into the specified issues');
  TKR_addACItem(searchWords, docDict, 'is:ownerbouncing',
                'Issues with owners we cannot contact');
  TKR_addACItem(searchWords, docDict, 'is:spam', 'Issues classified as spam');
  // We do not suggest -is:spam because it is implicit.

  TKR_addACDateItems(searchWords, docDict, 'opened', 'Opened');
  TKR_addACDateItems(searchWords, docDict, 'modified', 'Modified');
  TKR_addACDateItems(searchWords, docDict, 'closed', 'Closed');
  TKR_addACDateItems(searchWords, docDict, 'ownermodified', 'Owner field modified');
  TKR_addACDateItems(searchWords, docDict, 'ownerlastvisit', 'Owner last visit');
  TKR_addACDateItems(searchWords, docDict, 'statusmodified', 'Status field modified');
  TKR_addACDateItems(
      searchWords, docDict, 'componentmodified', 'Component field modified');

  TKR_projectQueryStore = new _AC_SimpleStore(searchWords, docDict);

  searchWords = searchWords.concat(searchWordsNeg);

  TKR_searchStore = new _AC_SimpleStore(searchWords, docDict);

  // When we insert an autocomplete value, replace an entire search term.
  // Add just a space after it (not a comma) if it is a complete search term,
  // or leave the caret immediately after the completion if we are just helping
  // the user with the search operator.
  TKR_searchStore.substitute =
      function(inputValue, caret, completable, completion) {
        var nextTerm = caret;
        while (inputValue.charAt(nextTerm) != ' ' &&
               nextTerm < inputValue.length) {
          nextTerm++;
        }
        while (inputValue.charAt(nextTerm) == ' ' &&
               nextTerm < inputValue.length) {
          nextTerm++;
        }
        return inputValue.substring(0, caret - completable.length) +
               completion.value + ' ' + inputValue.substring(nextTerm);
      };
  TKR_searchStore.autoselectFirstRow =
      function() {
        return false;
      };

  TKR_projectQueryStore.substitute = TKR_searchStore.substitute;
  TKR_projectQueryStore.autoselectFirstRow = TKR_searchStore.autoselectFirstRow;
}


/**
 * Use information from an options feed to populate the issue quick edit
 * autocomplete menu.
 */
function TKR_setUpQuickEditStore(
  labelDefs, memberDefs, openDefs, closedDefs, indMemberDefs) {
  var qeWords = [];
  var docDict = {};

  // Treat Key-Value and OneWord labels separately.
  var keyValueLabelDefs = [];
  var oneWordLabelDefs = [];
  for (var i = 0; i < labelDefs.length; i++) {
    var nameAndDoc = labelDefs[i];
    if (nameAndDoc.name.indexOf('-') == -1) {
      oneWordLabelDefs.push(nameAndDoc)
    } else {
      keyValueLabelDefs.push(nameAndDoc)
    }
  }
  TKR_addACItemList(qeWords, docDict, '', keyValueLabelDefs, '-', '=');
  TKR_addACItemList(qeWords, docDict, '-', keyValueLabelDefs, '-', '=');
  TKR_addACItemList(qeWords, docDict, '', oneWordLabelDefs);
  TKR_addACItemList(qeWords, docDict, '-', oneWordLabelDefs);

  TKR_addACItem(qeWords, docDict, 'owner=me', 'Make me the owner');
  TKR_addACItem(qeWords, docDict, 'owner=----', 'Clear the owner field');
  TKR_addACItem(qeWords, docDict, 'cc=me', 'CC me on this issue');
  TKR_addACItem(qeWords, docDict, 'cc=-me', 'Remove me from CC list');
  TKR_addACItemList(qeWords, docDict, 'owner=', indMemberDefs);
  TKR_addACItemList(qeWords, docDict, 'cc=', memberDefs);
  TKR_addACItemList(qeWords, docDict, 'cc=-', memberDefs);
  TKR_addACItemList(qeWords, docDict, 'status=', openDefs);
  TKR_addACItemList(qeWords, docDict, 'status=', closedDefs);
  TKR_addACItem(qeWords, docDict, 'summary=""', 'Set the summary field');

  TKR_quickEditStore = new _AC_SimpleStore(qeWords, docDict);

  // When we insert an autocomplete value, replace an entire command part.
  // Add just a space after it (not a comma) if it is a complete part,
  // or leave the caret immediately after the completion if we are just helping
  // the user with the command operator.
  TKR_quickEditStore.substitute =
      function(inputValue, caret, completable, completion) {
        var nextTerm = caret;
        while (inputValue.charAt(nextTerm) != ' ' &&
               nextTerm < inputValue.length) {
          nextTerm++;
        }
        while (inputValue.charAt(nextTerm) == ' ' &&
               nextTerm < inputValue.length) {
          nextTerm++;
        }
        return inputValue.substring(0, caret - completable.length) +
               completion.value + ' ' + inputValue.substring(nextTerm);
      };
}



/**
 * Constuct a new autocomplete store with all the project
 * custom permissions.
 * @param {Array} customPermissions An array of custom permission names.
 */
function TKR_setUpCustomPermissionsStore(customPermissions) {
  customPermissions = customPermissions || [];
  var permWords = ['View', 'EditIssue', 'AddIssueComment', 'DeleteIssue'];
  var docdict = {
    'View': '', 'EditIssue': '', 'AddIssueComment': '', 'DeleteIssue': ''};
  for (var i = 0; i < customPermissions.length; i++) {
    permWords.push(customPermissions[i]);
    docdict[customPermissions[i]] = '';
  }

  TKR_customPermissionsStore = new _AC_SimpleStore(permWords, docdict);

  TKR_customPermissionsStore.commaCompletes = false;

  TKR_customPermissionsStore.substitute =
  function(inputValue, cursor, completable, completion) {
    return completion.value;
  };
}


/**
 * Constuct a new autocomplete store with all the well-known project
 * member user names and real names.  The store has some
 * monorail-specific methods.
 * TODO(jrobbins): would it be easier to define my own class to use
 * instead of _AC_Simple_Store?
 * @param {Array} memberDefs an array of member objects.
 * @param {Array} nonGroupMemberDefs an array of member objects who are not groups.
 */
function TKR_setUpMemberStore(memberDefs, nonGroupMemberDefs) {
  let memberWords = [];
  let indMemberWords = [];
  let docdict = {};

  memberDefs.forEach(memberDef => {
    memberWords.push(memberDef.name);
    docdict[memberDef.name] = null;
  });
  nonGroupMemberDefs.forEach(memberDef => {
    indMemberWords.push(memberDef.name);
  });

  TKR_memberListStore = new _AC_SimpleStore(memberWords, docdict);

  TKR_memberListStore.completions = function(prefix, tofilter) {
    var fullList = TKR_fullComplete(prefix, memberDefs);
    if (fullList) return fullList;
    return _AC_SimpleStore.prototype.completions.call(this, prefix, tofilter);
  }

  TKR_memberListStore.completable = function(inputValue, cursor) {
   if (inputValue == '') return '*member';
   return _AC_SimpleStore.prototype.completable.call(this, inputValue, cursor);
  }

  TKR_memberListStore.substitute = TKR_acSubstituteWithComma;

  TKR_ownerStore = new _AC_SimpleStore(indMemberWords, docdict);

  TKR_ownerStore.commaCompletes = false;

  TKR_ownerStore.substitute =
  function(inputValue, cursor, completable, completion) {
    return completion.value;
  };

  TKR_ownerStore.completions = function(prefix, tofilter) {
    var fullList = TKR_fullComplete(prefix, nonGroupMemberDefs);
    if (fullList) return fullList;
    return _AC_SimpleStore.prototype.completions.call(this, prefix, tofilter);
  };

  TKR_ownerStore.completable = function(inputValue, cursor) {
    if (!ac_everTyped) return '*owner';
    return inputValue;
  };

}


/**
 * Constuct one new autocomplete store for each user-valued custom
 * field that has a needs_perm validation requirement, and thus a
 * list of allowed user indexes.
 * TODO(jrobbins): would it be easier to define my own class to use
 * instead of _AC_Simple_Store?
 * @param {Array} fieldDefs An array of field definitions, only some
 * of which have a 'user_indexes' entry.
 */
function TKR_setUpUserAutocompleteStores(fieldDefs) {
  fieldDefs.forEach(fieldDef => {
    if (fieldDef.qualifiedMembers) {
      var us = makeOneUserAutocompleteStore(fieldDef);
      TKR_userAutocompleteStores['custom_' + fieldDef['field_id']] = us;
    }
  });
}

function makeOneUserAutocompleteStore(fieldDef) {
  var memberWords = [];
  var docdict = {};
  for (const member of fieldDef.qualifiedMembers) {
    memberWords.push(member.name);
    docdict[member.name] = member.doc;
  }

  var userStore = new _AC_SimpleStore(memberWords, docdict);
  userStore.commaCompletes = false;

  userStore.substitute =
  function(inputValue, cursor, completable, completion) {
    return completion.value;
  };

  userStore.completions = function(prefix, tofilter) {
    var fullList = TKR_fullComplete(prefix, fieldDef.qualifiedMembers);
    if (fullList) return fullList;
    return _AC_SimpleStore.prototype.completions.call(this, prefix, tofilter);
  };

  userStore.completable = function(inputValue, cursor) {
    if (!ac_everTyped) return '*custom';
    return inputValue;
  };

  return userStore;
}


/**
 * Constuct a new autocomplete store with all the components.
 * The store has some monorail-specific methods.
 * @param {Array} componentDefs An array of definitions of components.
 */
function TKR_setUpComponentStore(componentDefs) {
  var componentWords = [];
  var docdict = {};
  for (var i = 0; i < componentDefs.length; i++) {
   var component = componentDefs[i];
   componentWords.push(component.name);
   docdict[component.name] = component.doc;
  }

  TKR_componentListStore = new _AC_SimpleStore(componentWords, docdict);
  TKR_componentListStore.commaCompletes = false;

  TKR_componentListStore.completions = function(prefix, tofilter) {
    var fullList = TKR_fullComplete(prefix, componentDefs);
    if (fullList) return fullList;
    return _AC_SimpleStore.prototype.completions.call(this, prefix, tofilter);
  }

  TKR_componentListStore.substitute = TKR_acSubstituteWithComma;

  TKR_componentListStore.completable = function(inputValue, cursor) {
    if (inputValue == '') return '*component';
    return _AC_SimpleStore.prototype.completable.call(this, inputValue, cursor);
  }

}


/**
 * An array of definitions of all well-known issue labels.  Each
 * definition has the name of the label, and a docstring that
 * describes its meaning.
 */
var TKR_labelWords = [];


/**
 * Constuct a new autocomplete store with all the well-known issue
 * labels for the current project.  The store has some DIT-specific methods.
 * TODO(jrobbins): would it be easier to define my own class to use
 * instead of _AC_Simple_Store?
 * @param {Array} labelDefs An array of definitions of the project
 * members.  Each definition has a name and docstring.
 */
function TKR_setUpLabelStore(labelDefs) {
  TKR_labelWords = [];
  var docdict = {};
  for (var i = 0; i < labelDefs.length; i++) {
   var label = labelDefs[i];
   TKR_labelWords.push(label.name);
   docdict[label.name] = label.doc;
  }

  TKR_labelStore = new _AC_SimpleStore(TKR_labelWords, docdict);

  TKR_labelStore.commaCompletes = false;
  TKR_labelStore.substitute =
  function(inputValue, cursor, completable, completion) {
    return completion.value;
  };

  /* Given what the user typed, return the part of it that should be used
   * to determine the auto-complete options offered to the user. */
  TKR_labelStore.completable = function(inputValue, cursor) {
    if (cursor == 0) {
      return '*label'; // Show every well-known label that is not redundant.
    }
    var start = 0;
    for (var i = cursor; --i >= 0;) {
      var c = inputValue.charAt(i)
      if (c == ' ' || c == ',') {
        start = i + 1;
        break;
      }
    }
    var questionPos = inputValue.indexOf('?');
    if (questionPos >= 0) {
      // Ignore any "?" character and anything after it.
      inputValue = inputValue.substring(start, questionPos);
    }
    var result = inputValue.substring(start, cursor);
    if (inputValue.lastIndexOf('-') > 0 && !ac_everTyped) {
      // Act like a menu: offer all alternative values for the same prefix.
      result = inputValue.substring(
          start, Math.min(cursor, inputValue.lastIndexOf('-')));
    }
    if (inputValue.startsWith('Restrict-') && !ac_everTyped) {
      // If user is in the middle of 2nd part, use that to narrow the choices.
      result = inputValue;
      // If they completed 2nd part, give all choices matching 2-part prefix.
      if (inputValue.lastIndexOf('-') > 8) {
        result = inputValue.substring(
            start, Math.min(cursor, inputValue.lastIndexOf('-') + 1));
      }
    }

    return result;
  };

  /* Start with all labels or only those that match what the user typed so far,
   * then filter out any that would lead to conflicts or redundancy. */
  TKR_labelStore.completions = function(prefix, tofilter) {
    var comps = TKR_fullComplete(prefix, labelDefs);
    if (comps == null) {
      comps = _AC_SimpleStore.prototype.completions.call(
          this, prefix, tofilter);
    }

    var filtered_comps = [];
    for (var i = 0; i < comps.length; i++) {
      var prefix_parts = comps[i].value.split('-');
      var label_prefix = prefix_parts[0].toLowerCase();
      if (FindInArray(TKR_exclPrefixes, label_prefix) == -1 ||
          TKR_usedPrefixes[label_prefix] == undefined ||
          TKR_usedPrefixes[label_prefix].length == 0 ||
          (TKR_usedPrefixes[label_prefix].length == 1 &&
           TKR_usedPrefixes[label_prefix][0] == ac_focusedInput)) {
        var uniq = true;
        for (var p in TKR_usedPrefixes) {
          var textFields = TKR_usedPrefixes[p];
          for (var j = 0; j < textFields.length; j++) {
            var tf = textFields[j];
            if (tf.value.toLowerCase() == comps[i].value.toLowerCase() &&
                tf != ac_focusedInput) {
                uniq = false;
            }
          }
        }
        if (uniq) {
          filtered_comps.push(comps[i]);
        }
      }
    }

    return filtered_comps;
  };
}


/**
 * Constuct a new autocomplete store with the given strings as choices.
 * @param {Array} choices An array of autocomplete choices.
 */
function TKR_setUpAutoCompleteStore(choices) {
  TKR_autoCompleteStore = new _AC_SimpleStore(choices);
  var choicesDefs = []
  for (var i = 0; i < choices.length; ++i) {
    choicesDefs.push({'name': choices[i], 'doc': ''});
  }

  /**
   * Override the default completions() function to return a list of
   * available choices.  It proactively shows all choices when the user has
   * not yet typed anything.  It stops offering choices if the text field
   * has a pretty long string in it already.  It does not offer choices that
   * have already been chosen.
   */
  TKR_autoCompleteStore.completions = function(prefix, tofilter) {
    if (prefix.length > 18) {
      return [];
    }
    var comps = TKR_fullComplete(prefix, choicesDefs);
    if (comps == null) {
      comps = _AC_SimpleStore.prototype.completions.call(
          this, prefix, tofilter);
    }

    var usedComps = {}
    var textFields = document.getElementsByTagName('input');
    for (var i = 0; i < textFields.length; ++i) {
      if (textFields[i].classList.contains('autocomplete')) {
         usedComps[textFields[i].value] = true;
       }
    }
    var unusedComps = []
    for (i = 0; i < comps.length; ++i) {
      if (!usedComps[comps[i].value]) {
        unusedComps.push(comps[i]);
      }
    }

    return unusedComps;
  }

  /**
   * Override the default completable() function with one that gives a
   * special value when the user has not yet typed anything.  This
   * causes TKR_fullComplete() to show all choices.  Also, always consider
   * the whole textfield value as an input to completion matching.  Otherwise,
   * it would only consider the part after the last comma (which makes sense
   * for gmail To: and Cc: address fields).
   */
  TKR_autoCompleteStore.completable = function(inputValue, cursor) {
   if (inputValue == '') {
     return '*ac';
   }
   return inputValue;
  }

  /**
   * Override the default substitute() function to completely replace the
   * contents of the text field when the user selects a completion. Otherwise,
   * it would append, much like the Gmail To: and Cc: fields append autocomplete
   * selections.
   */
  TKR_autoCompleteStore.substitute =
  function(inputValue, cursor, completable, completion) {
    return completion.value;
  };

  /**
   * We consider the whole textfield to be one value, not a comma separated
   * list.  So, typing a ',' should not trigger an autocomplete selection.
   */
  TKR_autoCompleteStore.commaCompletes = false;
}


/**
 * XMLHTTP object used to fetch autocomplete options from the server.
 */
var TKR_optionsXmlHttp = undefined;

/**
 * Contact the server to fetch the set of autocomplete options for the
 * projects the user is contributor/member/owner of.
 * If multiValue is set to true then the projectStore is configured to
 * have support for multi-values (useful for example for saved queries where
 * a query can apply to multiple projects).
 */
function TKR_fetchUserProjects(multiValue) {
  // Set a request token to prevent XSRF leaking of user project lists.
  if (CS_env.token) {
    var postURL = '/hosting/projects.do';
    var xh = XH_XmlHttpCreate()
    var data = 'token=' + CS_env.token;
    var callback = multiValue ? TKR_fetchMultiValProjectsCallback
                              : TKR_fetchProjectsCallback;
    XH_XmlHttpPOST(xh, postURL, data, callback);
  }
}

/**
 * Sets up the projectStore based on the json data received.
 * The projectStore is setup with support for multiple values.
 * @param {event} event with xhr Response with JSON data of projects.
 */
function TKR_fetchMultiValProjectsCallback(event) {
  var projects = TKR_getMemberProjects(event)
  if (projects) {
    TKR_setUpProjectStore(projects, true);
  }
}

/**
 * Sets up the projectStore based on the json data received.
 * @param {event} event with xhr Response with JSON data of projects.
 */
function TKR_fetchProjectsCallback(event) {
  var projects = TKR_getMemberProjects(event)
  if (projects) {
    TKR_setUpProjectStore(projects, false);
  }
}

function TKR_getMemberProjects(event) {
  var xhr = event.target;
  if (xhr) {
    if (xhr.readyState != 4 || xhr.status != 200)
      return;

    var projects = [];
    var json = CS_parseJSON(xhr);
    for (var category in json) {
      switch (category) {
        case 'contributorto':
        case 'memberof':
        case 'ownerof':
          for (var i = 0; i < json[category].length; i++) {
            projects.push(json[category][i]);
          }
          break;
        case 'error':
          return;
        default:
          break;
      }
    }
    projects.sort();
    return projects;
  }
}


/**
 * Constuct a new autocomplete store with all the projects that the
 * current user has visibility into. The store has some monorail-specific
 * methods.
 * @param {Array} projects An array of project names.
 * @param {Boolean} multiValue Determines whether the store should support
 *                  multiple values.
 */
function TKR_setUpProjectStore(projects, multiValue) {
  var projectsDefs = []
  var docdict = {}
  for (var i = 0; i < projects.length; ++i) {
    projectsDefs.push({'name': projects[i], 'doc': ''});
    docdict[projects[i]] = '';
  }

  TKR_projectStore = new _AC_SimpleStore(projects, docdict);
  TKR_projectStore.commaCompletes = !multiValue;

  if (multiValue) {
    TKR_projectStore.substitute = TKR_acSubstituteWithComma;
  } else {
    TKR_projectStore.substitute =
      function(inputValue, cursor, completable, completion) {
        return completion.value;
      };
  }

  TKR_projectStore.completions = function(prefix, tofilter) {
    var fullList = TKR_fullComplete(prefix, projectsDefs);
    if (fullList) return fullList;
    return _AC_SimpleStore.prototype.completions.call(this, prefix, tofilter);
  };

  TKR_projectStore.completable = function(inputValue, cursor) {
    if (inputValue == '') return '*project';
    if (multiValue)
      return _AC_SimpleStore.prototype.completable.call(
          this, inputValue, cursor);
    else
      return inputValue;
  };
}


/**
 * Convert the object resulting of a monorail.Projects ListStatuses to
 * the format expected by TKR_fetchOptions.
 * @param {object} statusesResponse A pRPC ListStatusesResponse object.
 */
function TKR_convertStatuses(statusesResponse) {
  let statusDefs = statusesResponse.statusDefs || [];
  const jsonData = {};

  // Split statusDefs into open and closed name-doc objects.
  jsonData.open = [];
  jsonData.closed = [];
  for (const s of statusDefs) {
    const item = {
      name: s.status,
      doc: s.docstring,
    };
    if (s.meansOpen) {
      jsonData.open.push(item);
    } else {
      jsonData.closed.push(item);
    }
  }

  jsonData.strict = statusesResponse.restrictToKnown;

  return jsonData;
}


/**
 * Convert the object resulting of a monorail.Projects ListComponents to
 * the format expected by TKR_fetchOptions.
 * @param {object} componentsResponse A pRPC ListComponentsResponse object.
 */
function TKR_convertComponents(componentsResponse) {
  let componentDefs = (componentsResponse.componentDefs || []);
  const jsonData = {};

  // Filter out deprecated components and normalize to name-doc object.
  jsonData.components = [];
  for (const c of componentDefs) {
    if (!c.deprecated) {
      jsonData.components.push({
          name: c.path,
          doc: c.docstring,
      });
    }
  }

  return jsonData;
}


/**
 * Convert the object resulting of a monorail.Projects GetLabelOptions
 * call to the format expected by TKR_fetchOptions.
 * @param {object} labelsResponse A pRPC GetLabelOptionsResponse.
 */
function TKR_convertLabels(labelsResponse) {
  let labelOptions = (labelsResponse.labelOptions || []);
  let exclusiveLabelPrefixes = (labelsResponse.exclusiveLabelPrefixes || []);
  const jsonData = {};

  jsonData.labels = labelOptions.map(
      label => ({name: label.label, doc: label.docstring}));

  jsonData.excl_prefixes = exclusiveLabelPrefixes.map(
      prefix => prefix.toLowerCase());

  return jsonData;
}


/**
 * Convert the object resulting of a monorail.Projects GetVisibleMembers
 * call to the format expected by TKR_fetchOptions.
 * @param {object} visibleMembersResponse A pRPC GetVisibleMembersResponse.
 */
function TKR_convertVisibleMembers(visibleMembersResponse) {
  let groupRefs = (visibleMembersResponse.groupRefs || []);
  let userRefs = (visibleMembersResponse.userRefs || []);
  const jsonData = {};

  const groupEmails = new Set(groupRefs.map(
      groupRef => groupRef.displayName));

  jsonData.memberEmails = userRefs.map(
      userRef => ({name: userRef.displayName}));
  jsonData.nonGroupEmails = jsonData.memberEmails.filter(
      memberEmail => !groupEmails.has(memberEmail));

  return jsonData;
}


/**
 * Convert the object resulting of a monorail.Projects ListFields to
 * the format expected by TKR_fetchOptions.
 * @param {object} fieldsResponse A pRPC ListFieldsResponse object.
 */
function TKR_convertFields(fieldsResponse) {
  let fieldDefs = (fieldsResponse.fieldDefs || []);
  const jsonData = {};

  jsonData.fields = fieldDefs.map(field =>
      ({
        field_id: field.fieldRef.fieldId,
        field_name: field.fieldRef.fieldName,
        field_type: field.fieldRef.type,
        docstring: field.docstring,
        choices: (field.enumChoices || []).map(
            choice => ({name: choice.label, doc: choice.docstring})),
        qualifiedMembers: (field.userChoices || []).map(
            userRef => ({name: userRef.displayName})),
      })
  );

  return jsonData;
}


/**
 * Convert the object resulting of a monorail.Features ListHotlistsByUser
 * call to the format expected by TKR_fetchOptions.
 * @param {object} hotlistsResponse A pRPC ListHotlistsByUserResponse object.
 */
function TKR_convertHotlists(hotlistsResponse) {
  if (hotlistsResponse.hotlists === undefined) {
    return [];
  }

  let seen = new Set();
  let ambiguousNames = new Set();

  hotlistsResponse.hotlists.forEach(hotlist => {
    if (seen.has(hotlist.name)) {
      ambiguousNames.add(hotlist.name);
    }
    seen.add(hotlist.name);
  });

  const hotlists = hotlistsResponse.hotlists.map(hotlist => {
    let ref_str = hotlist.name;
    if (ambiguousNames.has(hotlist.name)) {
      ref_str = hotlist.owner_ref.display_name + ':' + ref_str;
    }
    return {ref_str: ref_str, summary: hotlist.summary};
  });

  return hotlists;
}


/**
 * Contact the server to fetch the set of autocomplete options for the
 * current project.  This is done with XMLHTTPRequest because the list
 * could be long, and most of the time, the user will only view an
 * issue not edit it.
 * @param {string} projectName The name of the current project.
 */
function TKR_fetchOptions(projectName) {
  let logger = null;
  // TODO(jeffcarp): Replace this dependency reliance with ES modules.
  if (typeof(ClientLogger) === 'function' && typeof(ga) === 'function') {
    logger = new ClientLogger('autocomplete');
    logger.logStart('populate-options', 'user-time');
  }

  const projectRequestMessage = {
    project_name: projectName};

  const fieldsRequestMessage = {
    project_name: projectName,
    include_user_choices: true};

  const userRequestMessage = {
    user: {
      display_name: window.CS_env.loggedInUserEmail,
    }};

  const statusesPromise = window.prpcClient.call(
      'monorail.Projects', 'ListStatuses', projectRequestMessage);
  const componentsPromise = window.prpcClient.call(
      'monorail.Projects', 'ListComponents', projectRequestMessage);
  const labelsPromise = window.prpcClient.call(
      'monorail.Projects', 'GetLabelOptions', projectRequestMessage);
  const visibleMembersPromise = window.prpcClient.call(
      'monorail.Projects', 'GetVisibleMembers', projectRequestMessage);
  const fieldsPromise = window.prpcClient.call(
      'monorail.Projects', 'ListFields', fieldsRequestMessage);
  const customPermissionsPromise = window.prpcClient.call(
      'monorail.Projects', 'GetCustomPermissions', projectRequestMessage);
  const hotlistsPromise = window.prpcClient.call(
      'monorail.Features', 'ListHotlistsByUser', userRequestMessage);

  const allPromises = [];

  allPromises.push(
      statusesPromise.then(statusesResponse => {
        const jsonData = TKR_convertStatuses(statusesResponse);

        TKR_setUpStatusStore(jsonData.open, jsonData.closed);
        TKR_restrict_to_known = jsonData.strict;

        return jsonData;
  }));

  allPromises.push(
      componentsPromise.then(componentsResponse => {
        const jsonData = TKR_convertComponents(componentsResponse);

        TKR_setUpComponentStore(jsonData.components);

        return jsonData;
  }));

  allPromises.push(
      labelsPromise.then(labelsResponse => {
        const jsonData = TKR_convertLabels(labelsResponse);

        TKR_exclPrefixes = jsonData.excl_prefixes;
        TKR_setUpLabelStore(jsonData.labels);

        return jsonData;
  }));

  allPromises.push(
      visibleMembersPromise.then(visibleMembersResponse => {
        const jsonData = TKR_convertVisibleMembers(visibleMembersResponse);

        TKR_setUpMemberStore(jsonData.memberEmails, jsonData.nonGroupEmails);
        TKR_prepOwnerField(jsonData.memberEmails);

        return jsonData;
  }));

  allPromises.push(
      fieldsPromise.then(fieldsResponse => {
        const jsonData = TKR_convertFields(fieldsResponse);

        TKR_setUpUserAutocompleteStores(jsonData.fields);

        return jsonData;
  }));

  // We won't need custom permissions or hotlists later, so there's no need to
  // add them to allPromises.
  customPermissionsPromise.then(customPermissionsResponse => {
    TKR_setUpCustomPermissionsStore(customPermissionsResponse.permissions);
  });

  hotlistsPromise.then(hotlistsResponse => {
    TKR_setUpHotlistsStore(TKR_convertHotlists(hotlistsResponse));
  });

  Promise.all(allPromises).then(responses => {
    // Merge result objects.
    const jsonData = {};
    for (const response of responses) {
      Object.assign(jsonData, response);
    }

    /* QuickEdit is not yet in Monorail. crbug.com/monorail/1926
    TKR_setUpQuickEditStore(
       jsonData.labels, jsonData.memberEmails, jsonData.open, jsonData.closed,
       jsonData.nonGroupEmails);
    */

    // We need to wait until both exclusive prefixes (in configPromise) and
    // labels (in labelsPromise) have been read.
    TKR_prepLabelAC(TKR_labelFieldIDPrefix);

    TKR_setUpSearchStore(
       jsonData.labels, jsonData.memberEmails, jsonData.open, jsonData.closed,
       jsonData.components, jsonData.fields, jsonData.nonGroupEmails);

    if (logger) {
      logger.logEnd('populate-options', 'user-time');
    }
  });
}
