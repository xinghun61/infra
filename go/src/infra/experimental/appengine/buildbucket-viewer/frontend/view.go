// Copyright 2016 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package frontend

import (
	"fmt"
	"io"
	"net/http"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"infra/experimental/appengine/buildbucket-viewer/api/settings"

	bbapi "github.com/luci/luci-go/common/api/buildbucket/buildbucket/v1"
	"github.com/luci/luci-go/common/errors"
	log "github.com/luci/luci-go/common/logging"
	"github.com/luci/luci-go/common/proto/google"
	"github.com/luci/luci-go/common/sync/parallel"
	"github.com/luci/luci-go/common/sync/promise"
	"github.com/luci/luci-go/server/auth"
	"github.com/luci/luci-go/server/templates"

	"github.com/luci/gae/service/memcache"

	"golang.org/x/net/context"
)

// maxRequestWorkers is the maximum number of BuildBucket
// goroutines that can be used servicing a single request.
const maxRequestWorkers = 4

const calculatedValueCacheTime = 10 * time.Second

// buildStatus is an enumeration of supported build status states.
type buildStatus string

const (
	// buildPending is a build in SCHEDULED state.
	buildPending buildStatus = "pending"
	// buildRunning is a build in STARTED state.
	buildRunning buildStatus = "running"
	// buildSuccess is a build in COMPLETED state with result SUCCESS.
	buildSuccess buildStatus = "success"
	// buildCanceled is a build in COMPLETED state with result CANCELED,
	// regardless of cancellation reason.
	buildCanceled buildStatus = "canceled"
	// buildException is a build in COMPLETED state with result FAILURE and
	// failure reason anything other than BUILD_FAILURE.
	buildException buildStatus = "exception"
	// buildFailed is a build in COMPLETED state with result FAILURE and failure
	// reason BUILD_FAILURE.
	buildFailed buildStatus = "failed"
	// buildInvalid is a build in COMPLETED state with result FAILURE and reason
	// INVALID_BUILD_DEFINITION.
	buildInvalid buildStatus = "invalid"
)

var buildStatusOrder = map[buildStatus]int{
	buildPending:   0,
	buildSuccess:   1,
	buildCanceled:  2,
	buildRunning:   3,
	buildException: 4,
	buildFailed:    5,
	buildInvalid:   6,
}

// buildBotURLRegexp matches a BuildBot build URL:
//
// http://build.chromium.org/p/<master>/builders/<builder>/builds/<number>
var buildBotURLRegexp = regexp.MustCompile("http(s)?://.+/[pi]/([^/]+)/builders/([^/]+)/builds/(.+)")

func (bs buildStatus) aggregate(other buildStatus) buildStatus {
	if buildStatusOrder[bs] < buildStatusOrder[other] {
		return other
	}
	return bs
}

func getBuildStatus(b *bbapi.ApiCommonBuildMessage) buildStatus {
	switch b.Status {
	case "SCHEDULED":
		return buildPending

	case "STARTED":
		return buildRunning

	case "COMPLETED":
		switch b.Result {
		case "CANCELED":
			return buildCanceled

		case "FAILURE":
			switch b.FailureReason {
			case "INVALID_BUILD_DEFINITION":
				return buildInvalid
			case "BUILD_FAILURE":
				return buildFailed
			default:
				return buildException
			}

		case "SUCCESS":
			return buildSuccess
		}
	}
	return buildInvalid
}

type build struct {
	// ID is the BuildBucket ID
	ID int64

	// Title is the main title of the build.
	Title string
	// Status is the build status string.
	Status buildStatus
	// Subtext is individual lines of context text beneath the title.
	Subtext []string

	// URL is the URL for the build status for this build.
	URL string
	// BuildURL is the URL to the BuildBucket view.
	BuildURL string

	// CreatedTS is the time when this build was created.
	Created time.Time
	// Updated is the time when this build was last updated.
	Updated time.Time

	tags map[string][]string
}

