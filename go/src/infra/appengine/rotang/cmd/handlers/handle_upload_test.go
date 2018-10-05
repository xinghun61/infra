// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package handlers

import (
	"bytes"
	"context"
	"io"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"sort"
	"testing"
	"time"

	"infra/appengine/rotang"

	"github.com/kylelemons/godebug/pretty"
	"go.chromium.org/luci/server/router"
	"go.chromium.org/luci/server/templates"
)

const (
	jsonRotation = `
		{
			"rotation_config": {
					"calendar_name": "testCalendarLink@testland.com",
					"event_description": "Test description",
					"event_title": "Upload test",
					"owners": [
						"leowner@google.com"
					],
					"people_per_rotation": 1,
					"reminder_email_body": "Some reminder",
					"reminder_email_subject": "Chrome OS build sheriff reminder",
					"reminder_email_advance_days": 2,
					"rotation_length": 5,
					"strict_title": true,
					"temporarily_removed": {
						"email_address": "superadmin@google.com",
						"full_name": "Super Admin"
					}
				},
				"rotation_list_pacific": {
					"person": [
						{
							"email_address": "letestbot@google.com",
							"full_name": "Test Bot"
						},
						{
							"email_address": "testsheriff@google.com",
							"full_name": "Test Sheriff"
						},
						{
							"email_address": "anothersheriff@google.com",
							"full_name": "Yet Another Test Sheriff"
						}
					]
				}
		}`
	codesearchRotation = `
		{
			"rotation_config": [
				{
					"calendar_name": "testCalendarLink@testland.com",
					"event_description": "Triage for Codesearch Issues.",
					"event_title": "ChOps DevX Codesearch Triage Rotation.",
					"owners": [
						"test+one@google.com",
						"theboss@google.com"
					],
					"people_per_rotation": 1,
					"reminder_email_advance_days": 2,
					"reminder_email_body": "This is a friendly reminder that you are the Codesearch bug triager for %s. Please do daily bug triage of http://go/cr-cs-triage.",
					"reminder_email_subject": "ChOps DevX Codesearch Triage reminder",
					"rotation_length": 5,
					"strict_title": true
				}
			],
			"rotation_list_default": {
				"person": [
					{
						"email_address": "test+one@google.com",
						"full_name": "Test Bot"
					},
					{
						"email_address": "test+two@google.com",
						"full_name": "Test Sheriff"
					},
					{
						"email_address": "test+three@google.com",
						"full_name": "Yet Another Test Sheriff"
					},
					{
						"email_address": "test+four@google.com",
						"full_name": "Another codesearch wiz"
					}
				]
			}
		}`
)

type fileUpload struct {
	filename string
	reader   io.Reader
}

func uploadRequest(t *testing.T, upload []fileUpload) *http.Request {
	t.Helper()
	var buf bytes.Buffer
	multi := multipart.NewWriter(&buf)
	for _, u := range upload {
		mf, err := multi.CreateFormFile("file", u.filename)
		if err != nil {
			t.Fatalf("multi.CreateFormFile(%q, %q) failed: %v", "file", u.filename, err)
		}
		if _, err := io.Copy(mf, u.reader); err != nil {
			t.Fatalf("io.Copy() failed: %v", err)
		}
	}
	if err := multi.Close(); err != nil {
		t.Fatalf("multi.Close() failed: %v", err)
	}
	req, err := http.NewRequest("POST", "/upload", &buf)
	if err != nil {
		t.Fatalf("http.NewRequest(%q , %q , buf) failed: %v", "POST", "/upload", err)
	}
	req.Header.Set("Content-Type", multi.FormDataContentType())
	return req
}

func TestUploadGet(t *testing.T) {
	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name string
		fail bool
		ctx  *router.Context
	}{{
		name: "Failed Context",
		fail: true,
		ctx: &router.Context{
			Context: ctxCancel,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/upload", ""),
		},
	}, {
		name: "Success Get upload",
		ctx: &router.Context{
			Context: ctx,
			Writer:  httptest.NewRecorder(),
			Request: getRequest("/upload", ""),
		},
	},
	}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			tst.ctx.Context = templates.Use(tst.ctx.Context, &templates.Bundle{
				Loader: templates.FileSystemLoader(templatesLocation),
			}, nil)
		})

		h.HandleUpload(tst.ctx)

		recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
		if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
			t.Fatalf("%s: HandleUpload() = %t want: %t, res: %v", tst.name, got, want, recorder.Body)
		}
	}
}

