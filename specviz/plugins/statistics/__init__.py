import os

from ...core.plugin import Plugin
from qtpy.uic import loadUi
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QWidget


class Statistics(QWidget, Plugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        loadUi(os.path.abspath(
            os.path.join(os.path.dirname(__file__),
                         ".", "statistics.ui")), self)

    @Plugin.plugin_bar("Statistics", icon=QIcon(":/icons/012-file.svg"))
    def on_action_triggered(self):
        self.workspace.plugin_dock.setWidget(self)
