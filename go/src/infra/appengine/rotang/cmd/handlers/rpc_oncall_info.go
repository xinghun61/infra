package handlers

import (
	"context"
	"time"

	"github.com/golang/protobuf/ptypes"
	"go.chromium.org/luci/common/clock"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"infra/appengine/rotang"

	apb "infra/appengine/rotang/proto/rotangapi"
)

// Oncall returns the current oncaller for the specified shift.
func (h *State) Oncall(ctx context.Context, req *apb.OncallRequest) (*apb.OncallResponse, error) {
	if req.GetName() == "" {
		return nil, status.Errorf(codes.InvalidArgument, "rotation name is required")
	}
	cfg, err := h.configStore(ctx).RotaConfig(ctx, req.Name)
	if err != nil {
		return nil, err
	}

	if len(cfg) != 1 {
		return nil, status.Errorf(codes.Internal, "RotaConfig did not return 1 configuration, got: %d", len(cfg))
	}

	var tzConsider bool
	if !cfg[0].Config.External {
		gen, err := h.generators.Fetch(cfg[0].Config.Shifts.Generator)
		if err != nil {
			return nil, err
		}
		tzConsider = gen.TZConsider()
	}

	shift, err := h.shiftStore(ctx).Oncall(ctx, clock.Now(ctx), req.Name)
	if err != nil {
		if status.Code(err) == codes.NotFound {
			return &apb.OncallResponse{
				TzConsider: tzConsider,
			}, nil
		}
		return nil, err
	}

	s, err := h.shiftsToProto(ctx, []rotang.ShiftEntry{*shift})
	if err != nil {
		return nil, err
	}
	if len(s) != 1 {
		return nil, status.Errorf(codes.Internal, "found: %d shifts, should be 1", len(s))
	}

	return &apb.OncallResponse{
		Shift:      s[0],
		TzConsider: tzConsider,
	}, nil
}

// ListRotations returns a list of all rotations known to RotaNG.
func (h *State) ListRotations(ctx context.Context, _ *apb.ListRotationsRequest) (*apb.ListRotationsResponse, error) {
	rotations, err := h.configStore(ctx).RotaConfig(ctx, "")
	if err != nil {
		return nil, err
	}
	var res []*apb.Rotation
	for _, r := range rotations {
		var shiftCfg []*apb.ShiftConfiguration
		for _, s := range r.Config.Shifts.Shifts {
			shiftCfg = append(shiftCfg, &apb.ShiftConfiguration{
				Name:     s.Name,
				Duration: ptypes.DurationProto(s.Duration),
			})
		}
		res = append(res, &apb.Rotation{
			Name:    r.Config.Name,
			Enabled: r.Config.Enabled,
		})
	}
	return &apb.ListRotationsResponse{
		Rotations: res,
	}, nil
}

// Shifts returns a list of shift for the specified rotation and period.
func (h *State) Shifts(ctx context.Context, req *apb.ShiftsRequest) (*apb.ShiftsResponse, error) {
	if req.GetName() == "" {
		return nil, status.Errorf(codes.InvalidArgument, "rotation name is required")
	}

	if _, err := h.configStore(ctx).RotaConfig(ctx, req.Name); err != nil {
		return nil, err
	}

	start, end := time.Time{}, time.Time{}
	if ps := req.GetStart(); ps != nil {
		s, err := ptypes.Timestamp(req.GetStart())
		if err != nil {
			return nil, err
		}
		start = s
	}
	if pe := req.GetEnd(); pe != nil {
		e, err := ptypes.Timestamp(req.GetEnd())
		if err != nil {
			return nil, err
		}
		end = e
	}

	shifts, err := h.shiftStore(ctx).ShiftsFromTo(ctx, req.GetName(), start, end)
	if err != nil {
		if status.Code(err) == codes.NotFound {
			return &apb.ShiftsResponse{}, nil
		}
		return nil, err
	}
	res, err := h.shiftsToProto(ctx, shifts)
	if err != nil {
		return nil, err
	}
	return &apb.ShiftsResponse{
		Shifts: res,
	}, nil
}

func (h *State) shiftsToProto(ctx context.Context, shifts []rotang.ShiftEntry) ([]*apb.ShiftEntry, error) {
	var res []*apb.ShiftEntry
	for _, s := range shifts {
		protoStart, err := ptypes.TimestampProto(s.StartTime)
		if err != nil {
			return nil, err
		}
		protoEnd, err := ptypes.TimestampProto(s.EndTime)
		if err != nil {
			return nil, err
		}
		oncall, err := h.protoOnCaller(ctx, &s)
		if err != nil {
			return nil, err
		}
		res = append(res, &apb.ShiftEntry{
			Name:      s.Name,
			Oncallers: oncall,
			Start:     protoStart,
			End:       protoEnd,
			Comment:   s.Comment,
			EventId:   s.EvtID,
		})
	}
	return res, nil
}

func (h *State) protoOnCaller(ctx context.Context, shift *rotang.ShiftEntry) ([]*apb.OnCaller, error) {
	var res []*apb.OnCaller
	store := h.memberStore(ctx)
	for _, o := range shift.OnCall {
		m, err := store.Member(ctx, o.Email)
		if err != nil {
			return nil, err
		}
		res = append(res, &apb.OnCaller{
			Email: o.Email,
			Name:  m.Name,
			Tz:    m.TZ.String(),
		})
	}
	return res, nil
}
