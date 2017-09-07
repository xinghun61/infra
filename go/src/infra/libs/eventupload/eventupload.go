// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package eventupload is a library for streaming events to BigQuery.
package eventupload

import (
	"reflect"
	"sync"
	"time"

	"infra/libs/bqschema/tabledef"

	"cloud.google.com/go/bigquery"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/tsmon/field"
	"go.chromium.org/luci/common/tsmon/metric"
	"golang.org/x/net/context"
)

var id InsertIDGenerator

// eventUploader is an interface for types which implement a Put method. It
// exists for the purpose of mocking Uploader in tests.
type eventUploader interface {
	Put(ctx context.Context, src interface{}) error
}

// Uploader contains the necessary data for streaming data to BigQuery.
type Uploader struct {
	*bigquery.Uploader
	// Uploader is bound to a specific table. DatasetID and Table ID are
	// provided for reference.
	DatasetID string
	TableID   string
	s         bigquery.Schema
	// UploadsMetricName is a string used to create a tsmon Counter metric
	// for event upload attempts via Put, e.g.
	// "/chrome/infra/commit_queue/events/count". If unset, no metric will
	// be created.
	UploadsMetricName string
	// uploads is the Counter metric described by UploadsMetricName. It
	// contains a field "status" set to either "success" or "failure."
	uploads        metric.Counter
	initMetricOnce *sync.Once
}

// NewUploader constructs a new Uploader struct.
//
// DatasetID and TableID are provided to the BigQuery client (via TableDef) to
// gain access to a particular table.
//
// You may want to change the default configuration of the bigquery.Uploader.
// Check the documentation for more details.
//
// Set UploadsMetricName on the resulting Uploader to use the default counter
// metric.
func NewUploader(ctx context.Context, c *bigquery.Client, td *tabledef.TableDef) *Uploader {
	return &Uploader{
		DatasetID: td.GetDataset().ID(),
		TableID:   td.TableId,
		Uploader:  c.Dataset(td.GetDataset().ID()).Table(td.TableId).Uploader(),
		s:         tabledef.BQSchema(td.Fields),
	}
}

func (u *Uploader) getCounter(ctx context.Context) metric.Counter {
	u.initMetricOnce.Do(func() {
		if u.UploadsMetricName != "" {
			desc := "Upload attempts; status is 'success' or 'failure'"
			field := field.String("status")
			u.uploads = metric.NewCounterIn(ctx, u.UploadsMetricName, desc, nil, field)
		}
	})
	return u.uploads
}

func (u *Uploader) updateUploads(ctx context.Context, count int64, status string) {
	uploads := u.getCounter(ctx)
	if uploads == nil || count == 0 {
		return
	}
	err := uploads.Add(ctx, count, status)
	if err != nil {
		logging.WithError(err).Errorf(ctx, "eventupload: metric.Counter.Add failed")
	}
}

// Put uploads one or more rows to the BigQuery service. src is expected to
// be a struct (or a pointer to a struct) matching the schema in Uploader, or a
// slice containing such values. Put takes care of adding InsertIDs, used by
// BigQuery to deduplicate rows.
//
// If any rows do now match one of the expected types, Put will not attempt to
// upload any rows and returns an InvalidTypeError.
//
// Put returns a PutMultiError if one or more rows failed to be uploaded.
// The PutMultiError contains a RowInsertionError for each failed row.
//
// Put will retry on temporary errors. If the error persists, the call will
// run indefinitely. Because of this, if ctx does not have a timeout, Put will
// add one.
//
// See bigquery documentation and source code for detailed information on how
// struct values are mapped to rows.
func (u Uploader) Put(ctx context.Context, src interface{}) error {
	if _, ok := ctx.Deadline(); !ok {
		var c context.CancelFunc
		ctx, c = context.WithTimeout(ctx, time.Minute)
		defer c()
	}
	var failed int64
	sss, err := prepareSrc(u.s, src)
	if err != nil {
		return err
	}
	err = u.Uploader.Put(ctx, sss)
	if err != nil {
		logging.WithError(err).Errorf(ctx, "eventupload: Uploader.Put failed")
		if merr, ok := err.(bigquery.PutMultiError); ok {
			failed = int64(len(merr))
		} else {
			failed = int64(len(sss))
		}
		u.updateUploads(ctx, failed, "failure")
	}
	succeeded := int64(len(sss)) - failed
	if succeeded < 0 {
		logging.Errorf(ctx, "eventupload: Uploader.Put succeeded < 0: %v", succeeded)
	} else {
		u.updateUploads(ctx, succeeded, "success")
	}
	return err
}

