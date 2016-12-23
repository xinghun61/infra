function initializeDialogBox(hotlist_id) {
  var transferDialog = document.getElementById('transfer-ownership-dialog');
  $('transfer-ownership').addEventListener('click', function () {
    transferDialog.showModal();
  });

  var cancelButton = document.getElementById('cancel');

  cancelButton.addEventListener('click', function() {
    transferDialog.close();
  });

  $('hotlist_star').addEventListener('click', function () {
    _TKR_toggleStar($('hotlist_star'), null, null, null, hotlist_id);
  });

}
