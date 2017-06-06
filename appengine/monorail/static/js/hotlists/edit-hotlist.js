/**
 * Sets up the transfer ownership dialog box.
 * @param {Long} hotlist_id id of the current hotlist
*/
function initializeDialogBox(hotlist_id) {
  var transferContainer = $('transfer-ownership-container');
  $('transfer-ownership').addEventListener('click', function () {
    transferContainer.style.display = 'block';
  });

  var cancelButton = document.getElementById('cancel');

  cancelButton.addEventListener('click', function() {
    transferContainer.style.display = 'none';
  });

  $('hotlist_star').addEventListener('click', function () {
    _TKR_toggleStar($('hotlist_star'), null, null, null, hotlist_id);
  });

}

function initializeDialogBoxRemoveSelf() {
  /* Initialise the dialog box for removing self from the hotlist. */

  var removeSelfContainer = $('remove-self-container');
  $('remove-self').addEventListener('click', function () {
    removeSelfContainer.style.display = 'block';
  });

  var cancelButtonRS = document.getElementById('cancel-remove-self');

  cancelButtonRS.addEventListener('click', function () {
    removeSelfContainer.style.display = 'none';
  });

}
