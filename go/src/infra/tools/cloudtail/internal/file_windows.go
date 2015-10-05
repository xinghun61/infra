// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"os"
	"syscall"
)

// For reasons why this is so complicated:
// https://codereview.appspot.com/8203043/

func OpenForSharedRead(name string) (*os.File, error) {
	if len(name) == 0 {
		return nil, os.ErrNotExist
	}
	lpFileName, err := syscall.UTF16PtrFromString(name)
	if err != nil {
		return nil, err
	}
	// Read only, shared access, no descriptor inheritance.
	handle, err := syscall.CreateFile(
		lpFileName,
		uint32(syscall.GENERIC_READ),
		uint32(syscall.FILE_SHARE_READ|syscall.FILE_SHARE_WRITE|syscall.FILE_SHARE_DELETE),
		nil,
		uint32(syscall.OPEN_EXISTING),
		syscall.FILE_ATTRIBUTE_NORMAL, 0)
	if err != nil {
		return nil, err
	}
	return os.NewFile(uintptr(handle), name), nil
}
