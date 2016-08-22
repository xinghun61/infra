import time


class RpcMethodHandler(object):

  def __init__(self, request_deserializer, response_serializer, unary_unary):
    """An implementation of a single RPC method.

    Args:
      request_deserializer: A callable behavior that accepts a byte string and
        returns an object suitable to be passed to this object's business logic,
        or None to indicate that this object's business logic should be passed
        the raw request bytes.
      response_serializer: A callable behavior that accepts an object produced
        by this object's business logic and returns a byte string, or None to
        indicate that the byte strings produced by this object's business logic
        should be transmitted on the wire as they are.
      unary_unary: This object's application-specific business logic as
        a callable value that takes a request value and a ServicerContext object
        and returns a response value.
    """
    self.handler = unary_unary
    # These are haxx. Because gRPC only accepts binary protos as the wire
    # format, it makes the optimization of just passing around the serializer
    # and deserializer functions. However, because pRPC supports text and json
    # as well as binary, we need access to the actual request and response
    # message classes as well.
    # It turns out that the request_deserializer is just a function closure
    # with the message class it is constructing as the only local symbol being
    # closed over. We access the request class by diving into the closure cell
    # itself. In contrast, the response_serializer is an unbound method on
    # the response message class. We access the response class via the im_class
    # attribute which is set on all unbound instance methods.
    self.request_message = request_deserializer.__closure__[0].cell_contents
    self.response_message = response_serializer.im_class


class GenericRpcHandler(object):
  """An implementation of arbitrarily many RPC methods."""

  def __init__(self, service_name, method_handlers):
    """Create a new GenericRpcHandler which handles many methods in one service.

    Args:
      service_name: a string of the form 'package.subpackage.Service'
      method_handlers: a dictionary of the form {'MethodName': RpcMethodHandler}
    """
    self.service_name = service_name
    self.method_handlers = method_handlers

  def service(self, handler_call_details):
    """Services an RPC (or not).

    Args:
      handler_call_details: A HandlerCallDetails describing the RPC.

    Returns:
      An RpcMethodHandler with which the RPC may be serviced, or None to
        indicate that this object will not be servicing the RPC.
    """
    return self.method_handlers.get(handler_call_details.method)


class HandlerCallDetails(object):

  def __init__(self, method, invocation_metadata):
    """Describes an RPC that has just arrived for service.

    Attributes:
      method: The method name of the RPC.
      invocation_metadata: The metadata from the invocation side of the RPC.
    """
    self.method = method
    self.invocation_metadata = invocation_metadata


class ServicerContext(object):
  """A context object passed to method implementations."""

  def __init__(self):
    self._start_time = time.time()
    self.timeout = None
    self.active = True
    self.code = None
    self.details = None
    self.invocation_metadata = {}

  def time_remaining(self):
    """Describes the length of allowed time remaining for the RPC.

    Returns:
      A nonnegative float indicating the length of allowed time in seconds
      remaining for the RPC to complete before it is considered to have timed
      out, or None if no deadline was specified for the RPC.
    """
    if self._timeout is None:
      return None
    now = time.time()
    return max(0, self._start_time + self._timeout - now)

  def cancel(self):
    """Cancels the RPC.

    Idempotent and has no effect if the RPC has already terminated.
    """
    self.active = False

  def set_code(self, code):
    """Accepts the status code of the RPC.

    This method need not be called by method implementations if they wish the
    gRPC runtime to determine the status code of the RPC.

    Args:
      code: The integer status code of the RPC to be transmitted to the
        invocation side of the RPC.
    """
    self.code = code

  def set_details(self, details):
    """Accepts the service-side details of the RPC.

    This method need not be called by method implementations if they have no
    details to transmit.

    Args:
      details: The details string of the RPC to be transmitted to
        the invocation side of the RPC.
    """
    self.details = details
