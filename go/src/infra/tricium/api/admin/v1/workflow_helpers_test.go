// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package admin

import (
	"testing"

	. "github.com/smartystreets/goconvey/convey"

	"infra/tricium/api/v1"
)

func TestGetNext(t *testing.T) {
	Convey("Workflow with single worker, returns no successors", t, func() {
		cw := "Single"
		wf := &Workflow{
			Workers: []*Worker{
				{
					Name: cw,
				},
			},
		}
		sw := wf.GetNext(cw)
		So(sw, ShouldBeNil)
	})

	Convey("Workflow with succeeding workers, returns successors", t, func() {
		cw := "First"
		s := "Next1"
		s2 := "Next2"
		wf := &Workflow{
			Workers: []*Worker{
				{
					Name: cw,
					Next: []string{
						s,
						s2,
					},
				},
				{
					Name: s,
				},
				{
					Name: s2,
				},
			},
		}
		sw := wf.GetNext(cw)
		So(sw, ShouldNotBeNil)
		So(len(sw), ShouldEqual, 2)
		So(sw[0], ShouldEqual, s)
		So(sw[1], ShouldEqual, s2)
	})
}

func TestGetWithDescendants(t *testing.T) {
	Convey("Workflow with single worker, returns worker", t, func() {
		cw := "Single"
		wf := &Workflow{
			Workers: []*Worker{
				{
					Name: cw,
				},
			},
		}
		sw := wf.GetWithDescendants(cw)
		So(len(sw), ShouldEqual, 1)
		So(sw[0], ShouldEqual, cw)
	})

	Convey("Workflow with descending workers, returns worker with descendants", t, func() {
		cw := "First"
		s := "Next1"
		s2 := "Next2"
		t := "Next1Next1"
		t2 := "Next1Next2"
		wf := &Workflow{
			Workers: []*Worker{
				{
					Name: cw,
					Next: []string{
						s,
						s2,
					},
				},
				{
					Name: s,
					Next: []string{
						t,
						t2,
					},
				},
				{Name: s2},
				{Name: t},
				{Name: t2},
			},
		}
		sw := wf.GetWithDescendants(cw)
		So(sw, ShouldResemble, []string{cw, s, t, t2, s2})
	})
}

func TestRootWorkers(t *testing.T) {
	Convey("Workflow with no root workers, returns no root workers", t, func() {
		cw := "First"
		wf := &Workflow{
			Workers: []*Worker{
				{
					Name: cw,
				},
			},
		}
		rw := wf.RootWorkers()
		So(rw, ShouldBeNil)
	})
	Convey("Workflow with root workers, returns root workers", t, func() {
		w := "First"
		w2 := "Second"
		w3 := "Third"
		wf := &Workflow{
			Workers: []*Worker{
				{
					Name:  w,
					Needs: tricium.Data_GIT_FILE_DETAILS,
				},
				{
					Name:  w2,
					Needs: tricium.Data_FILES,
				},
				{
					Name:  w3,
					Needs: tricium.Data_GIT_FILE_DETAILS,
				},
			},
		}
		rw := wf.RootWorkers()
		So(rw, ShouldNotBeNil)
		So(len(rw), ShouldEqual, 2)
		So(rw[0], ShouldEqual, w)
		So(rw[1], ShouldEqual, w3)
	})

}