func TestHandleUpload(t *testing.T) {
	var mtvMidnight = func() time.Time {
		t, err := time.Parse(time.RFC822, "02 Jan 06 00:00 PDT")
		if err != nil {
			panic(err)
		}
		return t
	}()

	ctx := newTestContext()
	ctxCancel, cancel := context.WithCancel(ctx)
	cancel()

	tests := []struct {
		name string
		fail bool
		ctx  *router.Context
		want []rotang.Configuration
	}{
		{
			name: "Single Upload",
			ctx: &router.Context{
				Context: ctx,
				Writer:  httptest.NewRecorder(),
				Request: uploadRequest(t, []fileUpload{
					{
						filename: "test.json",
						reader:   bytes.NewBufferString(jsonRotation),
					},
				}),
			},
			want: []rotang.Configuration{
				{
					Config: rotang.Config{
						Description:      "Test description",
						Name:             "Upload test",
						Calendar:         "testCalendarLink@testland.com",
						TokenID:          "test@admin",
						ShiftsToSchedule: 4,
						Owners:           []string{"leowner@google.com"},
						Email: rotang.Email{
							Subject:          "Chrome OS build sheriff reminder",
							Body:             "Some reminder",
							DaysBeforeNotify: 2,
						},
						Shifts: rotang.ShiftConfig{
							ShiftMembers: 1,
							StartTime:    mtvMidnight.UTC(),
							Length:       5,
							Generator:    "Legacy",
							Shifts: []rotang.Shift{
								{
									Name:     "MTV all day",
									Duration: time.Duration(24 * time.Hour),
								},
							},
						},
					},
					Members: []rotang.ShiftMember{
						{
							Email:     "letestbot@google.com",
							ShiftName: "MTV all day",
						},
						{
							Email:     "testsheriff@google.com",
							ShiftName: "MTV all day",
						},
						{
							Email:     "anothersheriff@google.com",
							ShiftName: "MTV all day",
						},
					},
				},
			},
		}, {
			name: "Broken File",
			fail: true,
			ctx: &router.Context{
				Context: ctx,
				Writer:  httptest.NewRecorder(),
				Request: uploadRequest(t, []fileUpload{
					{
						filename: "test.json",
						reader:   bytes.NewBufferString("Not JSON"),
					},
				}),
			},
		}, {
			name: "Broken Request",
			fail: true,
			ctx: &router.Context{
				Context: ctx,
				Writer:  httptest.NewRecorder(),
				Request: func() *http.Request {
					req := uploadRequest(t, []fileUpload{
						{
							filename: "test.json",
							reader:   bytes.NewBufferString("{}"),
						},
					})
					req.Header.Set("Content-Type", "bogus")
					return req
				}(),
			},
		}, {
			name: "Multi Upload",
			ctx: &router.Context{
				Context: ctx,
				Writer:  httptest.NewRecorder(),
				Request: uploadRequest(t, []fileUpload{
					{
						filename: "test.json",
						reader:   bytes.NewBufferString(jsonRotation),
					},
					{
						filename: "test2.json",
						reader:   bytes.NewBufferString(codesearchRotation),
					},
				}),
			},
			want: []rotang.Configuration{
				{
					Config: rotang.Config{
						Description:      "Test description",
						Name:             "Upload test",
						TokenID:          "test@admin",
						Calendar:         "testCalendarLink@testland.com",
						ShiftsToSchedule: 4,
						Owners:           []string{"leowner@google.com"},
						Email: rotang.Email{
							Subject:          "Chrome OS build sheriff reminder",
							Body:             "Some reminder",
							DaysBeforeNotify: 2,
						},
						Shifts: rotang.ShiftConfig{
							StartTime:    mtvMidnight.UTC(),
							ShiftMembers: 1,
							Length:       5,
							Generator:    "Legacy",
							Shifts: []rotang.Shift{
								{
									Name:     "MTV all day",
									Duration: time.Duration(24 * time.Hour),
								},
							},
						},
					},
					Members: []rotang.ShiftMember{
						{
							Email:     "letestbot@google.com",
							ShiftName: "MTV all day",
						},
						{
							Email:     "testsheriff@google.com",
							ShiftName: "MTV all day",
						},
						{
							Email:     "anothersheriff@google.com",
							ShiftName: "MTV all day",
						},
					},
				}, {
					Config: rotang.Config{
						Description:      "Triage for Codesearch Issues.",
						Name:             "ChOps DevX Codesearch Triage Rotation.",
						Calendar:         "testCalendarLink@testland.com",
						TokenID:          "test@admin",
						ShiftsToSchedule: 4,
						Owners:           []string{"test+one@google.com", "theboss@google.com"},
						Email: rotang.Email{
							Subject:          "ChOps DevX Codesearch Triage reminder",
							Body:             "This is a friendly reminder that you are the Codesearch bug triager for %s. Please do daily bug triage of http://go/cr-cs-triage.",
							DaysBeforeNotify: 2,
						},
						Shifts: rotang.ShiftConfig{
							StartTime:    mtvMidnight.UTC(),
							ShiftMembers: 1,
							Length:       5,
							Generator:    "Legacy",
							Shifts: []rotang.Shift{
								{
									Name:     "MTV all day",
									Duration: time.Duration(24 * time.Hour),
								},
							},
						},
					},
					Members: []rotang.ShiftMember{
						{
							Email:     "test+one@google.com",
							ShiftName: "MTV all day",
						},
						{
							Email:     "test+two@google.com",
							ShiftName: "MTV all day",
						},
						{
							Email:     "test+three@google.com",
							ShiftName: "MTV all day",
						},
						{
							Email:     "test+four@google.com",
							ShiftName: "MTV all day",
						},
					},
				},
			},
		}, {
			name: "Multi Upload with nonJson file",
			ctx: &router.Context{
				Context: ctx,
				Writer:  httptest.NewRecorder(),
				Request: uploadRequest(t, []fileUpload{
					{
						filename: "test.json",
						reader:   bytes.NewBufferString(jsonRotation),
					}, {
						filename: "notjson.docx",
						reader:   bytes.NewBufferString("Jibberish"),
					},
					{
						filename: "test2.json",
						reader:   bytes.NewBufferString(codesearchRotation),
					},
				}),
			},
			want: []rotang.Configuration{
				{
					Config: rotang.Config{
						Description:      "Test description",
						Name:             "Upload test",
						Calendar:         "testCalendarLink@testland.com",
						TokenID:          "test@admin",
						ShiftsToSchedule: 4,
						Owners:           []string{"leowner@google.com"},
						Email: rotang.Email{
							Subject:          "Chrome OS build sheriff reminder",
							Body:             "Some reminder",
							DaysBeforeNotify: 2,
						},
						Shifts: rotang.ShiftConfig{
							StartTime:    mtvMidnight.UTC(),
							ShiftMembers: 1,
							Length:       5,
							Generator:    "Legacy",
							Shifts: []rotang.Shift{
								{
									Name:     "MTV all day",
									Duration: time.Duration(24 * time.Hour),
								},
							},
						},
					},
					Members: []rotang.ShiftMember{
						{
							Email:     "letestbot@google.com",
							ShiftName: "MTV all day",
						},
						{
							Email:     "testsheriff@google.com",
							ShiftName: "MTV all day",
						},
						{
							Email:     "anothersheriff@google.com",
							ShiftName: "MTV all day",
						},
					},
				}, {
					Config: rotang.Config{
						Description:      "Triage for Codesearch Issues.",
						Name:             "ChOps DevX Codesearch Triage Rotation.",
						Calendar:         "testCalendarLink@testland.com",
						TokenID:          "test@admin",
						ShiftsToSchedule: 4,
						Owners:           []string{"test+one@google.com", "theboss@google.com"},
						Email: rotang.Email{
							Subject:          "ChOps DevX Codesearch Triage reminder",
							Body:             "This is a friendly reminder that you are the Codesearch bug triager for %s. Please do daily bug triage of http://go/cr-cs-triage.",
							DaysBeforeNotify: 2,
						},
						Shifts: rotang.ShiftConfig{
							ShiftMembers: 1,
							StartTime:    mtvMidnight.UTC(),
							Length:       5,
							Generator:    "Legacy",
							Shifts: []rotang.Shift{
								{
									Name:     "MTV all day",
									Duration: time.Duration(24 * time.Hour),
								},
							},
						},
					},
					Members: []rotang.ShiftMember{
						{
							Email:     "test+one@google.com",
							ShiftName: "MTV all day",
						},
						{
							Email:     "test+two@google.com",
							ShiftName: "MTV all day",
						},
						{
							Email:     "test+three@google.com",
							ShiftName: "MTV all day",
						},
						{
							Email:     "test+four@google.com",
							ShiftName: "MTV all day",
						},
					},
				},
			},
		}, {
			name: "Cancelled Context",
			fail: true,
			ctx: &router.Context{
				Context: ctxCancel,
				Writer:  httptest.NewRecorder(),
			},
		},
	}

	h := testSetup(t)

	for _, tst := range tests {
		t.Run(tst.name, func(t *testing.T) {
			h.HandleUpload(tst.ctx)
			recorder := tst.ctx.Writer.(*httptest.ResponseRecorder)
			if got, want := (recorder.Code != http.StatusOK), tst.fail; got != want {
				t.Errorf("%s: HandleUpload(ctx) = %t want: %t, status: %v, body: %v", tst.name, got, want, recorder.Code, recorder.Body)
				return
			}
			if recorder.Code != http.StatusOK {
				return
			}

			gotRotas, err := h.configStore(ctx).RotaConfig(ctx, "")
			if err != nil {
				t.Fatalf("%s: s.FetchRota(ctx,\"\") failed: %v", tst.name, err)
			}
			sort.Slice(gotRotas, func(i, j int) bool {
				return gotRotas[i].Config.Name < gotRotas[j].Config.Name
			})
			sort.Slice(tst.want, func(i, j int) bool {
				return tst.want[i].Config.Name < tst.want[j].Config.Name
			})

			for _, r := range gotRotas {
				sort.Slice(r.Members, func(i, j int) bool {
					return r.Members[i].Email < r.Members[j].Email
				})
				defer h.configStore(ctx).DeleteRotaConfig(ctx, r.Config.Name)
			}
			for _, r := range tst.want {
				sort.Slice(r.Members, func(i, j int) bool {
					return r.Members[i].Email < r.Members[j].Email
				})
			}

			if diff := pretty.Compare(tst.want, gotRotas); diff != "" {
				t.Errorf("%s: HandleUpload(ctx) differs -want +got: %s", tst.name, diff)
			}
		})
	}
}
