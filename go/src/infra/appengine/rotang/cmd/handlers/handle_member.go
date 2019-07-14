package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"infra/appengine/rotang"
	"net/http"
	"time"

	"go.chromium.org/luci/common/clock"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/server/auth"
	"go.chromium.org/luci/server/router"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// JSONMember adds a TZString field to the rotang.Member structure.
// This is needed due to time.Location not having an encoding to JSON.
type JSONMember struct {
	rotang.Member
	TZString string
}

// MemberInfo is used by the shift-member element to get
// relevant member information.
type MemberInfo struct {
	Member JSONMember
	Shifts []RotaShift
}

// RotaShift contains a rota name and relevant shift
// information for the shift-member element.
type RotaShift struct {
	Name    string
	Entries []rotang.ShiftEntry
}

// HandleMember handles shift-member.
func (h *State) HandleMember(ctx *router.Context) {
	if err := ctx.Context.Err(); err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	usr := auth.CurrentUser(ctx.Context)
	if usr == nil || usr.Email == "" {
		url, err := auth.LoginURL(ctx.Context, ctx.Params.ByName("path"))
		if err != nil {
			http.Error(ctx.Writer, "not logged in", http.StatusForbidden)
			return
		}
		http.Redirect(ctx.Writer, ctx.Request, url, http.StatusFound)
		return
	}

	m, err := h.memberStore(ctx.Context).Member(ctx.Context, usr.Email)
	if err != nil {
		http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
		return
	}

	switch ctx.Request.Method {
	case "POST":
		if err := h.memberPOST(ctx, &JSONMember{
			Member:   *m,
			TZString: m.TZ.String(),
		}); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
	case "GET":
		if err := h.memberGET(ctx, m); err != nil {
			http.Error(ctx.Writer, err.Error(), http.StatusInternalServerError)
			return
		}
	default:
		http.Error(ctx.Writer, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
}

func (h *State) memberPOST(ctx *router.Context, member *JSONMember) error {
	var res rotang.Member
	if err := json.NewDecoder(ctx.Request.Body).Decode(&res); err != nil {
		return err
	}
	logging.Infof(ctx.Context, "res: %v", res)
	if res.Email != member.Email {
		return status.Errorf(codes.PermissionDenied, "only changes to your own user allowed")
	}

	for i := range res.OOO {
		if res.OOO[i].Comment == "" {
			return status.Errorf(codes.InvalidArgument, "comment needs to be set")
		}
		logging.Infof(ctx.Context, "res.OOO[i}", res.OOO[i])
	}
	loc, err := time.LoadLocation(member.TZString)
	if err != nil {
		return err
	}
	res.TZ = *loc
	return h.memberStore(ctx.Context).UpdateMember(ctx.Context, &res)
}

func (h *State) memberGET(ctx *router.Context, member *rotang.Member) error {
	rotas, err := h.configStore(ctx.Context).MemberOf(ctx.Context, member.Email)
	if err != nil {
		return err
	}
	if len(rotas) < 1 {
		return status.Errorf(codes.NotFound, "not a member of any rotations")
	}

	now := clock.Now(ctx.Context)

	shiftStore := h.shiftStore(ctx.Context)
	res := MemberInfo{
		Member: JSONMember{
			Member:   *member,
			TZString: member.TZ.String(),
		},
	}
	for _, r := range rotas {
		shifts, err := shiftStore.AllShifts(ctx.Context, r)
		if err != nil && status.Code(err) != codes.NotFound {
			return err
		}
		var entries []rotang.ShiftEntry
		for _, s := range shifts {
			if s.EndTime.After(now) {
				for _, o := range s.OnCall {
					if o.Email == member.Email {
						entries = append(entries, s)
					}
				}
			}
		}
		if len(entries) > 0 {
			res.Shifts = append(res.Shifts, RotaShift{
				Name:    r,
				Entries: entries,
			})
		}
	}

	var buf bytes.Buffer
	if err = json.NewEncoder(&buf).Encode(&res); err != nil {
		return err
	}
	_, err = fmt.Fprintln(ctx.Writer, buf.String())
	return err
}
