// Copyright 2015 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ephelper

import (
	"net/http"
	"testing"

	"github.com/GoogleCloudPlatform/go-endpoints/endpoints"
	. "github.com/smartystreets/goconvey/convey"
)

type FakeExportedServerBadMethods struct{}

func (FakeExportedServerBadMethods) fooMethod() {}

type FakeExportedServer struct{}

func (FakeExportedServer) FooMethod(*http.Request) error {
	return nil
}

func TestRegister(t *testing.T) {
	t.Parallel()

	Convey("Testing Register(...)", t, func() {

		Convey("errors", func() {
			Convey("nil server", func() {
				err := Register(nil, nil, nil, nil)
				So(err, ShouldEqual, ErrServerNil)
			})
			Convey("nil service", func() {
				serv := endpoints.NewServer("")
				err := Register(serv, nil, nil, nil)
				So(err, ShouldEqual, ErrServiceNil)
			})
			Convey("registration error", func() {
				s := FakeExportedServerBadMethods{}
				si := &endpoints.ServiceInfo{}
				mi := map[string]*endpoints.MethodInfo{
					"fooMethod": {},
				}
				serv := endpoints.NewServer("")
				err := Register(serv, s, si, mi)
				So(err.Error(), ShouldContainSubstring,
					"no exported methods")
			})
			Convey("method mismatch", func() {
				s := FakeExportedServer{}
				si := &endpoints.ServiceInfo{}
				mi := map[string]*endpoints.MethodInfo{
					"fooMethod": {},
				}
				serv := endpoints.NewServer("")
				err := Register(serv, s, si, mi)
				So(err.Error(), ShouldContainSubstring,
					"no method \"fooMethod\"")
			})
		})

		Convey("Success", func() {
			Convey("defaults", func() {
				s := FakeExportedServer{}
				srv := endpoints.NewServer("")
				err := Register(srv, s, nil, nil)
				So(err, ShouldBeNil)
				fakeServer := srv.ServiceByName("FakeExportedServer")
				So(fakeServer, ShouldNotBeNil)
				So(fakeServer.Info().Name, ShouldEqual, "fakeexportedserver")
				So(fakeServer.Info().Version, ShouldEqual, "v1")
				So(fakeServer.Info().Default, ShouldBeTrue)
				So(fakeServer.Info().Description, ShouldEqual, "")

				m := fakeServer.MethodByName("FooMethod")
				So(m, ShouldNotBeNil)
				So(m.Info().Name, ShouldEqual, "foomethod")
				So(m.Info().Path, ShouldEqual, "foomethod")
				So(m.Info().HTTPMethod, ShouldEqual, "GET")
				So(m.Info().Desc, ShouldEqual, "")
			})

			Convey("overrides", func() {
				s := FakeExportedServer{}
				si := &endpoints.ServiceInfo{
					Name:        "fakeThing",
					Version:     "9001",
					Description: "A space oddysey.",
				}
				mi := MethodInfoMap{
					"FooMethod": {
						Name:       "foo_method",
						Path:       "foo",
						HTTPMethod: "POST",
						Desc:       "does useful stuff",
					},
				}
				srv := endpoints.NewServer("")
				err := Register(srv, s, si, mi)
				So(err, ShouldBeNil)
				fakeServer := srv.ServiceByName("FakeExportedServer")
				So(fakeServer, ShouldNotBeNil)
				So(fakeServer.Info().Name, ShouldEqual, "fakething")
				So(fakeServer.Info().Version, ShouldEqual, "9001")
				So(fakeServer.Info().Default, ShouldBeFalse)
				So(fakeServer.Info().Description, ShouldEqual, "A space oddysey.")

				m := fakeServer.MethodByName("FooMethod")
				So(m, ShouldNotBeNil)
				So(m.Info().Name, ShouldEqual, "foo_method")
				So(m.Info().Path, ShouldEqual, "foo")
				So(m.Info().HTTPMethod, ShouldEqual, "POST")
				So(m.Info().Desc, ShouldEqual, "does useful stuff")
			})

			Convey("merge", func() {
				s := FakeExportedServer{}
				mi := MethodInfoMap{
					"FooMethod": {
						Desc: "does useful stuff",
					},
				}
				srv := endpoints.NewServer("")
				err := Register(srv, s, nil, mi)
				So(err, ShouldBeNil)
				fakeServer := srv.ServiceByName("FakeExportedServer")
				m := fakeServer.MethodByName("FooMethod")
				So(m, ShouldNotBeNil)
				So(m.Info().Name, ShouldEqual, "foomethod")
				So(m.Info().Path, ShouldEqual, "foomethod")
				So(m.Info().HTTPMethod, ShouldEqual, "GET")
				So(m.Info().Desc, ShouldEqual, "does useful stuff")
			})
		})
	})
}
