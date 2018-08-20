# -*- coding: UTF-8 -*-
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

STATUS = "not loaded"
try:
    import objgraph

    OBJGRAPH_EXTENSION_ENABLED = True
    STATUS = "objgraph available"
except ImportError:
    OBJGRAPH_EXTENSION_ENABLED = False
    STATUS = "objgraph not installed"

ENABLED = OBJGRAPH_EXTENSION_ENABLED # fuglu compatibility

# objgraph can be very useful detecting memory leaks
