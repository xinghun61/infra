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
	"reflect"
	"sync"
	"time"

	"cloud.google.com/go/bigquery"
	"github.com/luci/luci-go/common/tsmon/field"
	"github.com/luci/luci-go/common/tsmon/metric"
	"golang.org/x/net/context"
)

var id idGenerator

type idGenerator struct {
	mu      sync.Mutex
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

	switch reflect.ValueOf(src).Kind() {
	case reflect.Slice:
		v := reflect.ValueOf(src)
		for i := 0; i < v.Len(); i++ {
			srcs = append(srcs, v.Index(i).Interface())
		}
	case reflect.Struct:
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

// BatchUploader contains the necessary data for asynchronously sending batches
// of event row data to BigQuery.
type BatchUploader struct {
	// TickC is a channel used by BatchUploader to prompt upload(). Set
	// TickC before the first call to Stage. A <-chan time.Time with a
	// ticker can be constructed with time.NewTicker(time.Duration).C. If
	// left unset, the default upload interval is one minute.
	TickC <-chan time.Time
	// tick holds the default ticker
	tick *time.Ticker
	// UploadsMetricName is a string used to create a tsmon Counter metric
	// for event upload attempts via Put, e.g.
	// "/chrome/infra/commit_queue/events/count". Set UploadMetricName
	// before the first call to Stage. If left unset, no metric will be
	// created.
	UploadMetricName string
	// uploads is the Counter metric described by UploadMetricName. It
	// contains a field "status" set to either "success" or "failure."
	uploads metric.Counter

	u     eventUploader
	ctx   context.Context
	stopc chan struct{}
	wg    sync.WaitGroup

	mu      sync.Mutex
	pending []interface{}
	started bool
}

func (bu *BatchUploader) start() {
	if bu.UploadMetricName != "" {
		name := bu.UploadMetricName
		desc := "Upload attempts; status is 'success' or 'failure'"
		field := field.String("status")
		bu.uploads = metric.NewCounterIn(bu.ctx, name, desc, nil, field)
	}

	if bu.TickC == nil {
		bu.tick = time.NewTicker(time.Minute)
		bu.TickC = bu.tick.C
	}

	bu.wg.Add(1)
	go func() {
		defer bu.wg.Done()
		for {
			select {
			case <-bu.TickC:
				bu.upload()
			case <-bu.stopc:
				return
			}
		}
	}()
}

// NewBatchUploader constructs a new BatchUploader, which may optionally be
// further configured by setting its exported fields before the first call to
// Stage. Its Close method should be called when it is no longer needed.
func NewBatchUploader(ctx context.Context, u eventUploader) (*BatchUploader, error) {
	bu := &BatchUploader{
		u:     u,
		ctx:   ctx,
		stopc: make(chan struct{}),
	}
	return bu, nil
}

// Stage stages one or more rows for sending to BigQuery. src is expected to
// be a struct matching the schema in Uploader, or a slice containing
// such structs. Stage returns immediately and batches of rows will be sent to
// BigQuery at regular intervals according to the configuration of TickC.
func (bu *BatchUploader) Stage(src interface{}) {
	bu.mu.Lock()
	defer bu.mu.Unlock()

	if !bu.started {
		bu.start()
		bu.started = true
	}

	switch reflect.ValueOf(src).Kind() {
	case reflect.Slice:
		v := reflect.ValueOf(src)
		for i := 0; i < v.Len(); i++ {
			bu.pending = append(bu.pending, v.Index(i).Interface())
		}
	case reflect.Struct:
		bu.pending = append(bu.pending, src)
	}
}

// upload streams a batch of event rows to BigQuery. Put takes care of retrying,
// so if it returns an error there is either an issue with the data it is trying
// to upload, or BigQuery itself is experiencing a failure. So, we don't retry.
func (bu *BatchUploader) upload() {
	bu.mu.Lock()
	pending := bu.pending
	bu.pending = nil
	bu.mu.Unlock()

	if len(pending) == 0 {
		return
	}

	var succeeded, failed int64

	if err := bu.u.Put(bu.ctx, pending); err != nil {
		log.Printf("eventupload: Uploader.Put: %v", err)
		if merr, ok := err.(bigquery.PutMultiError); ok {
			failed = int64(len(merr))
		} else {
			failed = int64(len(pending))
		}
		bu.updateUploads(failed, "failure")
	}

	succeeded = int64(len(pending)) - failed
	bu.updateUploads(succeeded, "success")
}

func (bu *BatchUploader) updateUploads(count int64, status string) {
	if bu.uploads == nil || count == 0 {
		return
	}
	err := bu.uploads.Add(bu.ctx, count, status)
	if err != nil {
		log.Printf("eventupload: metric.Counter.Add: %v", err)
	}
}

// Close flushes any pending event rows and releases any resources held by the
// uploader. Close should be called when the logger is no longer needed.
func (bu *BatchUploader) Close() {
	close(bu.stopc)
	bu.wg.Wait()

	// Final upload.
	bu.upload()

	if bu.tick != nil {
		bu.tick.Stop()
	}
}