func prepareSrc(s bigquery.Schema, src interface{}) ([]*bigquery.StructSaver, error) {

	validateSingleValue := func(v reflect.Value) error {
		switch v.Kind() {
		case reflect.Struct:
			return nil
		case reflect.Ptr:
			ptrK := v.Elem().Kind()
			if ptrK == reflect.Struct {
				return nil
			}
			return errors.Reason("pointer types must point to structs, not %s", ptrK).Err()
		default:
			return errors.Reason("struct or pointer-to-struct expected, got %v", v.Kind()).Err()
		}
	}

	var srcs []interface{}

	srcV := reflect.ValueOf(src)
	if srcV.Kind() == reflect.Slice {
		srcs = make([]interface{}, srcV.Len())
		for i := 0; i < srcV.Len(); i++ {
			itemV := srcV.Index(i)
			if err := validateSingleValue(itemV); err != nil {
				return nil, err
			}
			srcs[i] = itemV.Interface()
		}
	} else {
		if err := validateSingleValue(srcV); err != nil {
			return nil, err
		}
		srcs = []interface{}{src}
	}

	var prepared []*bigquery.StructSaver
	for i, src := range srcs {
		// If no schema is supplied explicitly via TableDef, infer it from each
		// individual element. This inference is cached based on the type.
		schema := s
		if len(schema) == 0 {
			var err error
			if schema, err = bigquery.InferSchema(src); err != nil {
				return nil, errors.Annotate(err, "could not infer schema for element #%d (%T)", i, src).Err()
			}
		}

		insertID, err := id.Generate()
		if err != nil {
			return nil, err
		}
		ss := &bigquery.StructSaver{
			Schema:   schema,
			InsertID: insertID,
			Struct:   src,
		}

		prepared = append(prepared, ss)
	}
	return prepared, nil
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

	u     eventUploader
	stopc chan struct{}
	wg    sync.WaitGroup

	mu      sync.Mutex
	pending []interface{}
	started bool
	closed  bool
}

func (bu *BatchUploader) start(ctx context.Context) {
	if bu.TickC == nil {
		bu.tick = time.NewTicker(time.Minute)
		bu.TickC = bu.tick.C
	}

	bu.wg.Add(1)
	go func() {
		defer bu.wg.Done()
		for {
			select {
			case <-ctx.Done():
				return
			case <-bu.TickC:
				bu.upload(ctx)
			case <-bu.stopc:
				return
			}
		}
	}()
}

// NewBatchUploader constructs a new BatchUploader, which may optionally be
// further configured by setting its exported fields before the first call to
// Stage. Its Close method should be called when it is no longer needed.
//
// Uploader implements eventUploader.
func NewBatchUploader(u eventUploader) (*BatchUploader, error) {
	bu := &BatchUploader{
		u:     u,
		stopc: make(chan struct{}),
	}
	return bu, nil
}

// Stage stages one or more rows for sending to BigQuery. src is expected to
// be a struct matching the schema in Uploader, or a slice containing
// such structs. Stage returns immediately and batches of rows will be sent to
// BigQuery at regular intervals according to the configuration of TickC.
//
// Stage will spawn another goroutine that manages uploads, if it hasn't been
// started already. That routine depends on ctx, so be aware that if ctx is
// cancelled immediately after calling Stage, those events will not be uploaded.
func (bu *BatchUploader) Stage(ctx context.Context, src interface{}) {
	if bu.closed {
		panic("Stage called on closed BatchUploader")
	}
	bu.mu.Lock()
	defer bu.mu.Unlock()

	if !bu.started {
		bu.start(ctx)
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
func (bu *BatchUploader) upload(ctx context.Context) {
	bu.mu.Lock()
	pending := bu.pending
	bu.pending = nil
	bu.mu.Unlock()

	if len(pending) == 0 {
		return
	}

	_ = bu.u.Put(ctx, pending)
}

// Close flushes any pending event rows and releases any resources held by the
// uploader. Close should be called when the BatchUploader is no longer needed.
func (bu *BatchUploader) Close(ctx context.Context) {
	if bu.closed {
		return
	}

	close(bu.stopc)
	bu.wg.Wait()

	// Final upload.
	bu.upload(ctx)

	if bu.tick != nil {
		bu.tick.Stop()
	}
	bu.closed = true
}