func (b *build) getOneTag(k string) string {
	value := b.tags[k]
	if len(value) == 0 {
		return ""
	}
	return value[0]
}

func (b *build) hasTagValue(key, value string) bool {
	for _, tag := range b.tags[key] {
		if tag == value {
			return true
		}
	}
	return false
}

type buildSet struct {
	// name is the name of this build set.
	Name string

	// Status is the aggregate status of the build set.
	Status buildStatus

	// Builds is the set of builds that belongs to this BuildSet.
	Builds []*build

	// ErrorMsg, if not empty, means that an error occurred loading this buildSet.
	// This preempts any other non-error fields in this struct.
	ErrorMsg string
}

func validateSection(s *settings.View_Section) error {
	if len(s.Bucket) == 0 {
		return errors.New("at least one bucket must be supplied")
	}
	for _, b := range s.Bucket {
		if b == "" {
			return errors.New("cannot have empty bucket name")
		}
	}
	return nil
}

type buildSetRenderer struct {
	context.Context
	*settings.Settings

	req       *http.Request
	bbService *bbapi.Service

	calcValueMu sync.Mutex
	calcValue   map[settings.View_Tag_CalculatedValue]*promise.Promise
}

func getBuildSetRenderer(c context.Context, req *http.Request, s *settings.Settings) (*buildSetRenderer, error) {
	// Get BuildBucket client. We use delegation to communicate with BuildBucket
	// as the current user.
	transport, err := auth.GetRPCTransport(c, auth.AsUser)
	if err != nil {
		return nil, errors.Annotate(err, "").InternalReason("failed to get RPC transport").Err()
	}

	svc, err := bbapi.New(&http.Client{Transport: transport})
	if err != nil {
		return nil, errors.Annotate(err, "").InternalReason("failed to get BuildBucket client").Err()
	}
	svc.BasePath = fmt.Sprintf("https://%s/_ah/api/buildbucket/v1/", s.BuildbucketHost)

	return &buildSetRenderer{
		Context:   c,
		Settings:  s,
		req:       req,
		bbService: svc,
	}, nil
}

func (r *buildSetRenderer) render(v *settings.View, w io.Writer) error {
	// Resolve calculated tags. First, scan through our view and identify all of
	// the tags that need resolution.
	var resolved map[settings.View_Tag_CalculatedValue]string
	for _, s := range v.Section {
		for _, tag := range s.Tag {
			if cv := tag.GetCalc(); cv != settings.View_Tag_EMPTY {
				if resolved == nil {
					resolved = make(map[settings.View_Tag_CalculatedValue]string)
				}
				resolved[cv] = ""
			}
		}
	}

	// Execute BuildBucket queries. Our WorkPool function cannot fail, since its
	// inner method doesn't return an error. Instead, if an error occurs, it will
	// be populated in that request's "buildSets" entry for template rendering.
	buildSets := make([]*buildSet, len(v.Section))
	_ = parallel.WorkPool(maxRequestWorkers, func(taskC chan<- func() error) {
		for i, s := range v.Section {
			i, s := i, s
			taskC <- func() error {
				bs, err := r.fetchViewSection(s)
				if err != nil {
					log.Fields{
						log.ErrorKey: err,
						"bucket":     s.Bucket,
						"tags":       s.Tag,
					}.Errorf(r, "Failed to fetch BuildSet.")

					// Create an error-state buildSet.
					buildSets[i] = &buildSet{
						Status:   buildInvalid,
						ErrorMsg: err.Error(),
					}
				} else {
					buildSets[i] = bs
				}
				return nil
			}
		}
	})

	// Determine our title.
	title := v.Title
	if title == "" {
		title = "BuildBucket Builds"
	}

	// Build template arguments.
	log.Fields{
		"count": len(buildSets),
	}.Debugf(r, "Rendering build sets.")
	args, err := getDefaultTemplateArgs(r, r.req)
	if err != nil {
		return errors.Annotate(err, "").InternalReason("failed to get default template args").Err()
	}
	args["Title"] = title
	args["BuildSets"] = buildSets
	if d := google.DurationFromProto(v.RefreshInterval); d >= 0 {
		args["RefreshIntervalSecs"] = int(d.Seconds())
	}

	// Render template.
	templates.MustRender(r, w, "pages/query.html", args)
	return nil
}

