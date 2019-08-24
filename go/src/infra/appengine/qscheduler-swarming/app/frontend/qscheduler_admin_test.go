// Copyright 2018 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package frontend_test

import (
	"testing"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	. "github.com/smartystreets/goconvey/convey"
	"go.chromium.org/luci/appengine/gaetesting"

	qscheduler "infra/appengine/qscheduler-swarming/api/qscheduler/v1"
	"infra/appengine/qscheduler-swarming/app/frontend"
	"infra/qscheduler/qslib/protos"
)

func TestCreateDeleteScheduler(t *testing.T) {
	Convey("Given an admin server running in a test context", t, func() {
		ctx := gaetesting.TestingContext()
		admin := &frontend.QSchedulerAdminServerImpl{}
		view := &frontend.QSchedulerViewServerImpl{}
		poolID := "Pool 1"
		req := qscheduler.CreateSchedulerPoolRequest{
			PoolId: poolID,
		}

		Convey("when CreateSchedulerPool is called with a config", func() {
			config := &protos.SchedulerConfig{}
			req.Config = config
			resp, err := admin.CreateSchedulerPool(ctx, &req)
			Convey("then an error is returned.", func() {
				So(resp, ShouldBeNil)
				So(err, ShouldNotBeNil)
			})
		})

		Convey("when CreateSchedulerPool is called", func() {
			resp, err := admin.CreateSchedulerPool(ctx, &req)
			Convey("then it returns without errors.", func() {
				So(resp, ShouldNotBeNil)
				So(err, ShouldBeNil)
			})

			Convey("when InspectPool is called, it succeeds.", func() {
				req := &qscheduler.InspectPoolRequest{PoolId: poolID}
				resp, err := view.InspectPool(ctx, req)
				So(err, ShouldBeNil)
				So(resp, ShouldNotBeNil)
			})

			Convey("when DeleteSchedulerPool is called to delete the scheduler", func() {
				req := &qscheduler.DeleteSchedulerPoolRequest{
					PoolId: poolID,
				}
				resp, err := admin.DeleteSchedulerPool(ctx, req)
				So(err, ShouldBeNil)
				So(resp, ShouldNotBeNil)
				Convey("when inspect is called, it fails to find scheduler.", func() {
					req := &qscheduler.InspectPoolRequest{PoolId: poolID}
					resp, err := view.InspectPool(ctx, req)
					So(resp, ShouldBeNil)
					So(err, ShouldNotBeNil)
				})
			})
		})
	})
}

func TestCreateListDeleteAccount(t *testing.T) {
	poolID := "Pool1"
	Convey("Given an admin server running in a test context", t, func() {
		ctx := gaetesting.TestingContext()
		admin := &frontend.QSchedulerAdminServerImpl{}
		view := &frontend.QSchedulerViewServerImpl{}
		Convey("when CreateAccount is called with a nonexistent pool", func() {
			req := qscheduler.CreateAccountRequest{
				PoolId: poolID,
			}
			resp, err := admin.CreateAccount(ctx, &req)
			// TODO(akeshet): this should return NotFound instead of Unknown.
			Convey("then an error with code Unknown is returned.", func() {
				So(resp, ShouldBeNil)
				So(err, ShouldNotBeNil)
				s, ok := status.FromError(err)
				So(ok, ShouldBeTrue)
				So(s.Code(), ShouldEqual, codes.Unknown)
			})
		})

		Convey("when ListAccounts is called for nonexistent pool", func() {
			req := qscheduler.ListAccountsRequest{
				PoolId: poolID,
			}
			resp, err := view.ListAccounts(ctx, &req)
			// TODO(akeshet): this should return NotFound instead of Unknown.
			Convey("then an error with code Unknown is returned.", func() {
				So(resp, ShouldBeNil)
				So(err, ShouldNotBeNil)
				s, ok := status.FromError(err)
				So(ok, ShouldBeTrue)
				So(s.Code(), ShouldEqual, codes.Unknown)
			})
		})

		Convey("with a scheduler pool", func() {
			req := qscheduler.CreateSchedulerPoolRequest{
				PoolId: poolID,
			}
			_, err := admin.CreateSchedulerPool(ctx, &req)
			So(err, ShouldBeNil)

			Convey("when ListAccounts is called for that pool", func() {
				req := qscheduler.ListAccountsRequest{
					PoolId: poolID,
				}
				resp, err := view.ListAccounts(ctx, &req)
				Convey("then it returns no results.", func() {
					So(resp.Accounts, ShouldBeEmpty)
					So(err, ShouldBeNil)
				})
			})

			Convey("when CreateAccount is called for that pool", func() {
				accountID := "Account1"
				req := qscheduler.CreateAccountRequest{
					AccountId: accountID,
					PoolId:    poolID,
				}
				resp, err := admin.CreateAccount(ctx, &req)
				Convey("then it succeeds.", func() {
					So(resp, ShouldResemble, &qscheduler.CreateAccountResponse{})
					So(err, ShouldBeNil)
				})
				Convey("when ListAccounts is called for that pool", func() {
					req := qscheduler.ListAccountsRequest{
						PoolId: poolID,
					}
					resp, err := view.ListAccounts(ctx, &req)
					Convey("then it returns a list with that account.", func() {
						So(err, ShouldBeNil)
						So(resp.Accounts, ShouldContainKey, accountID)
						So(resp.Accounts, ShouldHaveLength, 1)
					})
				})
				Convey("when ModAccount is called to delete the account", func() {
					req := &qscheduler.DeleteAccountRequest{
						PoolId:    poolID,
						AccountId: accountID,
					}
					resp, err := admin.DeleteAccount(ctx, req)
					So(resp, ShouldNotBeNil)
					So(err, ShouldBeNil)
					Convey("when ListAccounts is called for that pool", func() {
						req := qscheduler.ListAccountsRequest{
							PoolId: poolID,
						}
						resp, err := view.ListAccounts(ctx, &req)
						Convey("then it returns no results.", func() {
							So(resp.Accounts, ShouldBeEmpty)
							So(err, ShouldBeNil)
						})
					})
				})
			})
		})
	})
}
