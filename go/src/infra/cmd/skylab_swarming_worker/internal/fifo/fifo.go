// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package fifo implements FIFO utilities for skylab_swarming_worker.
package fifo

import (
	"io"
	"log"
	"os"

	"go.chromium.org/luci/common/errors"
)

// Copier encapsulates the operation of copying from a FIFO.
type Copier struct {
	done   <-chan struct{}
	closer chan<- struct{}
}

// Close closes the FIFO and waits for copying to finish.  Repeated
// calls do nothing.
//
// This closes the write fd for the FIFO that we hold and waits for
// the copying goroutine to read EOF.  The FIFO yields EOF only when
// all writers have been closed.  Thus, this will block on any writers
// that are still holding fds.
func (fc *Copier) Close() error {
	if fc.closer != nil {
		close(fc.closer)
		fc.closer = nil
	}
	<-fc.done
	return nil
}

// NewCopier creates a FIFO whose data is copied to the Writer.
// The copying is done in a goroutine.  The returned Copier must be
// closed to flush and terminate the copying.  This function does not
// block on opening the FIFO for reading.
func NewCopier(w io.Writer, path string) (*Copier, error) {
	if err := makeFIFO(path); err != nil {
		return nil, errors.Annotate(err, "copy from fifo %s", path).Err()
	}
	r, c, err := openFIFO(path)
	if err != nil {
		return nil, errors.Annotate(err, "copy from fifo %s", path).Err()
	}
	done := make(chan struct{})
	fc := Copier{
		done:   done,
		closer: c,
	}
	go func() {
		defer close(done)
		io.Copy(w, r)
	}()
	return &fc, nil
}

// openFIFO opens a FIFO and returns a reader for it.  A write fd for
// the FIFO is also opened internally.  This is for two reasons: to
// stop opening the read fd from blocking (opening read fds blocks
// until one write fd is opened), and to control closing the pipe so
// the pipe sends an EOF (the pipe closes when all write fds are
// closed).  Closing the returned channel will close the write fd.
//
// The common use pattern is to call this function to obtain the
// reader without blocking, then run a goroutine which reads from the
// reader while other processes open and write to the FIFO.  After all
// processes terminate, close the channel, which closes the pipe and
// sends EOF to the reading goroutine.
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
