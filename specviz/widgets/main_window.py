import os

from qtpy.QtWidgets import QMainWindow
from qtpy.uic import loadUi

from .workspace import Workspace
from ..utils import UI_PATH
from . import resources

__all__ = ['MainWindow']


class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        # Load the ui file and attached it to this instance
        loadUi(os.path.join(UI_PATH, "main_window.ui"), self)

        # Set the tabs to be expanding; os-specific
        self.tab_widget.tabBar().setExpanding(True)

        # Create a button on the tab widget
        # icon = qta.icon('fa.music',
        #                 active='fa.legal',
        #                 color='blue',
        #                 color_active='orange')
        # add_button = QToolButton()
        # add_button.setIcon(icon)
        # self.tab_widget.setCornerWidget(add_button)

        # Create the tab item model
        # self._data_item_model = DataListModel()

        # test_button = QPushButton()
        # self.list_view.setIndexWidget(self._data_item_model.createIndex(0, 1), test_button)

        # Set delegates
        # self.list_view.setItemDelegate(DataItemDelegate())
        # self.list_view.setModel(self._data_item_model)

        # Add some new data

        # Setup connections
        self.setup_connections()

        # Create a default workspace
        self.new_workspace()

    def setup_connections(self):
        # Close tab when request
        self.tab_widget.tabCloseRequested.connect(self.tab_widget.removeTab)

        # Update the title bar based on the current workspace

        # When new workspace button clicked, add new tab
        self.new_action.triggered.connect(self.new_workspace)

        # When a new workspace tab is selected, change the application title
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index):
        self.tab_widget.setCurrentIndex(index)

        # Change the application title to reflect current workspace
        if self.tab_widget.count() == 0:
            self.setWindowTitle("SpecViz")
        else:
            self.setWindowTitle(self.tab_widget.tabText(index) + " — SpecViz")

    def new_workspace(self):
        # Get count of current untitled workspaces
        count = len([i for i in range(self.tab_widget.count())
                     if "Untitled Workspace" in self.tab_widget.tabText(i)])
        title = "Untitled Workspace {}".format(count) if count > 0 else "Untitled Workspace"

        # Instantiate and set workspace tab
        workspace = Workspace(self)
        self.tab_widget.addTab(workspace, title)
