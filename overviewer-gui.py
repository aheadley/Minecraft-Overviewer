#!/usr/bin/env python

#    This file is part of the Minecraft Overviewer.
#
#    Minecraft Overviewer is free software: you can redistribute it and/or
#    modify it under the terms of the GNU General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or (at
#    your option) any later version.
#
#    Minecraft Overviewer is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
#    Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with the Overviewer.  If not, see <http://www.gnu.org/licenses/>.

import sys
import platform

from PySide.QtCore import *
from PySide.QtGui import *

import multiprocessing

def check_version():
    """Require python >= 2.6 and < 3.0
    """
    if sys.version_info[0] == 2 and sys.version_info[1] < 6:
        #bail
        pass
    elif sys.version_info[0] == 3:
        #bail
        pass

class MainWindow(QMainWindow, Ui_MainWindow):
    """
    """

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        #connect actions to UI stuff

if __name__ == '__main__':
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec_())