// Code generated by svcdec; DO NOT EDIT.

package api

import (
	"context"

	proto "github.com/golang/protobuf/proto"
)

type DecoratedDrone struct {
	// Service is the service to decorate.
	Service DroneServer
	// Prelude is called for each method before forwarding the call to Service.
	// If Prelude returns an error, then the call is skipped and the error is
	// processed via the Postlude (if one is defined), or it is returned directly.
	Prelude func(c context.Context, methodName string, req proto.Message) (context.Context, error)
	// Postlude is called for each method after Service has processed the call, or
	// after the Prelude has returned an error. This takes the the Service's
	// response proto (which may be nil) and/or any error. The decorated
	// service will return the response (possibly mutated) and error that Postlude
	// returns.
	Postlude func(c context.Context, methodName string, rsp proto.Message, err error) error
}

func (s *DecoratedDrone) ReportDrone(c context.Context, req *ReportDroneRequest) (rsp *ReportDroneResponse, err error) {
	if s.Prelude != nil {
		var newCtx context.Context
		newCtx, err = s.Prelude(c, "ReportDrone", req)
		if err == nil {
			c = newCtx
		}
	}
	if err == nil {
		rsp, err = s.Service.ReportDrone(c, req)
	}
	if s.Postlude != nil {
		err = s.Postlude(c, "ReportDrone", rsp, err)
	}
	return
}

func (s *DecoratedDrone) ReleaseDuts(c context.Context, req *ReleaseDutsRequest) (rsp *ReleaseDutsResponse, err error) {
	if s.Prelude != nil {
		var newCtx context.Context
		newCtx, err = s.Prelude(c, "ReleaseDuts", req)
		if err == nil {
			c = newCtx
		}
	}
	if err == nil {
		rsp, err = s.Service.ReleaseDuts(c, req)
	}
	if s.Postlude != nil {
		err = s.Postlude(c, "ReleaseDuts", rsp, err)
	}
	return
}