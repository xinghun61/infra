/* Copyright 2019 The Chromium Authors. All rights reserved.
 *
 * Use of this source code is governed by a BSD-style
 * license that can be found in the LICENSE file or at
 * https://developers.google.com/open-source/licenses/bsd
 */

const parentSelect = document.getElementById('parent_to_invite');
const createButton = document.getElementById('create_linked_account_invite');
const acceptButtons = document.querySelectorAll('.incoming_invite');

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

// TODO(jrobbins): function to unlink accounts.
