from .operation_handler import SpectralOperationHandler
import numpy as np
import logging
from qtpy.QtWidgets import QMessageBox
from astropy.modeling.fitting import LevMarLSQFitter
from ...core.operations import FunctionalOperation
from .threads import OperationThread


__all__ = ['simple_linemap', 'fitted_linemap', 'fit_spaxels',
           'spectral_smoothing']


def simple_linemap(viewer):
    def threadable_function(data, tracker, mask):
        out = np.empty(shape=data.shape[1:])

        for x in range(data.shape[1]):
            for y in range(data.shape[2]):
                out[x, y] = np.sum(data[:, x, y][mask])
                tracker()

        return out, data.meta.get('unit')

    data = viewer.layers[0].state.layer
    component_id = viewer.layers[0].state.attribute
    mask = viewer.hub.region_mask

    spectral_operation = SpectralOperationHandler(
        data=data,
        function=lambda *args: threadable_function(*args, mask=mask),
        operation_name="Simple Linemap",
        component_id=component_id,
        layout=viewer._layout,
        ui_settings={
            'title': "Simple Linemap",
            'group_box_title': "Choose the component to use for linemap "
                                "generation",
            'description': "Sums the values of the chosen component in the "
                            "range of the current ROI in the spectral view "
                            "for each spectrum in the data cube."},
        parent=viewer)

    spectral_operation.exec_()


def fitted_linemap(viewer):
    # Check to see if the model fitting plugin is loaded
    model_editor_plugin = viewer.current_workspace._plugin_bars.get("Model Editor")

    if model_editor_plugin is None:
        logging.error("Model editor plugin is not loaded.")
        return

    if (model_editor_plugin.model_tree_view.model() is None or
            model_editor_plugin.model_tree_view.model().evaluate() is None):
        QMessageBox.warning(viewer,
                            "No evaluable model.",
                            "There is currently no model or the created "
                            "model is empty. Unable to perform fitted "
                            "linemap operation.")
        return

    def threadable_function(data, tracker, spectral_axis, mask, model):
        out = np.empty(shape=data.shape[1:])
        fitter = LevMarLSQFitter()

        for x in range(data.shape[1]):
            for y in range(data.shape[2]):
                flux = data[:, x, y].value

                fit_model = LevMarLSQFitter()(model,
                                   spectral_axis[mask],
                                   flux[mask])

                new_data = fit_model(spectral_axis)

                out[x, y] = np.sum(new_data[mask])

                tracker()

        return out, data.meta.get('unit')

    data = viewer.layers[0].state.layer
    component_id = viewer.layers[0].state.attribute
    mask = viewer.hub.region_mask
    spectral_axis = viewer.hub.plot_item.spectral_axis
    model = model_editor_plugin.model_tree_view.model().evaluate()

    spectral_operation = SpectralOperationHandler(
        data=data,
        function=lambda *args: threadable_function(
            *args, spectral_axis=spectral_axis, mask=mask, model=model),
        operation_name="Fitted Linemap",
        component_id=component_id,
        layout=viewer._layout,
        ui_settings={
            'title': "Fitted Linemap",
            'group_box_title': "Choose the component to use for linemap "
                                "generation",
            'description': "Fits the current model to the values of the "
                            "chosen component in the range of the current "
                            "ROI in the spectral view for each spectrum in "
                            "the data cube."},
        parent=viewer)

    spectral_operation.exec_()


def fit_spaxels(viewer):
    # Check to see if the model fitting plugin is loaded
    model_editor_plugin = viewer.current_workspace._plugin_bars.get("Model Editor")

    if model_editor_plugin is None:
        logging.error("Model editor plugin is not loaded.")
        return

    if (model_editor_plugin.model_tree_view.model() is None or
            model_editor_plugin.model_tree_view.model().evaluate() is None):
        QMessageBox.warning(viewer,
                            "No evaluable model.",
                            "There is currently no model or the created "
                            "model is empty. Unable to perform fitted "
                            "linemap operation.")
        return

    def threadable_function(data, tracker, spectral_axis, mask, model):
        out = np.empty(shape=data.shape)
        fitter = LevMarLSQFitter()


        for x in range(data.shape[1]):
            for y in range(data.shape[2]):
                flux = data[:, x, y].value

                fit_model = fitter(model,
                                spectral_axis[mask],
                                flux[mask])

                new_data = fit_model(spectral_axis[mask])

                out[:, x, y] = new_data

                if tracker is not None:
                    tracker()

        return out, data.meta.get('unit')

    data = viewer.layers[0].state.layer
    component_id = viewer.layers[0].state.attribute
    model = model_editor_plugin.model_tree_view.model().evaluate()
    mask = viewer.hub.region_mask
    spectral_axis = viewer.hub.plot_item.spectral_axis

    spectral_operation = SpectralOperationHandler(
        data=data,
        function=lambda *args: threadable_function(
            *args, model=model, spectral_axis=spectral_axis, mask=mask),
        operation_name="Fit Spaxels",
        component_id=component_id,
        layout=viewer._layout,
        ui_settings={
            'title': "Fit Spaxel",
            'group_box_title': "Choose the component to use for spaxel "
                                "fitting",
            'description': "Fits the current model to the values of the "
                            "chosen component in the range of the current "
                            "ROI in the spectral view for each spectrum in "
                            "the data cube."})

    spectral_operation.exec_()


def spectral_smoothing(viewer):
    def threadable_function(func, data, tracker, **kwargs):
        out = np.empty(shape=data.shape)

        for x in range(data.shape[1]):
            for y in range(data.shape[2]):
                out[:, x, y] = func(data[:, x, y],
                                    data.spectral_axis)
                tracker()

        return out, data.meta.get('unit')

    stack = FunctionalOperation.operations()[::-1]

    if len(stack) == 0:
        QMessageBox.warning(viewer,
                            "No smoothing in history.",
                            "To apply a smoothing operation to the entire "
                            "cube, first do a local smoothing operation "
                            "(Operations > Smoothing). Once done, the "
                            "operation can then be performed over the "
                            "entire cube.")
        return

    data = viewer.layers[0].state.layer
    component_id = viewer.layers[0].state.attribute

    spectral_operation = SpectralOperationHandler(
        data=data,
        func_proxy=threadable_function,
        stack=stack,
        component_id=component_id,
        layout=viewer._layout,
        ui_settings={
            'title': "Spectral Smoothing",
            'group_box_title': "Choose the component to smooth.",
            'description': "Performs a previous smoothing operation over "
                            "the selected component for the entire cube."})

    spectral_operation.exec_()