// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"io"
	"os"

	"go.chromium.org/luci/common/errors"

	"infra/cmd/skylab_swarming_worker/internal/log"
)

// openFIFO opens a FIFO and returns a reader for it.  The write end
// of the FIFO is opened internally to not block opening the read end
// and also to allow more control over closing the pipe.  Closing the
// returned channel will close the write end.
func openFIFO(path string) (io.ReadCloser, chan<- struct{}, error) {
	c := make(chan struct{})
	go func() {
		w, err := os.OpenFile(path, os.O_WRONLY, 0666)
		if err != nil {
			log.Printf("Error opening fifo %s for write: %s", path, err)
			return
		}
		select {
		case <-c:
			w.Close()
		}
	}()
	r, err := os.OpenFile(path, os.O_RDONLY, 0666)
	if err != nil {
		close(c)
		return nil, nil, errors.Annotate(err, "open fifo %s for read", path).Err()
	}
	return r, c, nil
}