func (r *buildSetRenderer) loadCalculatedValue(cv settings.View_Tag_CalculatedValue) (string, error) {
	// Get our Promise; create one if necessary.
	var p *promise.Promise
	func() {
		r.calcValueMu.Lock()
		defer r.calcValueMu.Unlock()

		p = r.calcValue[cv]
		if p == nil {
			p = promise.New(r, func(c context.Context) (interface{}, error) {
				return r.resolveCalculatedValue(c, cv)
			})

			if r.calcValue == nil {
				r.calcValue = make(map[settings.View_Tag_CalculatedValue]*promise.Promise)
			}
			r.calcValue[cv] = p
		}
	}()

	v, err := p.Get(r)
	if err != nil {
		return "", errors.Annotate(err, "").Err()
	}
	return v.(string), nil
}

func (r *buildSetRenderer) fetchViewSection(s *settings.View_Section) (*buildSet, error) {
	// Augment "s.Tag" with the resolved values.
	for _, tag := range s.Tag {
		if cv := tag.GetCalc(); cv != settings.View_Tag_EMPTY {
			val, err := r.loadCalculatedValue(cv)
			if err != nil {
				return nil, errors.Annotate(err, "").InternalReason("failed to load calculated value").Err()
			}

			tag.Tagval = &settings.View_Tag_Value{
				Value: val,
			}
		}
	}

	tags := make([]string, 0, len(s.Tag))
	for _, tag := range s.Tag {
		tags = append(tags, assembleTag(tag.Key, tag.GetValue()))
	}
	sort.Strings(tags)

	// Determine our result constraint string.
	var result, failureReason string
	switch s.Result {
	case settings.View_Section_SUCCESS:
		result = "SUCCESS"
	case settings.View_Section_CANCELED:
		result = "CANCELED"
	case settings.View_Section_FAILURE:
		result = "FAILURE"
	case settings.View_Section_BUILDBUCKET_FAILURE:
		result = "FAILURE"
		failureReason = "BUILDBUCKET_FAILURE"
	case settings.View_Section_BUILD_FAILURE:
		result = "FAILURE"
		failureReason = "BUILD_FAILURE"
	case settings.View_Section_INFRA_FAILURE:
		result = "FAILURE"
		failureReason = "INFRA_FAILURE"
	case settings.View_Section_INVALID_BUILD_DEFINITION:
		result = "FAILURE"
		failureReason = "INVALID_BUILD_DEFINITION"
	}

	searchBuilds, err := buildBucketSearch(r, r.bbService, s.Bucket, tags, s.Canary, result, failureReason, int(s.MaxBuilds))
	if err != nil {
		return nil, errors.Annotate(err, "").InternalReason("BuildBucket Search() error").Err()
	}

	// Translate our BuildBucket response into internal "build"s.
	var (
		builds          = make([]*build, len(searchBuilds))
		aggregateStatus = buildPending
	)
	for i, b := range searchBuilds {
		build := build{
			ID:      b.Id,
			Title:   s.Name,
			Status:  getBuildStatus(b),
			Subtext: nil,
			BuildURL: fmt.Sprintf(
				"https://apis-explorer.appspot.com/apis-explorer/?base=https://%s/_ah/api#p/buildbucket/v1/buildbucket.get?id=%d",
				r.BuildbucketHost, b.Id),
			Created: timeFromMicrosecondsSinceEpoch(b.CreatedTs),
			Updated: timeFromMicrosecondsSinceEpoch(b.UpdatedTs),
			URL:     b.Url,
		}

		aggregateStatus = aggregateStatus.aggregate(build.Status)

		// Ingest build tags into our tag map.
		for _, tag := range b.Tags {
			if build.tags == nil {
				build.tags = map[string][]string{}
			}

			k, v := splitTag(tag)
			build.tags[k] = append(build.tags[k], v)
		}

		// See if we can convert this to a Milo URL.
		if build.URL != "" {
			if mh := r.MiloHost; mh != "" {
				if miloURL, err := maybeGetMiloURL(mh, &build); err != nil {
					log.Fields{
						log.ErrorKey: err,
						"url":        build.URL,
					}.Debugf(r, "Could not construct Milo URL.")
				} else {
					build.URL = miloURL
				}
			}
		}

		// Generate our title.
		titleTags := make([]string, 0, len(s.TitleTag)+1)
		for _, tt := range s.TitleTag {
			if v := build.getOneTag(tt); v != "" {
				titleTags = append(titleTags, v)
			}
		}
		if len(titleTags) == 0 {
			titleTags = append(titleTags, strconv.FormatInt(b.Id, 10))
		}
		build.Title = strings.Join(titleTags, " ")

		// Assemble our subtext from show values.
		for _, show := range s.Show {
			if st := show.GetTag(); st != "" {
				for _, v := range build.tags[st] {
					build.Subtext = append(build.Subtext, v)
				}
			}
			switch show.GetInfo() {
			case settings.View_Section_Show_NONE:
				break

			case settings.View_Section_Show_STATUS:
				build.Subtext = append(build.Subtext, fmt.Sprintf("Status: %s", b.Status))

			case settings.View_Section_Show_FAILURE_REASON:
				if fr := b.FailureReason; fr != "" {
					build.Subtext = append(build.Subtext, fmt.Sprintf("Failure Reason: %s", fr))
				}
			}
		}

		builds[i] = &build
	}

	sbb := sortableBuildSlice{
		sortTags: s.SortTag,
		builds:   builds,
	}
	sort.Sort(&sbb)

	// Assemble our build set.
	bs := buildSet{
		Name:   s.Name,
		Status: aggregateStatus,
		Builds: sbb.builds,
	}
	if bs.Name == "" {
		bs.Name = strings.Join(append(append([]string(nil), s.Bucket...), tags...), " ")
	}
	return &bs, nil
}

