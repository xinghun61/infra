// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// With lists a and b, get the elements that are in a but not in b.
// result = a - b
function arrayDifference(listA, listB, equals) {
  if (!equals) {
    equals = (a, b) => (a === b);
  }
  listA = listA || [];
  listB = listB || [];
  return listA.filter((a) => {
    return !listB.find((b) => (equals(a, b)));
  });
}

function loadAttachments(attachments) {
  if (!attachments || !attachments.length) return [];
  return attachments.map(_loadLocalFile);
}

function _loadLocalFile(f) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onloadend = () => {
      resolve({filename: f.name, content: btoa(r.result)});
    };
    r.onerror = () => {
      reject(r.error);
    };

    r.readAsBinaryString(f);
  });
}

export {arrayDifference, loadAttachments};
