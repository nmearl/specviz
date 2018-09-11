import os

from ...core.plugin import Plugin
from qtpy.uic import loadUi
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QWidget

import qtawesome as qta


class ModelEditor(QWidget, Plugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        loadUi(os.path.abspath(
            os.path.join(os.path.dirname(__file__),
                         ".", "model_editor.ui")), self)

        self.add_model_button.setIcon(qta.icon('fa.plus'))
        self.remove_model_button.setIcon(qta.icon('fa.minus'))

        # Model editing
        from ...core.models import ModelFittingModel, ModelFittingProxyModel

        model_fitting_model = ModelFittingModel()
        model_fitting_proxy_model = ModelFittingProxyModel()
        model_fitting_proxy_model.setSourceModel(model_fitting_model)

        self.model_tree_view.setModel(model_fitting_proxy_model)
        self.model_tree_view.setHeaderHidden(True)
        self.parameter_tree_view.setModel(model_fitting_model)

        def _set_root(idx):
            src_idx = model_fitting_proxy_model.mapToSource(idx)
            idx = src_idx.siblingAtColumn(1)
            self.parameter_tree_view.setRootIndex(idx)

        self.model_tree_view.selectionModel().currentChanged.connect(_set_root)

    @Plugin.plugin_bar("Model Editor", icon=QIcon(":/icons/012-file.svg"))
    def on_action_triggered(self):
        self.workspace.plugin_dock.setWidget(self)