func (r *buildSetRenderer) resolveCalculatedValue(c context.Context, cv settings.View_Tag_CalculatedValue) (string, error) {
	// Pull the value from memcache, if available.
	memcacheKey := fmt.Sprintf("calculated_value_%s", cv)
	switch itm, err := memcache.GetKey(c, memcacheKey); err {
	case nil:
		return string(itm.Value()), nil

	case memcache.ErrCacheMiss:
		break

	default:
		log.Fields{
			log.ErrorKey: err,
			"cv":         cv,
			"key":        memcacheKey,
		}.Warningf(r, "Memcache error when looking up calculated value.")
	}

	// Perform a lookup.
	var (
		v   string
		err error
	)
	switch cv {
	case settings.View_Tag_LATEST_PALADIN_BUILD:
		if v, err = r.queryLatestForTags(c, r.MasterBucket, "buildset", "master:False", "build_type:paladin"); err != nil {
			return "", errors.Annotate(err, "").Err()
		}

	case settings.View_Tag_LATEST_PFQ_BUILD:
		if v, err = r.queryLatestForTags(c, r.MasterBucket, "buildset", "master:False", "build_type:pfq"); err != nil {
			return "", errors.Annotate(err, "").Err()
		}

	case settings.View_Tag_LATEST_CANARY_BUILD:
		if v, err = r.queryLatestForTags(c, r.MasterBucket, "buildset", "master:False", "build_type:release"); err != nil {
			return "", errors.Annotate(err, "").Err()
		}

	case settings.View_Tag_LATEST_RELEASE_BUILD:
		if v, err = r.queryLatestForTags(c, r.ReleaseBucket, "buildset", "master:False", "build_type:release"); err != nil {
			return "", errors.Annotate(err, "").Err()
		}

	case settings.View_Tag_LATEST_TOOLCHAIN_BUILD:
		if v, err = r.queryLatestForTags(c, r.MasterBucket, "buildset", "master:False", "build_type:toolchain"); err != nil {
			return "", errors.Annotate(err, "").Err()
		}

	default:
		return "", errors.Reason("unknown calculated value %q", cv).Err()
	}

	// Add this value to memcache.
	itm := memcache.NewItem(c, memcacheKey)
	itm.SetValue([]byte(v))
	itm.SetExpiration(calculatedValueCacheTime)
	if err := memcache.Add(c, itm); err != nil {
		log.Fields{
			log.ErrorKey: err,
			"cv":         cv,
			"key":        memcacheKey,
		}.Warningf(c, "Failed to cache calculated value.")
	}
	return v, nil
}

