// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"net/http"
	"strconv"
	"strings"
	"time"

	"infra/experimental/appengine/buildbucket-viewer/api/settings"

	"github.com/luci/luci-go/common/errors"
	"github.com/luci/luci-go/common/proto/google"

	"github.com/golang/protobuf/proto"
	"github.com/julienschmidt/httprouter"
	"golang.org/x/net/context"
)

func getQueryHandler(c context.Context, req *http.Request, resp http.ResponseWriter, p httprouter.Params) error {
	params, err := parseQueryParams(req.URL.RawQuery)
	if err != nil {
		return makeHTTPError(http.StatusBadRequest, errors.Annotate(err).Reason("invalid query string").Err())
	}

	// Assemble our BuildBucket params.
	var (
		view settings.View
		cur  *settings.View_Section
	)
	addSectionIfAvailable := func() error {
		if cur != nil {
			if err := validateSection(cur); err != nil {
				return makeHTTPError(http.StatusBadRequest, err)
			}
			view.Section = append(view.Section, cur)
			cur = nil
		}
		return nil
	}
	for _, param := range params {
		// Special cases: define a new section boundary via "bucket".
		switch param.key {
		case "bucket":
			if err := addSectionIfAvailable(); err != nil {
				return err
			}
			cur = &settings.View_Section{
				Bucket: strings.Split(param.value, ","),
			}
			continue

		case "refresh": // Page refresh, in seconds.
			secs, err := strconv.ParseUint(param.value, 10, 32)
			if err != nil {
				return makeHTTPError(http.StatusBadRequest, errors.Reason("invalid 32-bit 'refresh' integer: %(param)q").
					D("param", param.value).Err())
			}
			if secs == 0 {
				return makeHTTPError(http.StatusBadRequest, errors.Reason("'refresh' parameter must be a positive number").
					D("param", param.value).Err())
			}
			view.RefreshInterval = google.NewDuration(time.Duration(secs) * time.Second)
			continue
		}

		if cur == nil {
			return makeHTTPError(http.StatusBadRequest, errors.Reason(`a section must begin with a "bucket" parameter`).Err())
		}

		switch param.key {
		case "name": // Name
			cur.Name = param.value

		case "tag": // Tag
			key, value := splitTag(param.value)

			viewTag := settings.View_Tag{
				Key: key,
			}

			if v, ok := trimPrefix(value, "$"); ok {
				// Calculated Tag
				cv, ok := proto.EnumValueMap("settings.View_Tag_CalculatedValue")[v]
				if !ok {
					return makeHTTPError(http.StatusBadRequest, errors.Reason("unknown calculated value %(name)q").D("name", v).Err())
				}

				viewTag.Tagval = &settings.View_Tag_Calc{
					Calc: settings.View_Tag_CalculatedValue(cv),
				}
			} else {
				viewTag.Tagval = &settings.View_Tag_Value{
					Value: value,
				}
			}
			cur.Tag = append(cur.Tag, &viewTag)

		case "sorttag": // Sort Tag
			cur.SortTag = append(cur.SortTag, param.value)

		case "titletag": // Title Tag
			cur.TitleTag = append(cur.TitleTag, param.value)

		case "showtag": // Show (Tag)
			cur.Show = append(cur.Show, &settings.View_Section_Show{
				What: &settings.View_Section_Show_Tag{
					Tag: param.value,
				},
			})

		case "show": // Show (Info)
			// Calculated Tag
			info, ok := proto.EnumValueMap("settings.View_Section_Show_Info")[param.value]
			if !ok {
				return makeHTTPError(http.StatusBadRequest, errors.Reason("unknown show info value %(name)q").D("name", param.value).Err())
			}

			cur.Show = append(cur.Show, &settings.View_Section_Show{
				What: &settings.View_Section_Show_Info_{
					Info: settings.View_Section_Show_Info(info),
				},
			})

		case "result": // Result status.
			rv, ok := proto.EnumValueMap("settings.View_Section_Result")[param.value]
			if !ok {
				return makeHTTPError(http.StatusBadRequest, errors.Reason("unknown result string %(value)q").D("value", param.value).Err())
			}
			cur.Result = settings.View_Section_Result(rv)

		case "max": // Max builds
			mb, err := strconv.ParseInt(param.value, 10, 32)
			if err != nil {
				return makeHTTPError(http.StatusBadRequest, errors.Reason("invalid 32-bit 'max' integer: %(param)q").
					D("param", param.value).Err())
			}
			cur.MaxBuilds = int32(mb)

		case "canary": // Canary
			cur.Canary = parseTrinary(param.value)

		default:
			return makeHTTPError(http.StatusBadRequest, errors.Reason("unknown parameter: %(param)q").D("param", param.key).Err())
		}
	}
	if err := addSectionIfAvailable(); err != nil {
		return err
	}

	// Get our application settings.
	s, err := getSettings(c, true)
	if err != nil {
		return errors.Annotate(err).InternalReason("failed to load settings").Err()
	}

	r, err := getBuildSetRenderer(c, req, s)
	if err != nil {
		return errors.Annotate(err).InternalReason("failed to get build set renderer").Err()
	}
	return r.render(&view, resp)
}

func parseTrinary(v string) settings.Trinary {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "":
		return settings.Trinary_UNSPECIFIED
	case "n", "no", "f", "false", "0":
		return settings.Trinary_NO
	default:
		return settings.Trinary_YES
	}
}
