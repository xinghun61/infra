(function(window) {
  // TODO: make this dynamic so it works on prod too.
   const PREDICT_ENDPOINT =
       'https://monorail-predict.appspot.com/_predict';
   const DEBOUNCE_THRESH_MS = 2000;
   const LOG_ENDPOINT =
       'https://monorail-predict.appspot.com/_log';

  // Simple debouncer to handle text input. Don't try to get suggestions
  // until the user has stopped typing for a few seconds.
  function debounce(func) {
    var timeout;
    return function() {
      var later = function() {
        timeout = null;
        func.apply();
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, DEBOUNCE_THRESH_MS);
    };
  }

  var componentsEl, commentEl, suggestionsEl;

  // The user has clicked on a suggestion, which we assume means they accept
  // it. Add it to the list of components in the input and remvoe the
  // suggestion from the UI. Also remove the whole suggestions element if
  // the list is now empty, and log the accept so we know if it was useful
  // or not.
  function acceptSuggestion(evt) {
    var suggestion = evt.target.textContent;
    var current = componentsEl.value.split(',').map(function(el) {
      return el.trim();
    }).filter(function(el) {
      return el != '';
    });
    current.push(suggestion);
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
    if (!suggestionsEl) {
      suggestionsEl = document.createElement('div');
      suggestionsEl.style.display = 'flex';
      suggestionsEl.style.flexWrap = 'wrap';
      suggestionsEl.style.margin = '0.5em 0 0.5em 0';
      var labelEl = document.createElement('div');
      labelEl.textContent = 'Suggested Components:';
      labelEl.style.margin = '0.25em';
      labelEl.style.padding = '0.25em';
      suggestionsEl.appendChild(labelEl);
    } else {
      // Clear it out.
      while (suggestionsEl.firstChild) {
        suggestionsEl.removeChild(suggestionsEl.firstChild);
      }
    }
    resp.components.forEach(function(component) {
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
    var textArea = window.document.getElementById('comment');
    var data = {
      text: textArea.value,
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
    var textArea = window.document.getElementById('comment');
    if (!textArea) {
      return;
    }
    // TODO: call gatherTextAndPredict here on pageload too, for existing
    // issues that don't have components assigned.
    var safeGatherTextAndPredict = debounce(gatherTextAndPredict);

    // TODO: other events, like what if they paste text in rather than
    // manually typing it.
    textArea.addEventListener('keyup', safeGatherTextAndPredict);
  });
})(window);

