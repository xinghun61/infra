package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"infra/appengine/rotang"
	"net/http"
	"sort"
	"strings"
	"time"

	"go.chromium.org/gae/service/memcache"
	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/router"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// HandleLegacy serves the /legacy endpoint.
func (h *State) HandleLegacy(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	name := ctx.Params.ByName("name")

	vf, ok := h.legacyMap[name]
	if !ok {
		http.Error(ctx.Writer, "not found", http.StatusNotFound)
		return
	}

	item := memcache.NewItem(ctx.Context, name)
	if err := memcache.Get(ctx.Context, item); err != nil {
		logging.Warningf(ctx.Context, "%q not in the cache", name)
		val, err := vf(ctx, name)
		if err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
		fmt.Fprint(ctx.Writer, val)
		return
	}
	doCORS(ctx)
	fmt.Fprint(ctx.Writer, string(item.Value()))
}

func doCORS(ctx *router.Context) {
	ctx.Writer.Header().Add("Access-Control-Allow-Origin", "*")
}

const (
	trooperCal   = "google.com_3aov6uidfjscpj2hrpsd8i4e7o@group.calendar.google.com"
	matchSummary = "CCI-Trooper:"
)

type trooperJSON struct {
	Primary   string   `json:"primary"`
	Secondary []string `json:"secondary"`
	UnixTS    int64    `json:"updated_unix_timestamp"`
}

func (h *State) legacyTrooper(ctx *router.Context, file string) (string, error) {
	updated := clock.Now(ctx.Context)
	oc, err := h.legacyCalendar.TrooperOncall(ctx, trooperCal, matchSummary, updated)
	if err != nil && status.Code(err) != codes.NotFound {
		return "", err
	}
	switch file {
	case "trooper.js":
		str := "None"
		if len(oc) > 0 {
			str = oc[0]
			if len(oc) > 1 {
				str += ", secondary: " + strings.Join(oc[1:], ", ")
			}
		}
		return "document.write('" + str + "');", nil
	case "current_trooper.json":
		primary := "None"
		var secondary []string
		if len(oc) > 0 {
			primary = oc[0]
			if len(oc) > 1 {
				secondary = oc[1:]
			}
		}

		var buf bytes.Buffer
		enc := json.NewEncoder(&buf)
		if err := enc.Encode(&trooperJSON{
			Primary:   primary,
			Secondary: secondary,
			UnixTS:    updated.Unix(),
		}); err != nil {
			return "", err
		}
		return buf.String(), nil
	case "current_trooper.txt":
		if len(oc) == 0 {
			return "None", nil
		}
		return strings.Join(oc, ","), nil
	default:
		return "", status.Errorf(codes.InvalidArgument, "legacyTrooper only handles `trooper.js` and `current_trooper.txt`")
	}
}

var fileToRota = map[string][2]string{
	"sheriff.js": {"Build Sheriff", ""},
	// "sheriff_webkit.js":              "",
	// "sheriff_memory.js":              "",
	"sheriff_cros_mtv.js":          {"Chrome OS Build Sheriff", ""},
	"sheriff_cros_nonmtv.js":       {"Chrome OS Build Sheriff - Other", "Chrome OS Build Sheriff"},
	"sheriff_perf.js":              {"Chromium Perf Regression Sheriff Rotation", ""},
	"sheriff_cr_cros_gardeners.js": {"Chrome on ChromeOS Gardening", ""},
	"sheriff_gpu.js":               {"Chrome GPU Pixel Wrangling", ""},
	"sheriff_angle.js":             {"The ANGLE Wrangle", ""},
	"sheriff_android.js":           {"Chrome on Android Build Sheriff", ""},
	"sheriff_ios.js":               {"Chrome iOS Build Sheriff", ""},
	"sheriff_v8.js":                {"V8 Sheriff", ""},
	"sheriff_perfbot.js":           {"Chromium Perf Bot Sheriff Rotation", ""},

	"sheriff.json": {"Build Sheriff", ""},
	// "sheriff_webkit.json":            "", // In the cron file but does not have a configuration.
	// "sheriff_memory.json":            "", // In the cron file but does not have a configuration.
	"sheriff_cros_mtv.json":          {"Chrome OS Build Sheriff", ""},
	"sheriff_cros_nonmtv.json":       {"Chrome OS Build Sheriff - Other", "Chrome OS Build Sheriff"},
	"sheriff_perf.json":              {"Chromium Perf Regression Sheriff Rotation", ""},
	"sheriff_cr_cros_gardeners.json": {"Chrome on ChromeOS Gardening", ""},
	"sheriff_gpu.json":               {"Chrome GPU Pixel Wrangling", ""},
	"sheriff_angle.json":             {"The ANGLE Wrangle", ""},
	"sheriff_android.json":           {"Chrome on Android Build Sheriff", ""},
	"sheriff_ios.json":               {"Chrome iOS Build Sheriff", ""},
	"sheriff_v8.json":                {"V8 Sheriff", ""},
	"sheriff_perfbot.json":           {"Chromium Perf Bot Sheriff Rotation", ""},
	//"all_rotations.js":               "",
	//"all_rotations.js":               "",
}

