import os

from qtpy.QtWidgets import QWidget, QTabBar
from qtpy.uic import loadUi

from ..core.models import DataListModel
from .plot_window import PlotWindow

from ..utils import UI_PATH


class Workspace(QWidget):
    def __init__(self, *args, **kwargs):
        super(Workspace, self).__init__(*args, **kwargs)

        # Load the ui file and attach it to this instance
        loadUi(os.path.join(UI_PATH, "workspace.ui"), self)

        # Define a new data list model for this workspace
        self._model = DataListModel()
        self.list_view.setModel(self._model)

        # Create and define a plot subwindow
        plot_window = PlotWindow()
        plot_window.setWindowTitle("TESTING")
        self.mdi_area.addSubWindow(plot_window)
        plot_window.showMaximized()

        # Don't expand mdiarea tabs
        self.mdi_area.findChild(QTabBar).setExpanding(False)

    @property
    def model(self):
        return self._model

    @property
    def current_window(self):
        return self.mdi_area.currentSubWindow()
