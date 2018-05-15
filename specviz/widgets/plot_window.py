import os
import numpy as np
import pyqtgraph as pg
import qtawesome as qta

from qtpy.QtWidgets import QMainWindow, QMdiSubWindow, QListWidget, QAction
from qtpy.uic import loadUi

from ..utils import UI_PATH


class PlotWindow(QMdiSubWindow):
    def __init__(self, *args, **kwargs):
        super(PlotWindow, self).__init__(*args, **kwargs)

        self._main_window = QMainWindow()
        loadUi(os.path.join(UI_PATH, "plot_window.ui"), self._main_window)

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.plot(x=np.arange(10), y=np.random.sample(10))

        self._main_window.setCentralWidget(self._plot_widget)

        self.setWidget(self._main_window)

        self._action = QAction(
                qta.icon('fa.music',
                         active='fa.legal',
                         color='blue',
                         color_active='orange'),
                'Styling')
        self._main_window.tool_bar.addAction(self._action)
