// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package eventupload is a library for streaming events to BigQuery.
package eventupload

import (
	"errors"
	"fmt"
	"log"
	"os"
	"sync"
	"time"

	"cloud.google.com/go/bigquery"
	"golang.org/x/net/context"
)

var id idGenerator

type idGenerator struct {
	mu      *sync.Mutex
	counter int
	prefix  string
}

// Uploader contains the necessary data for streaming data to BigQuery.
type Uploader struct {
	datasetID string
	tableID   string
	u         *bigquery.Uploader
	s         bigquery.Schema
	timeout   time.Duration
}

func init() {
	var prefix string
	h, err := os.Hostname()
	if err != nil {
		log.Printf(fmt.Sprintf("eventupload: ERROR: os.Hostname() returns %s", err))
	} else {
		prefix = fmt.Sprintf("%s:%d:%d", h, os.Getpid(), time.Now().UnixNano())
	}
	id = idGenerator{prefix: prefix}
}

// NewUploader constructs a new Uploader struct.
//
// datasetID, tableID are identifiers passed to the BigQuery client to gain
// access to a particular table.
// skipInvalid, ignoreUnknown are options for bigquery.Uploader.
// timeout is used by Put to determine how long it should attempt to upload rows
// to BigQuery. Put automatically retries on transient errors, so a timeout is
// necessary to avoid indefinite retries in the event the error is not actually
// transient.
func NewUploader(ctx context.Context, datasetID, tableID string, skipInvalid, ignoreUnknown bool, timeout time.Duration) (*Uploader, error) {
	if id.prefix == "" {
		return nil, errors.New("error initializing prefix for insertID")
	}
	c, err := bigquery.NewClient(ctx, "chrome-infra-events")
	if err != nil {
		return nil, err
	}
	t := c.Dataset(datasetID).Table(tableID)
	md, err := t.Metadata(ctx)
	if err != nil {
		return nil, err
	}
	u := t.Uploader()
	u.SkipInvalidRows = skipInvalid
	u.IgnoreUnknownValues = ignoreUnknown
	return &Uploader{
		datasetID,
		tableID,
		u,
		md.Schema,
		timeout,
	}, nil
}

// Put uploads one or more rows to the BigQuery service. src is expected to
// be a struct matching the schema in Uploader, or a slice containing
// such structs. Put takes care of adding InsertIDs, used by BigQuery to
// deduplicate rows.
//
// Put returns a PutMultiError if one or more rows failed to be uploaded.
// The PutMultiError contains a RowInsertionError for each failed row.
//
// Put will retry on temporary errors. If the error persists, the call will
// run indefinitely. Because of this, Put adds a timeout to the Context.
//
// See bigquery documentation and source code for detailed information on how
// struct values are mapped to rows.
func (u Uploader) Put(ctx context.Context, src interface{}) error {
	ctx, cancel := context.WithTimeout(ctx, u.timeout)
	defer cancel()
	if err := u.u.Put(ctx, prepareSrc(u.s, src)); err != nil {
		return err
	}
	return nil
}

func prepareSrc(s bigquery.Schema, src interface{}) []*bigquery.StructSaver {
	var srcs []interface{}
	if sl, ok := src.([]interface{}); ok {
		srcs = sl
	} else {
		srcs = []interface{}{src}
	}

	var prepared []*bigquery.StructSaver
	for _, src := range srcs {
		ss := &bigquery.StructSaver{
			Schema:   s,
			InsertID: id.generateInsertID(),
			Struct:   src,
		}

		prepared = append(prepared, ss)
	}
	return prepared
}

func (id *idGenerator) generateInsertID() string {
	id.mu.Lock()
	defer id.mu.Unlock()
	insertID := fmt.Sprintf("%s:%d", id.prefix, id.counter)
	id.counter++
	return insertID
}
