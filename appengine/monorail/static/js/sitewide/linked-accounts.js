/* Copyright 2019 The Chromium Authors. All rights reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

const parentSelect = document.getElementById('parent_to_invite');
const createButton = document.getElementById('create_linked_account_invite');
const acceptButtons = document.querySelectorAll('.incoming_invite');
const unlinkButtons = document.querySelectorAll('.unlink_account');

function CreateLinkedAccountInvite(ev) {
  const email = parentSelect.value;
  const message = {
    email: email,
  };
  const inviteCall = window.prpcClient.call(
    'monorail.Users', 'InviteLinkedParent', message);
  inviteCall.then((resp) => {
    location.reload();
  }).catch((reason) => {
    console.error('Inviting failed: ' + reason);
  });
}

function AcceptIncomingInvite(ev) {
  const email = ev.target.attributes['data-email'].value;
  const message = {
    email: email,
  };
  const acceptCall = window.prpcClient.call(
    'monorail.Users', 'AcceptLinkedChild', message);
  acceptCall.then((resp) => {
    location.reload();
  }).catch((reason) => {
    console.error('Accepting failed: ' + reason);
  });
}


function UnlinkAccounts(ev) {
  const parent = ev.target.dataset.parent;
  const child = ev.target.dataset.child;
  const message = {
    parent: {display_name: parent},
    child: {display_name: child},
  };
  const unlinkCall = window.prpcClient.call(
    'monorail.Users', 'UnlinkAccounts', message);
  unlinkCall.then((resp) => {
    location.reload();
  }).catch((reason) => {
    console.error('Unlinking failed: ' + reason);
  });
}


if (parentSelect) {
  parentSelect.onchange = function(e) {
    const email = parentSelect.value;
    createButton.disabled = email ? '' : 'disabled';
  };
}

if (createButton) {
  createButton.onclick = CreateLinkedAccountInvite;
}

if (acceptButtons) {
  for (const acceptButton of acceptButtons) {
    acceptButton.onclick = AcceptIncomingInvite;
  }
}

if (unlinkButtons) {
  for (const unlinkButton of unlinkButtons) {
    unlinkButton.onclick = UnlinkAccounts;
  }
}
