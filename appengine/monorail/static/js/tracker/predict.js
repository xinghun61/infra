(function(window) {
  // TODO: make this dynamic so it works on prod too.
   const PREDICT_ENDPOINT =
       'https://monorail-predict.appspot.com/_predict';
   const LOG_ENDPOINT =
       'https://monorail-predict.appspot.com/_log';

  var componentsEl, commentEl, suggestionsEl, newIssueTextArea,
      addCommentTextArea, issueSummaryInput, existingComments, componentEdit;

  function currentComponents() {
    var current = componentsEl.value.split(',').map(function(el) {
      return el.trim();
    }).filter(function(el) {
      return (!!el);
    });
    return current;
  }

  function caseInsensitiveContains(array, item) {
    return array.some(function(a) {
      return a.toLowerCase() == item.toLowerCase();
    });
   }

  // The user has clicked on a suggestion, which we assume means they accept
  // it. Add it to the list of components in the input and remove the
  // suggestion from the UI. Also remove the whole suggestions element if
  // the list is now empty, and log the accept so we know if it was useful
  // or not.
  function acceptSuggestion(evt) {
    var suggestion = evt.target.textContent;
    var current = currentComponents();
    if (!caseInsensitiveContains(current, suggestion)) {
      current.push(suggestion);
    }

    componentsEl.value = current.join(', ');
    suggestionsEl.removeChild(evt.target);
    if (suggestionsEl.childElementCount == 1) { // 1 being the label div.
      suggestionsEl.parentElement.removeChild(suggestionsEl);
    }

    // Log the accept.
    var params = [
      'acceptedSuggestion=' + encodeURIComponent(suggestion),
      // For new issues, this parameter isn't so useful. TODO: Find a way to
      // associate accept events with isssues during creation.
      'issueUrl=' + encodeURIComponent(window.location.href),
    ];
    fetch(LOG_ENDPOINT + '?' + params.join('&')).catch(function(error) {
      window.console.error('Failed to POST accept log.', error);
    });
  }

  // Update the list of suggested components.
  function updateComponents(resp) {
    componentsEl = document.getElementById('components');
    if (!componentsEl) {
      componentsEl = document.getElementById('componentedit');
    }
    // No permission to edit or specify components, nothing to suggest.
    if (!componentsEl) {
      return;
    }

    if (!suggestionsEl) {
      suggestionsEl = document.createElement('div');
      suggestionsEl.style.display = 'flex';
      suggestionsEl.style.flexWrap = 'wrap';
      suggestionsEl.style.margin = '0.5em 0 0.5em 0';
    } else {
      // Clear it out.
      while (suggestionsEl.firstChild) {
        suggestionsEl.removeChild(suggestionsEl.firstChild);
      }
    }

    var suggested = resp.components || [];
    var current = currentComponents();
    suggested = suggested.filter(function(comp) {
      return !caseInsensitiveContains(current, comp);
    });

    if (suggested.length == 0) {
      return;
    }

    var labelEl = document.createElement('div');
    labelEl.textContent = 'Suggested Components:';
    labelEl.style.margin = '0.25em';
    labelEl.style.padding = '0.25em';
    suggestionsEl.appendChild(labelEl);

    suggested.forEach(function(component) {
      var comp = document.createElement('div');
      comp.textContent = component;
      comp.className = 'component-suggestion';
      comp.title = 'Click to use this component';
      comp.addEventListener('click', acceptSuggestion);
      // TODO: UI for explicit rejection.
      suggestionsEl.appendChild(comp);
    });
    componentsEl.parentElement.appendChild(suggestionsEl);
  }

  function gatherTextAndPredict() {
    // Only suggest components if there are none already.
    if (componentEdit && componentEdit.value.trim() != '') {
      return;
    }

    var text = [];

    if (issueSummaryInput) {
      text.push(issueSummaryInput.value.trim())
    }

    if (newIssueTextArea) {
      text.push(newIssueTextArea.value.trim());
    }

    if (addCommentTextArea) {
      text.push(addCommentTextArea.value.trim());
    }

    if (existingComments) {
      for (var i = 0; i < existingComments.length; i++) {
        // Do not double-include the issue summary text, which also appears
        // in the #desc_comment_area textarea input.
        if (existingComments[i].id != 'desc_comment_area') {
          text.push(existingComments[i].textContent.trim());
        }
      }
    }

    var data = {
      text: text.join('\n').trim(),
      // TODO: other values?
    };

    CS_doPost(PREDICT_ENDPOINT, function(evt) {
      if (evt.target.responseText) {
        resp = JSON.parse(evt.target.responseText);
        updateComponents(resp);
      }
    }, data);
  }

  window.addEventListener('load', function() {
    // Only use this for chromium issues.
    var href = window.location.href;
    if (href.indexOf('/p/chromium') == -1) {
      return;
    }

    // TODO: call gatherTextAndPredict here on pageload too, for existing
    // issues that don't have components assigned.
    var safeGatherTextAndPredict = debounce(gatherTextAndPredict);
 
    newIssueTextArea = window.document.getElementById('comment');
    if (newIssueTextArea) {
      // TODO: other events, like what if they paste text in rather than
      // manually typing it.
      newIssueTextArea.addEventListener('keyup', safeGatherTextAndPredict);
    }

    addCommentTextArea =
        window.document.getElementById('addCommentTextArea');
    if (addCommentTextArea) {
      addCommentTextArea.addEventListener('keyup', safeGatherTextAndPredict);
    }

    issueSummaryInput = document.getElementById('summary');
    if (issueSummaryInput) {
      issueSummaryInput.addEventListener('keyup', safeGatherTextAndPredict);
    }

    existingComments = document.getElementsByClassName('issue_text');

    // If this is an issue edit page and the issue has no components assigned,
    // get some component suggestions on page load.
    componentEdit = document.getElementById('componentedit');
    if (href.indexOf('/p/chromium/issues/detail?id=') != -1 &&
        componentEdit && componentEdit.value.trim() == '') {
      gatherTextAndPredict();
    }
  });

})(window);

