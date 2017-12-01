# Monorail API v2

This directory holds all the source for the Monorail API v2. This API is
implemented using `.proto` files to describe a `gRPC` interface (services,
methods, and request/response messages). It then uses a shim which
converts the
[`gRPC` server](http://www.grpc.io/docs/tutorials/basic/python.html)
(which doesn't work on AppEngine, due to lack of support for HTTP/2) into a
[`pRPC` server](https://godoc.org/github.com/luci/luci-go/grpc/prpc) which
supports communication over HTTP/1.1, as well as text and JSON IO.

## Regenerating Python from Protocol Buffers

In order to regenerate the python server and client stubs from the `.proto`
files, follow these steps:

```bash
$ PATH=../components/prpc:$PATH protoc --python_out=. --prpc-python_out=. *.proto
```
