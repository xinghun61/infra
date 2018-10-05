// Copyright 2018 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package logdog implements a convenient interface wrapping the
// LogDog, Butler, and Annotee APIs from LUCI.
package logdog

import (
	"io"

	"go.chromium.org/luci/logdog/client/annotee"
	"go.chromium.org/luci/logdog/client/butler"
	"go.chromium.org/luci/logdog/client/butler/output"
	"go.chromium.org/luci/logdog/common/types"
)

// Options is passed to New to configure client creation.
type Options struct {
	// logdog://HOST/PROJECT/PREFIX/+/annotations
	AnnotationStream *types.StreamAddr
	// SourceInfo identifies the LogDog client (like UserAgent in
	// HTTP).
	SourceInfo []string
}

// Client is the LogDog client interface exported from this package.
// You must call Close to flush and close all of the resources.
type Client struct {
	output            output.Output
	butler            *butler.Butler
	processor         *annotee.Processor
	processorFinished chan struct{}
	readPipe          *io.PipeReader
	writePipe         *io.PipeWriter
}

// Stdout returns a Writer that is directly connected to the root
// LogDog stream.  This stream is parsed for @@@ annotations.
// See the annotee/basic package for more information about
// annotations.
//
// Do not write to this after calling Close on the Client.
func (c *Client) Stdout() io.Writer {
	return c.writePipe
}

// Close flushes and cleans up all currently initialized components of
// the Client, and returns the first error encountered.
func (c *Client) Close() (err error) {
	if c.writePipe != nil {
		if err2 := c.writePipe.Close(); err == nil {
			err = err2
		}
		c.writePipe = nil
	}
	if c.processorFinished != nil {
		<-c.processorFinished
		c.processorFinished = nil
	}
	if c.processor != nil {
		c.processor.Finish()
		c.processor = nil
	}
	if c.butler != nil {
		c.butler.Activate()
		if err2 := c.butler.Wait(); err == nil {
			err = err2
		}
		c.butler = nil
	}
	if c.output != nil {
		c.output.Close()
		c.output = nil
	}
	// Close read pipe after flushing all LogDog stuff.
	if c.readPipe != nil {
		if err2 := c.readPipe.Close(); err == nil {
			err = err2
		}
		c.readPipe = nil
	}
	return err
}
