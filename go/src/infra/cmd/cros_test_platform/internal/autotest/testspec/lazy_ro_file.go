// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package testspec

import (
	"io"
	"os"
)

// Open the file at path lazily for ReadOnly access.
func openROLazy(path string) io.Reader {
	return &lazyROFile{Path: path}
}

// lazyROFile is a Read()er for a file at Path that opens the file only at the
// first Read().
type lazyROFile struct {
	Path string
	fd   io.Reader
}

func (c *lazyROFile) Read(b []byte) (n int, err error) {
	if err := c.ensureOpen(); err != nil {
		return 0, err
	}
	return c.fd.Read(b)
}

func (c *lazyROFile) ensureOpen() error {
	if c.fd != nil {
		return nil
	}
	fd, err := os.Open(c.Path)
	if err == nil {
		c.fd = fd
	}
	return err
}