func (r *buildSetRenderer) queryLatestForTags(c context.Context, bucket, extractTag string, tags ...string) (string, error) {
	if bucket == "" {
		return "", errors.New("bucket is not defined")
	}

	builds, err := buildBucketSearch(c, r.bbService, []string{bucket}, tags, settings.Trinary_UNSPECIFIED, "", "", 1)
	if err != nil {
		return "", errors.Annotate(err, "").InternalReason(
			"failed to search for %q: bucket(%q)/tags(%v)", extractTag, bucket, tags).Err()
	}

	if len(builds) < 1 {
		return "", errors.Annotate(err, "").InternalReason(
			"no matching builds: extract(%q)/bucket(%q)/tags(%v)", extractTag, bucket, tags).Err()
	}
	build := builds[0]

	for _, tag := range build.Tags {
		k, v := splitTag(tag)
		if k == extractTag {
			log.Fields{
				"id":         build.Id,
				"extractTag": extractTag,
				"value":      v,
			}.Infof(c, "Using build to extract tag value.")
			return v, nil
		}
	}

	return "", errors.Reason("matching build %d was missing %q tag", build.Id, extractTag).
		InternalReason("bucket(%q)/tags(%v)", bucket, tags).Err()
}

type sortableBuildSlice struct {
	sortTags []string
	builds   []*build
}

func (sbb *sortableBuildSlice) Len() int { return len(sbb.builds) }
func (sbb *sortableBuildSlice) Swap(i, j int) {
	sbb.builds[i], sbb.builds[j] = sbb.builds[j], sbb.builds[i]
}

func (sbb *sortableBuildSlice) Less(i, j int) bool {
	bi, bj := sbb.builds[i], sbb.builds[j]
	for _, st := range sbb.sortTags {
		if ti := bi.getOneTag(st); ti != "" {
			if tj := bj.getOneTag(st); tj != "" {
				if ti < tj {
					return true
				}
				if ti > tj {
					return false
				}
			} else {
				// Has Tag < No Tag
				return true
			}
		} else {
			if tj := bj.getOneTag(st); tj != "" {
				// No Tag > Has Tag
				return false
			}
		}
	}

	// Neither entry has a tag. Compare ID.
	return bi.ID < bj.ID
}

func maybeGetMiloURL(host string, build *build) (string, error) {
	if u := build.URL; u != "" {
		// Is this a BuildBot URL?
		parts := buildBotURLRegexp.FindStringSubmatch(u)
		if len(parts) < 5 {
			return "", errors.Reason("URL is not a BuildBot build URL: %q", u).Err()
		}

		master, builder, buildNumber := parts[2], parts[3], parts[4]
		return fmt.Sprintf("https://%s/buildbot/%s/%s/%s", host, master, builder, buildNumber), nil
	}

	return "", errors.Reason("unrecognized build pattern").Err()
}
