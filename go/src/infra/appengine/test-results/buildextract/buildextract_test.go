// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package buildextract

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"testing"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"

	"github.com/golang/protobuf/proto"
	milo "github.com/luci/luci-go/milo/api/proto"
	. "github.com/smartystreets/goconvey/convey"
	"golang.org/x/net/context"
)

type fakeClient struct {
	MasterData map[string][]byte
	BuildsData map[string]map[string][]byte
}

func (c *fakeClient) Call(ctx context.Context, serviceName, methodName string, in, out proto.Message, opts ...grpc.CallOption) error {
	if serviceName != "milo.Buildbot" {
		panic(fmt.Errorf("unkonwn serivce name %s", serviceName))
	}
	switch methodName {
	case "GetCompressedMasterJSON":
		iin := in.(*milo.MasterRequest)
		iout := out.(*milo.CompressedMasterJSON)
		gsbz := bytes.Buffer{}
		gsw := gzip.NewWriter(&gsbz)
		data, ok := c.MasterData[iin.Name]
		if !ok {
			return grpc.Errorf(codes.NotFound, "not found")
		}
		gsw.Write(data)
		gsw.Close()
		iout.Data = gsbz.Bytes()
	case "GetBuildbotBuildsJSON":
		iin := in.(*milo.BuildbotBuildsRequest)
		iout := out.(*milo.BuildbotBuildsJSON)
		d, ok := c.BuildsData[iin.Master][iin.Builder]
		if !ok {
			return grpc.Errorf(codes.NotFound, "not found")
		}
		result := &BuildsData{}
		err := json.Unmarshal(d, result)
		if err != nil {
			return err
		}
		for _, b := range result.Builds {
			bs, err := json.Marshal(b)
			if err != nil {
				return err
			}
			iout.Builds = append(iout.Builds, &milo.BuildbotBuildJSON{Data: bs})
		}
	default:
		panic(fmt.Errorf("unknown method name %s", methodName))
	}
	return nil
}

func TestClient(t *testing.T) {
	t.Parallel()

	// Data is not representative of actual data from live API.
	masterData := map[string][]byte{
		"chromium.mac": []byte(`{ "life": 42 }`),
	}
	buildsData := map[string]map[string][]byte{
		"chromium.mac": {
			"ios.simulator": []byte(`{"builds":[{"steps":[{"name":"baz"}]}]}`),
		},
	}

	fakepc := fakeClient{
		MasterData: masterData,
		BuildsData: buildsData,
	}

	Convey("Client", t, func() {
		c := Client{&fakepc}
		ctx := context.Background()

		Convey("exists", func() {
			Convey("GetMasterJSON", func() {
				data, err := c.GetMasterJSON(ctx, "chromium.mac")
				So(err, ShouldBeNil)
				defer data.Close()
				b, err := ioutil.ReadAll(data)
				So(err, ShouldBeNil)
				So(b, ShouldResemble, []byte(`{ "life": 42 }`))
			})
			Convey("GetBuildsJSON", func() {
				data, err := c.GetBuildsJSON(ctx, "ios.simulator", "chromium.mac", 1)
				So(err, ShouldBeNil)
				So(data.Builds[0].Steps[0].Name, ShouldEqual, "baz")
			})

		})
		Convey("does not exist", func() {
			Convey("GetMasterJSON", func() {
				_, err := c.GetMasterJSON(ctx, "non-existent")
				So(err, ShouldHaveSameTypeAs, &StatusError{})
				So(err.(*StatusError).StatusCode, ShouldEqual, http.StatusNotFound)

			})
			Convey("GetBuildsJSON", func() {
				_, err := c.GetBuildsJSON(ctx, "non-existent", "chromium.mac", 1)
				So(err, ShouldHaveSameTypeAs, &StatusError{})
				So(err.(*StatusError).StatusCode, ShouldEqual, http.StatusNotFound)
			})
		})

	})
}
