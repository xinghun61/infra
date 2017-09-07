// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package eventupload

import (
	"fmt"
	"testing"
	"time"

	"cloud.google.com/go/bigquery"
	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

type mockUploader chan []fakeEvent

func (u mockUploader) Put(ctx context.Context, src interface{}) error {
	srcs := src.([]interface{})
	var fes []fakeEvent
	for _, fe := range srcs {
		fes = append(fes, fe.(fakeEvent))
	}
	u <- fes
	return nil
}

type fakeEvent struct{}

func shouldHavePut(actual interface{}, expected ...interface{}) string {
	u := actual.(mockUploader)

	select {
	case got := <-u:
		return ShouldResemble([]interface{}{got}, expected)
	case <-time.After(50 * time.Millisecond):
		return "timed out waiting for upload"
	}
}

func TestClose(t *testing.T) {
	t.Parallel()

	Convey("Test Close", t, func() {
		u := make(mockUploader, 1)
		bu, err := NewBatchUploader(u)
		if err != nil {
			t.Fatal(err)
		}

		closed := false
		defer func() {
			if !closed {
				bu.Close(context.Background())
			}
		}()

		bu.TickC = make(chan time.Time)

		Convey("Expect Stage to add event to pending queue", func() {
			bu.Stage(context.Background(), fakeEvent{})
			So(bu.pending, ShouldHaveLength, 1)
		})

		Convey("Expect Close to flush pending queue", func() {
			bu.Stage(context.Background(), fakeEvent{})
			bu.Close(context.Background())
			closed = true
			So(bu.pending, ShouldHaveLength, 0)
			So(u, shouldHavePut, []fakeEvent{{}})
			So(bu.closed, ShouldBeTrue)
			So(func() { bu.Stage(context.Background(), fakeEvent{}) }, ShouldPanic)
		})
	})
}

func TestUpload(t *testing.T) {
	t.Parallel()

	Convey("Test Upload", t, func() {
		u := make(mockUploader, 1)
		bu, err := NewBatchUploader(&u)
		if err != nil {
			t.Fatal(err)
		}
		defer bu.Close(context.Background())

		tickc := make(chan time.Time)
		bu.TickC = tickc

		bu.Stage(context.Background(), fakeEvent{})
		Convey("Expect Put to wait for tick to call upload", func() {
			So(u, ShouldHaveLength, 0)
			tickc <- time.Time{}
			So(u, shouldHavePut, []fakeEvent{{}})
		})
	})
}

func TestPrepareSrc(t *testing.T) {
	t.Parallel()

	notStruct := 0
	tcs := []struct {
		desc    string
		src     interface{}
		wantLen int
	}{
		{
			desc:    "prepareSrc accepts structs",
			src:     fakeEvent{},
			wantLen: 1,
		},
		{
			desc:    "prepareSrc accepts pointers to structs",
			src:     &fakeEvent{},
			wantLen: 1,
		},
		{
			desc:    "prepareSrc accepts slices of structs",
			src:     []fakeEvent{{}, {}},
			wantLen: 2,
		},
		{
			desc: "prepareSrc accepts slices of pointers to structs",
			src: []*fakeEvent{
				{},
				{},
			},
			wantLen: 2,
		},
		{
			desc:    "prepareSrc does not accept pointers to non-struct types",
			src:     &notStruct,
			wantLen: 0,
		},
		{
			desc:    "prepareSrc does not accept slices of non-struct or non-pointer types",
			src:     []string{"not a struct or pointer"},
			wantLen: 0,
		},
		{
			desc:    "prepareSrc does not accept slices of non-struct or non-pointer types (2)",
			src:     []*int{&notStruct},
			wantLen: 0,
		},
	}

	Convey("Test PrepareSrc", t, func() {
		s, err := bigquery.InferSchema(fakeEvent{})
		if err != nil {
			t.Fatal(err)
		}
		for _, tc := range tcs {
			Convey(tc.desc, func() {
				sss, _ := prepareSrc(s, tc.src)
				So(sss, ShouldHaveLength, tc.wantLen)
			})
		}
	})
}

func TestStage(t *testing.T) {
	t.Parallel()

	tcs := []struct {
		desc    string
		src     interface{}
		wantLen int
	}{
		{
			desc:    "single event",
			src:     fakeEvent{},
			wantLen: 1,
		},
		{
			desc:    "slice of events",
			src:     []fakeEvent{{}, {}},
			wantLen: 2,
		},
	}

	Convey("Stage can accept single events and slices of events", t, func() {
		u := make(mockUploader, 1)
		bu, err := NewBatchUploader(&u)
		if err != nil {
			t.Fatal(err)
		}
		defer bu.Close(context.Background())

		for _, tc := range tcs {
			Convey(fmt.Sprintf("Test %s", tc.desc), func() {
				bu.Stage(context.Background(), tc.src)
				So(bu.pending, ShouldHaveLength, tc.wantLen)
				So(bu.pending[len(bu.pending)-1], ShouldHaveSameTypeAs, fakeEvent{})
			})
		}
	})
}