const week = 7 * 24 * time.Hour

type sheriffJSON struct {
	UnixTS int64    `json:"updated_unix_timestamp"`
	Emails []string `json:"emails"`
}

// legacySheriff produces the legacy cron created sherriff oncall files.
func (h *State) legacySheriff(ctx *router.Context, file string) (string, error) {
	rota, ok := fileToRota[file]
	if !ok {
		return "", status.Errorf(codes.InvalidArgument, "file: %q not handled by legacySheriff", file)
	}
	r, err := h.configStore(ctx.Context).RotaConfig(ctx.Context, rota[0])
	if err != nil {
		return "", err
	}
	if len(r) != 1 {
		return "", status.Errorf(codes.Internal, "RotaConfig did not return 1 configuration")
	}
	cfg := r[0]
	// As a workaround to handle split shifts some users create multiple configurations with different
	// calendars but the same Event Name. The new service use the rota name as a key in the datastore.
	if rota[1] != "" {
		cfg.Config.Name = rota[1]
	}

	updated := clock.Now(ctx.Context)
	events, err := h.legacyCalendar.Events(ctx, cfg, updated.Add(-week), updated.Add(week))
	if err != nil {
		return "", err
	}

	var entry rotang.ShiftEntry
	for _, e := range events {
		if (updated.After(e.StartTime) || updated.Equal(e.StartTime)) &&
			updated.Before(e.EndTime) {
			entry = e
		}
	}

	sp := strings.Split(file, ".")
	if len(sp) != 2 {
		return "", status.Errorf(codes.InvalidArgument, "filename in wrong format")
	}

	switch sp[1] {
	case "js":
		var oc []string
		for _, o := range entry.OnCall {
			oc = append(oc, strings.Split(o.Email, "@")[0])
		}
		str := "None"
		if len(oc) > 0 {
			str = strings.Join(oc, ", ")
		}
		return "document.write('" + str + "');", nil
	case "json":
		// This makes the JSON encoder produce `[]` instead of `null`
		// for empty lists.
		oc := make([]string, 0)
		for _, o := range entry.OnCall {
			oc = append(oc, o.Email)
		}
		var buf bytes.Buffer
		enc := json.NewEncoder(&buf)
		if err := enc.Encode(&sheriffJSON{
			UnixTS: updated.Unix(),
			Emails: oc,
		}); err != nil {
			return "", err
		}
		return buf.String(), nil

	default:
		return "", status.Errorf(codes.InvalidArgument, "filename in wrong format")
	}
}

var rotaToName = map[string][2]string{
	"angle":                   {"The ANGLE Wrangle", ""},
	"arc":                     {"ARC Sheriff+Release duty", ""},
	"ios_internal_roll":       {"Bling Piper Roll", ""},
	"bling":                   {"Chrome iOS Build Sheriff", ""},
	"blink_bug_triage":        {"Blink Bug Triage", ""},
	"blink_media_triage":      {"Blink Media Bug Triage Rotation", ""},
	"chromeosgardener":        {"Chrome on ChromeOS Gardening", ""},
	"chromeosgardener.shadow": {"Chrome on ChromeOS Gardening Shadow", ""},
	"chromeos.other":          {"Chrome OS Build Sheriff - Other", "Chrome OS Build Sheriff"},
	"chromeos":                {"Chrome OS Build Sheriff", ""},
	"chrome":                  {"Build Sheriff", ""},
	"android":                 {"Chrome on Android Build Sheriff", ""},
	"android_stability":       {"Chrome on Android Stability Sheriff", "Clank Stability Sheriff"},
	"codesearch":              {"ChOps DevX Codesearch Triage Rotation", ""},
	"ecosystem_infra":         {"Ecosystem Infra rotation", ""},
	"fizzlon_bugcop":          {"Fizz London Bug Cop", ""},
	"gitadmin":                {"Chrome Infra Git Admin Rotation", ""},
	"gpu":                     {"Chrome GPU Pixel Wrangling", ""},
	"headless_roll":           {"Headless Chrome roll sheriff", ""},
	"infra_platform":          {"Chops Foundation Triage", ""},
	"infra_triage":            {"Chrome Infra Bug Triage Rotation", ""},
	"media_ux_triage":         {"Chrome Media UX Bug Triage Rotation", ""},
	"monorail":                {"Chrome Infra Monorail Triage Rotation", ""},
	"network":                 {"Chrome Network Bug Triage", ""},
	"perfbot":                 {"Chromium Perf Bot Sheriff Rotation", ""},
	"ios":                     {"Chrome iOS Build Sheriff", ""},
	"perf":                    {"Chromium Perf Regression Sheriff Rotation", ""},
	"sdk":                     {"ChOps DevX SDK Triage Rotation", ""},
	"sheriff-o-matic":         {"Sheriff-o-Matic Bug Triage Rotation", ""},
	"stability":               {"Chromium Stability Sheriff", ""},
	"v8_infra_triage":         {"V8 Infra Bug Triage Rotation", ""},
	// "v8":                      {"V8 Sheriff", ""}, // Nothing in their calendar.
	"webview_bugcop": {"WebView Bug Cop", ""},
	"flutter_engine": {"Flutter Engine Rotation", ""},
	//"troopers":              {"", ""} // Handled in it's own way.
}

