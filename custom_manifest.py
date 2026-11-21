# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

# Critical system modules for ESP8266 boot and filesystem initialization.
freeze("$(PORT_DIR)/modules", "_boot.py", opt=2)
freeze("$(PORT_DIR)/modules", "flashbdev.py", opt=2)
freeze("$(PORT_DIR)/modules", "inisetup.py", opt=2)

# Optional: WebREPL (uncomment to enable, requires more flash space)
# require("webrepl")

# Freeze all custom .py files from our local 'custom_modules' directory
freeze("custom_modules", opt=2)
