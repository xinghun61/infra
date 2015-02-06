import os as _os

import infra as _infra

# Full real path of the infra.git checkout.
full_infra_path = _os.path.abspath(_os.path.join(
    _os.path.realpath(_infra.__file__), _os.pardir, _os.pardir))