const (
	fullDay     = 24 * time.Hour
	timeDelta   = 90 * fullDay
	trooperRota = "troopers"
)

type allRotations struct {
	Rotations []string   `json:"rotations"`
	Calendar  []dayEntry `json:"calendar"`
}

type dayEntry struct {
	Date         string     `json:"date"`
	Participants [][]string `json:"participants"`
}

func (h *State) legacyAllRotations(ctx *router.Context, _ string) (string, error) {
	start := clock.Now(ctx.Context).In(mtvTime)
	end := start.Add(timeDelta)
	cs := h.configStore(ctx.Context)

	var res allRotations
	dateMap := make(map[string]map[string][]string)

	// The Sheriff rotations.
	for k, v := range rotaToName {
		rs, err := cs.RotaConfig(ctx.Context, v[0])
		if err != nil {
			logging.Errorf(ctx.Context, "Getting configuration for: %q failed: %v", v, err)
			continue
		}
		if len(rs) != 1 {
			return "", status.Errorf(codes.Internal, "RotaConfig did not return 1 configuration")
		}
		cfg := rs[0]
		if v[1] != "" {
			cfg.Config.Name = v[1]
		}
		shifts, err := h.legacyCalendar.Events(ctx, cfg, start, end)
		if err != nil {
			logging.Errorf(ctx.Context, "Fetching calendar events for: %q failed: %v", v[0], err)
			continue
		}
		res.Rotations = append(res.Rotations, k)
		//buildSheriffRotation(ctx.Context, dateMap, k, start, shifts)
		buildLegacyRotation(dateMap, k, shifts)
	}
	// Troopers rotation.
	ts, err := h.legacyCalendar.TrooperShifts(ctx, trooperCal, matchSummary, start, end)
	if err != nil {
		return "", err
	}
	buildLegacyRotation(dateMap, trooperRota, ts)
	res.Rotations = append(res.Rotations, trooperRota)

	for k, v := range dateMap {
		entry := dayEntry{
			Date: k,
		}
		for _, r := range res.Rotations {
			p, ok := v[r]
			// When JSON encoding slices creating a slice with.
			// var bla []slice -> Produces `null` in the json output.
			// If instead creating the slice with.
			// make([]string,0) -> Will produce `[]`.
			if !ok || len(p) == 0 {
				p = make([]string, 0)
			}
			entry.Participants = append(entry.Participants, p)
		}
		res.Calendar = append(res.Calendar, entry)
	}

	sort.Slice(res.Calendar, func(i, j int) bool {
		return res.Calendar[i].Date < res.Calendar[j].Date
	})

	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	if err := enc.Encode(res); err != nil {
		return "", err
	}

	return buf.String(), nil
}

func buildLegacyRotation(dateMap map[string]map[string][]string, rota string, shifts []rotang.ShiftEntry) {
	if len(shifts) < 1 {
		return
	}
	for _, s := range shifts {
		// Truncade to fulldays for go/chromecals
		date := time.Date(s.StartTime.Year(), s.StartTime.Month(), s.StartTime.Day(), 0, 0, 0, 0, time.UTC)
		oc := make([]string, 0)
		for _, o := range s.OnCall {
			oc = append(oc, strings.Split(o.Email, "@")[0])
		}
		for ; ; date = date.Add(fullDay) {
			s.StartTime = time.Date(s.StartTime.Year(), s.StartTime.Month(), s.StartTime.Day(), 0, 0, 0, 0, time.UTC)
			s.EndTime = time.Date(s.EndTime.Year(), s.EndTime.Month(), s.EndTime.Day(), 0, 0, 0, 0, time.UTC)
			if !((date.After(s.StartTime) || date.Equal(s.StartTime)) && date.Before(s.EndTime)) {
				break
			}
			if _, ok := dateMap[date.Format(elementTimeFormat)]; !ok {
				dateMap[date.Format(elementTimeFormat)] = make(map[string][]string)
			}
			dateMap[date.Format(elementTimeFormat)][rota] = append(dateMap[date.Format(elementTimeFormat)][rota], oc...)
		}
	}
}
