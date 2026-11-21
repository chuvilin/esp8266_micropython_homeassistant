# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# A simple test module to verify that custom Python files are successfully
# frozen into the MicroPython firmware.

def hello():
    """Returns a greeting string to confirm the module is loaded correctly."""
    return "Hello from frozen module!"

VERSION = "1.0.0"
