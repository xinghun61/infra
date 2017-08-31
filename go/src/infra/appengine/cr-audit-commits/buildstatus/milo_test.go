// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package buildstatus

import (
	"testing"

	"golang.org/x/net/context"
	"google.golang.org/grpc"

	milo "go.chromium.org/luci/milo/api/proto"

	. "github.com/smartystreets/goconvey/convey"
)

type MockBuildbotClient struct {
	milo.BuildbotClient
	FakeData []byte
}

func (mbc *MockBuildbotClient) GetBuildbotBuildJSON(ctx context.Context, req *milo.BuildbotBuildRequest, opts ...grpc.CallOption) (*milo.BuildbotBuildJSON, error) {
	return &milo.BuildbotBuildJSON{
		Data: mbc.FakeData,
	}, nil

}

func TestGetBuildInfo(t *testing.T) {
	Convey("Basic", t, func() {
		// TODO(robertocn): Move mock generation to milo.
		mbc := &MockBuildbotClient{
			FakeData: []byte(`{
			    "slave": "buildSlave42", 
			    "logs": [
				[
				    "preamble", 
				    "https://build.chromium.org/p/m/builders/b/builds/1/steps/steps/logs/preamble"
				], 
				[
				    "stdio", 
				    "https://build.chromium.org/p/m/builders/b/builds/1/steps/steps/logs/stdio"
				]
			    ], 
			    "builderName": "b", 
			    "text": [
				"failed", 
				"steps", 
				"failed", 
				"compile", 
				"failed", 
				"Failure reason"
			    ], 
			    "timeStamp": 1500913632, 
			    "finished": true, 
			    "number": 1, 
			    "currentStep": null, 
			    "results": 2, 
			    "blame": [
				"contributor@chromium.org", 
				"somedev@chromium.org"
			    ], 
			    "reason": "scheduler", 
			    "eta": null, 
			    "Master": "m", 
			    "internal": false, 
			    "sourceStamp": {
				"repository": "https://chromium.googlesource.com/chromium/src", 
				"hasPatch": false, 
				"project": "src", 
				"branch": "master", 
				"changes": [
				    {
					"category": "", 
					"repository": "https://chromium.googlesource.com/chromium/src", 
					"when": 1500912041, 
					"who": "somedev@chromium.org", 
					"rev": "c001c0de", 
					"number": 89292, 
					"comments": "Remove someone@ from WATCHLISTS as they haven't worked on Chrome in many\nmoons.\n\nBug: None\nChange-Id: IFakeChangeId\nReviewed-on: https://chromium-review.googlesource.com/5000\nCommit-Queue: Reviewer <reviewer@chromium.org>\nReviewed-by: Reviewer <reviewer@chromium.org>\nCr-Commit-Position: refs/heads/master@{#1}", 
					"project": "src", 
					"at": "Mon 10 Jul 2017 09:00:41", 
					"branch": "master", 
					"revlink": "https://chromium.googlesource.com/chromium/src/+/c001c0de", 
					"properties": [
					    [
						"git_revision", 
						"c001c0de", 
						"Change"
					    ]
					], 
					"revision": "c001c0de"
				    }
				], 
				"revision": "c001c0de2"
			    }, 
			    "steps": [
				{
				    "isFinished": true, 
				    "step_number": 0, 
				    "isStarted": true, 
				    "results": [
					2, 
					[
					    "steps"
					]
				    ], 
				    "urls": {}, 
				    "text": [
					"running steps via annotated script"
				    ], 
				    "hidden": false, 
				    "times": [
					1500913401.997552, 
					1500913617.177543
				    ], 
				    "name": "steps"
				}, 
				{
				    "statistics": {}, 
				    "logs": [
					[
					    "stdio", 
					    "https://build.chromium.org/p/m/builders/b/builds/1/steps/update_scripts/logs/stdio"
					]
				    ], 
				    "isFinished": true, 
				    "step_number": 1, 
				    "expectations": [], 
				    "isStarted": true, 
				    "results": [
					0, 
					[]
				    ], 
				    "text": [
					"update_scripts"
				    ], 
				    "hidden": false, 
				    "times": [
					1500913407.019757, 
					1500913412.043572
				    ], 
				    "name": "update_scripts"
				}
			    ], 
			    "times": [
				1500913401.995199, 
				1500913617.179009
			    ], 
			    "properties": [
				[
				    "blamelist", 
				    [
					"contributor@chromium.org", 
					"somedev@chromium.org"
				    ], 
				    "Build"
				], 
				[
				    "branch", 
				    "master", 
				    "Build"
				]
			    ]
			}`)}
		amc := &AuditMiloClient{
			BuildbotClient: mbc,
		}
		ctx := context.Background()
		Convey("Bad build url", func() {
			b, err := amc.GetBuildInfo(ctx, "https://tempuri.com")
			So(err, ShouldNotBeNil)
			So(b, ShouldBeNil)
		})
		Convey("Good build url", func() {
			b, err := amc.GetBuildInfo(ctx, "https://tempuri.com/buildbot/m/b/1")
			So(err, ShouldBeNil)
			So(b, ShouldNotBeNil)
			So(len(b.SourceStamp.Changes), ShouldEqual, 1)
			So(b.SourceStamp.Changes[0].Who, ShouldEqual, "somedev@chromium.org")
		})
	})
}
