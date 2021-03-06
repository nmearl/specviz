import logging
import os
import pickle
import uuid

import numpy as np
from astropy.modeling import fitting, models, optimizers
from qtpy.QtCore import QSortFilterProxyModel, QThread, Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (QAction, QDialog, QFileDialog, QInputDialog, QMenu,
                            QMessageBox, QToolButton, QWidget)
from qtpy.uic import loadUi
from specutils.fitting import fit_lines
from specutils.spectra import Spectrum1D
from specutils.utils import QuantityModel

from .equation_editor_dialog import ModelEquationEditorDialog
from .initializers import initialize
from .items import ModelDataItem
from .models import ModelFittingModel
from ...core.plugin import plugin

MODELS = {
    'Const1D': models.Const1D,
    'Linear1D': models.Linear1D,
    'Polynomial1D': models.Polynomial1D,
    'Gaussian1D': models.Gaussian1D,
    'Voigt1D': models.Voigt1D,
    'Lorentzian1D': models.Lorentz1D,
}

FITTERS = {
    'Levenberg-Marquardt': fitting.LevMarLSQFitter,
    'Simplex Least Squares': fitting.SimplexLSQFitter,
    # Disabled # 'SLSQP Optimization': fitting.SLSQPLSQFitter,
}

SPECVIZ_MODEL_FILE_FILTER = 'Specviz Model Files (*.smf)'


@plugin.plugin_bar("Model Editor", icon=QIcon(":/icons/new-model.svg"))
class ModelEditor(QWidget):
    """
    Qt widget for interacting with the model editor functionality in SpecViz.
    This class is responsible for populating the values and handling user
    interactions such as adding/removing models, accessing the arithmetic
    editor and allows for parameter editing.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fitting_options = {
            'fitter': 'Levenberg-Marquardt',
            'displayed_digits': 5,
            'max_iterations': optimizers.DEFAULT_MAXITER,
            'relative_error': optimizers.DEFAULT_ACC,
            'epsilon': optimizers.DEFAULT_EPS,
        }

        self._init_ui()

    def _init_ui(self):
        loadUi(os.path.abspath(
            os.path.join(os.path.dirname(__file__),
                         ".", "model_editor.ui")), self)

        # Populate the add mode button with a dropdown containing available
        # fittable model objects
        self.add_model_button.setPopupMode(QToolButton.InstantPopup)
        models_menu = QMenu(self.add_model_button)
        self.add_model_button.setMenu(models_menu)

        for k, v in MODELS.items():
            action = QAction(k, models_menu)
            action.triggered.connect(lambda x, m=v: self._add_fittable_model(m))
            models_menu.addAction(action)

        self.fit_model_thread = None

        # Initially hide the model editor tools until user has selected an
        # editable model spectrum object
        self.editor_holder_widget.setHidden(True)
        self.setup_holder_widget.setHidden(False)

        self.equation_edit_button.clicked.connect(
            self._on_equation_edit_button_clicked)
        self.new_model_button.clicked.connect(self._on_create_new_model)
        self.remove_model_button.clicked.connect(self._on_remove_model)

        self.advanced_settings_button.clicked.connect(
            lambda: ModelAdvancedSettingsDialog(self, self).exec())

        self.save_model_button.clicked.connect(self._on_save_model)
        self.load_model_button.clicked.connect(self._on_load_from_file)

        self._data_item_proxy_model = DataItemProxyModel()
        self._data_item_proxy_model.setSourceModel(self.hub.model)
        self.data_selection_combo.setModel(self._data_item_proxy_model)
        self.data_selection_combo.currentIndexChanged.connect(self._redraw_model)

        # When a plot data item is select, get its model editor model
        # representation
        self.hub.workspace.current_selected_changed.connect(
            self._on_plot_item_selected)

        # When the plot window changes, reset model editor
        self.hub.workspace.mdi_area.subWindowActivated.connect(self._on_new_plot_activated)

        # Listen for when data items are added to internal model
        self.hub.model.data_added.connect(self._on_data_item_added)

        # Connect the fit model button
        self.fit_button.clicked.connect(self._on_fit_clicked)

    @plugin.tool_bar(name="New Model", icon=QIcon(":/icons/new-model.svg"))
    def on_new_model_triggered(self):
        """
        Create a new model based on user choice and add it to the display of
        models in the editor.
        """
        self._on_create_new_model()

    def _on_data_item_added(self, data_item):
        if not isinstance(data_item, ModelDataItem):
            return

        model_data_item = data_item
        plot_data_item = self.hub.plot_data_item_from_data_item(model_data_item)

        # Connect data change signals so that the plot updates when the user
        # changes a parameter in the model view model
        model_data_item.model_editor_model.itemChanged.connect(
            lambda item: self._on_model_item_changed(item))

        # plot_data_item = self.hub.workspace.proxy_model.item_from_id(model_data_item.identifier)
        plot_data_item.visible = True

        self.hub.workspace.current_plot_window.plot_widget.on_item_changed(
            model_data_item)
        self.hub.workspace._on_item_changed(item=plot_data_item.data_item)

    def _on_create_new_model(self):
        if self.hub.data_item is None:
            QMessageBox.warning(self,
                                "No item selected, cannot create model.",
                                "There is currently no item selected. Please "
                                "select an item before attempting to create "
                                "a new model.")
            return

        # Grab the currently selected plot data item
        new_spec = Spectrum1D(flux=np.zeros(self.hub.data_item.spectral_axis.size) * self.hub.data_item.flux.unit,
                              spectral_axis=self.hub.data_item.spectral_axis)

        self.create_model_data_item(new_spec, data_item=self.hub.data_item)

    def create_model_data_item(self, spectrum, name=None, data_item=None):
        """
        Generate a new model data item to be added to the data list.

        Parameters
        ----------
        spectrum : :class:`~specutils.Spectrum1D`
            The spectrum holding the spectral data.
        """
        # Set the currently displayed plugin panel widget to the model editor
        self.hub.set_active_plugin_bar(name="Model Editor")

        model_data_item = ModelDataItem(model=ModelFittingModel(),
                                        name=name or "Fittable Model Spectrum",
                                        identifier=uuid.uuid4(),
                                        data=spectrum)
        model_data_item._selected_data = data_item

        self.hub.append_data_item(model_data_item)

        if model_data_item._selected_data is not None:
            index = self.data_selection_combo.findData(model_data_item._selected_data)
            if index != -1:
                self.data_selection_combo.setCurrentIndex(index)

    def _on_remove_model(self):
        """Remove an astropy model from the model editor tree view."""
        indexes = self.model_tree_view.selectionModel().selectedIndexes()

        if len(indexes) > 0:
            selected_idx = indexes[0]
            self.model_tree_view.model().remove_model(row=selected_idx.row())

            # If removing the model resulted in an invalid arithmetic equation,
            # force open the arithmetic editor so the user can fix it.
            if len(self.model_tree_view.model().items) > 0 and \
                self.model_tree_view.model().equation and \
                self.model_tree_view.model().evaluate() is None:
                self._on_equation_edit_button_clicked()

            # # Re-evaluation model
            self.hub.plot_item.set_data()

    def _save_models(self, filename):
        model_editor_model = self.hub.plot_item.data_item.model_editor_model
        models = model_editor_model.fittable_models

        with open(filename, 'wb') as handle:
            pickle.dump(models, handle)

    def _on_save_model(self, interactive=True):
        model_editor_model = self.hub.data_item.model_editor_model
        # There are no models to save
        if not model_editor_model.fittable_models:
            QMessageBox.warning(self,
                                'No model available',
                                'No model exists to be saved.')
            return

        default_name = os.path.join(os.path.curdir, 'new_model.smf')
        outfile = QFileDialog.getSaveFileName(
            self, caption='Save Model', directory=default_name,
            filter=SPECVIZ_MODEL_FILE_FILTER)[0]
        # No file was selected; the user hit "Cancel"
        if not outfile:
            return

        self._save_models(outfile)

        QMessageBox.information(self,
                                'Model saved',
                                'Model successfully saved to {}'.format(outfile))

    def _load_model_from_file(self, filename):
        with open(filename, 'rb') as handle:
            loaded_models = pickle.load(handle)

        for _, model in loaded_models.items():
            self._add_model(model)

    def _on_load_from_file(self):
        filename = QFileDialog.getOpenFileName(
            self, caption='Load Model',
            filter=SPECVIZ_MODEL_FILE_FILTER)[0]
        if not filename:
            return

        self._load_model_from_file(filename)

    def _add_model(self, model):
        idx = self.model_tree_view.model().add_model(model)
        self.model_tree_view.setExpanded(idx, True)

        for i in range(0, 4):
            self.model_tree_view.resizeColumnToContents(i)

        self._redraw_model()

    def _add_fittable_model(self, model_type):
        if issubclass(model_type, models.Polynomial1D):
            text, ok = QInputDialog.getInt(self, 'Polynomial1D',
                                           'Enter Polynomial1D degree:')
            # User decided not to create a model after all
            if not ok:
                return

            model = model_type(int(text))
        else:
            model = model_type()

        # Grab any user-defined regions so we may initialize parameters only
        # for the selected data.
        mask = self.hub.region_mask
        spec = self._get_selected_plot_data_item().data_item.spectrum

        # Initialize the parameters
        model = initialize(model, spec.spectral_axis[mask], spec.flux[mask])

        self._add_model(model)

    def _update_model_data_item(self):
        """
        When a new data item is selected, check if
        the model's plot_data_item units are compatible
        with the target data item's plot_data_item units.
        If the units are not the same, update the model's units.
        """
        # Note
        # ----
        # Target data items that cannot be plotted are not
        # selectable in the data selection combo. The only instance
        # a unit change is needed is when noting is plotted and the
        # user changes the target data.

        # Get the current plot item and update
        # its data item if its a model plot item
        model_plot_data_item = self.hub.plot_item

        if model_plot_data_item is not None and \
                isinstance(model_plot_data_item.data_item, ModelDataItem):
            # This is the data item selected in the
            # model editor data selection combo box
            data_item = self._get_selected_data_item()

            if data_item is not None and \
                    isinstance(data_item.spectrum, Spectrum1D):

                selected_plot_data_item = self.hub.plot_data_item_from_data_item(data_item)

                new_spectral_axis_unit = selected_plot_data_item.spectral_axis_unit
                new_data_unit = selected_plot_data_item.data_unit

                compatible = model_plot_data_item.are_units_compatible(
                    new_spectral_axis_unit,
                    new_data_unit,
                )
                if not compatible:
                    # If not compatible, update the units of every
                    # model plot_data_item unit to match the selected
                    # data's plot_data_item units in every plot sub-window
                    model_identifier = model_plot_data_item.data_item.identifier
                    selection_identifier = selected_plot_data_item.data_item.identifier
                    for sub_window in self.hub.workspace.mdi_area.subWindowList():
                        proxy_model = sub_window.proxy_model

                        # Get plot_data_items in that sub_window
                        model_p_d_i = proxy_model.item_from_id(model_identifier)
                        selected_p_d_i = proxy_model.item_from_id(selection_identifier)

                        # Update model's plot_data_item units
                        model_p_d_i._spectral_axis_unit = selected_p_d_i.spectral_axis_unit
                        model_p_d_i._data_unit = selected_p_d_i.data_unit
                        sub_window.plot_widget.check_plot_compatibility()

                # Copy the spectrum and assign the current
                # fittable model the spectrum with the
                # spectral axis and flux converted to plot units.
                spectrum = data_item.spectrum.with_spectral_unit(new_spectral_axis_unit)
                spectrum = spectrum.new_flux_unit(new_data_unit)
                model_plot_data_item.data_item.set_data(spectrum)
                model_plot_data_item.data_item._selected_data = data_item

    def _redraw_model(self):
        """
        Re-plot the current model item.
        """
        model_plot_data_item = self.hub.plot_item

        if model_plot_data_item is not None and \
                isinstance(model_plot_data_item.data_item, ModelDataItem):
            self._update_model_data_item()
            model_plot_data_item.set_data()

    def _on_model_item_changed(self, item):
        if item.parent():
            # If the item has a parent, then we know that the parameter
            # value has changed. Note that the internal stored data has not
            # been truncated at all, only the displayed text value. All fitting
            # uses the full, un-truncated data value.
            if item.column() == 1:
                item.setData(float(item.text()), Qt.UserRole + 1)
                item.setText(item.text())
            self._redraw_model()
        else:
            # In this case, the user has renamed a model. Since the equation
            # editor now doesn't know about the old model, reset the equation
            self.hub.data_item.model_editor_model.reset_equation()

    def _on_equation_edit_button_clicked(self):
        # Get the current model
        model_data_item = self.hub.data_item

        if not isinstance(model_data_item, ModelDataItem):
            QMessageBox.warning(self,
                                "No model available.",
                                "The currently selected item does not"
                                " contain a fittable model. Create a new"
                                " one, or select an item containing a model.")
            return

        equation_editor_dialog = ModelEquationEditorDialog(
            model_data_item.model_editor_model)
        equation_editor_dialog.accepted.connect(self.hub.plot_item.set_data)
        equation_editor_dialog.exec_()

    def _clear_tree_view(self):
        self.model_tree_view.setModel(None)
        self.editor_holder_widget.setHidden(True)
        self.setup_holder_widget.setHidden(False)

    def _on_new_plot_activated(self):
        plot_data_item = self.hub.plot_item
        if plot_data_item is not None:
            if isinstance(plot_data_item.data_item, ModelDataItem):
                return self._on_plot_item_selected(plot_data_item)
        self._clear_tree_view()

    def _on_plot_item_selected(self, plot_data_item):
        if not isinstance(plot_data_item.data_item, ModelDataItem):
            return self._clear_tree_view()

        self.editor_holder_widget.setHidden(False)
        self.setup_holder_widget.setHidden(True)

        model_data_item = plot_data_item.data_item

        # Set the model on the tree view and expand all children initially.
        self.model_tree_view.setModel(model_data_item.model_editor_model)
        self.model_tree_view.expandAll()
        if model_data_item._selected_data is not None:
            index = self.data_selection_combo.findData(model_data_item._selected_data)
            if index != -1:
                self.data_selection_combo.setCurrentIndex(index)

        for i in range(0, 4):
            self.model_tree_view.resizeColumnToContents(i)

    def _get_selected_plot_data_item(self):
        workspace = self.hub.workspace

        if self.hub.proxy_model is None:
            raise Exception("Workspace proxy_model is None")

        row = self.data_selection_combo.currentIndex()
        idx = workspace.list_view.model().index(row, 0)

        return self.hub.proxy_model.data(idx, role=Qt.UserRole)

    def _get_selected_data_item(self):
        # The spectrum_data_item would be the data item that this model is to
        # be fit to. This selection is done via the data_selection_combo.
        combo_index = self.data_selection_combo.currentIndex()
        data_item = self.data_selection_combo.itemData(combo_index)

        # If user chooses a model instead of a data item, notify and return
        if isinstance(data_item, ModelDataItem):
            QMessageBox.warning(self,
                                "Selected data is a model.",
                                "The currently selected data "
                                "is a model. Please select a "
                                "data item containing spectra.")
            return None
        return data_item

    def _on_fit_clicked(self, eq_pop_up=True):
        if eq_pop_up:
            self._on_equation_edit_button_clicked()

        # Grab the currently selected plot data item from the data list
        plot_data_item = self.hub.plot_item

        # If this item is not a model data item, bail
        if not isinstance(plot_data_item.data_item, ModelDataItem):
            return

        data_item = self._get_selected_data_item()

        if data_item is None:
            return

        spectral_region = self.hub.spectral_regions

        # Compose the compound model from the model editor sub model tree view
        model_editor_model = plot_data_item.data_item.model_editor_model
        result = model_editor_model.evaluate()

        if result is None:
            QMessageBox.warning(self,
                                "Please add models to fit.",
                                "Models can be added by clicking the"
                                " green \"add\" button and selecting a"
                                " model from the drop-down menu")
            return

        # Load options
        fitter = FITTERS[self.fitting_options["fitter"]]
        output_formatter = "{:0.%sg}" % self.fitting_options['displayed_digits']

        kwargs = {}
        if isinstance(fitter, fitting.LevMarLSQFitter):
            kwargs['maxiter'] = self.fitting_options['max_iterations']
            kwargs['acc'] = self.fitting_options['relative_error']
            kwargs['epsilon'] = self.fitting_options['epsilon']

        # Run the compound model through the specutils fitting routine. Ensure
        # that the returned values are always in units of the current plot by
        # passing in the spectrum with the spectral axis and flux
        # converted to plot units.
        spectrum = data_item.spectrum.with_spectral_unit(
            plot_data_item.spectral_axis_unit)
        spectrum = spectrum.new_flux_unit(plot_data_item.data_unit)

        # Setup the thread and begin execution.
        self.fit_model_thread = FitModelThread(
            spectrum=spectrum,
            model=result,
            fitter=fitter(),
            fitter_kwargs=kwargs,
            window=spectral_region)
        self.fit_model_thread.result.connect(
            lambda x, r=result: self._on_fit_model_finished(x, result=r))
        self.fit_model_thread.start()

    def _on_fit_model_finished(self, fit_mod, result=None):
        if fit_mod is None or result is None:
            logging.error("Fitted model result is `None`.")
            return

        plot_data_item = self.hub.plot_item
        model_editor_model = plot_data_item.data_item.model_editor_model

        model_editor_model.clear()
        model_editor_model.reset_equation()

        if result.n_submodels() > 1:
            if isinstance(fit_mod, QuantityModel):
                sub_mods = [x for x in fit_mod.unitless_model]
            else:
                sub_mods = [x for x in fit_mod]

            for i, x in enumerate(result):
                sub_mods[i].name = x.name
        else:
            fit_mod.name = result.name
            sub_mods = [fit_mod]

        for mod in sub_mods:
            self._add_model(mod)

        for i in range(0, 4):
            self.model_tree_view.resizeColumnToContents(i)

        # Update the displayed data on the plot
        self._redraw_model()


class ModelAdvancedSettingsDialog(QDialog):
    """
    Dialog to display an interface for editing the fitting performed when the
    user attempts to fit the model to the selected data.

    Parameters
    ----------
    model_editor : :class:`specviz.plugins.model_editor.ModelEditor`
        The model editor instance to which these fitter settings will apply.
    parent : :class:`qtpy.QtWidgets.QWidget`
        The parent widget this class will be owned by.
    """
    def __init__(self, model_editor, parent=None):
        super().__init__(parent)

        self.model_editor = model_editor
        self._init_ui()

    def _init_ui(self):
        loadUi(os.path.abspath(
            os.path.join(os.path.dirname(__file__), ".",
                         "model_advanced_settings.ui")), self)

        self.fitting_type_combo_box.addItems(list(FITTERS.keys()))

        self.buttonBox.accepted.connect(self.apply_settings)
        self.buttonBox.rejected.connect(self.cancel)

        fitting_options = self.model_editor.fitting_options

        self.displayed_digits_spin_box.setValue(fitting_options['displayed_digits'])
        self.max_iterations_line_edit.setText(str(fitting_options['max_iterations']))
        self.relative_error_line_edit.setText(str(fitting_options['relative_error']))
        self.epsilon_line_edit.setText(str(fitting_options['epsilon']))
        self.fitting_type_combo_box.currentIndexChanged.connect(self._on_index_change)
        index = self.fitting_type_combo_box.findText(fitting_options['fitter'],
                                                     Qt.MatchFixedString)
        if index >= 0:
            self.fitting_type_combo_box.setCurrentIndex(index)

        self._on_index_change()

    def _on_index_change(self, *args):
        fitting_type = self.fitting_type_combo_box.currentText()
        is_lev_mar_lsq = fitting_type == 'Levenberg-Marquardt'
        self.max_iterations_line_edit.setDisabled(not is_lev_mar_lsq)
        self.relative_error_line_edit.setDisabled(not is_lev_mar_lsq)
        self.epsilon_line_edit.setDisabled(not is_lev_mar_lsq)

    def _validate_inputs(self):
        """
        Check if user inputs are valid.
        return
        ------
        success : bool
            True if all input boxes are valid.
        """
        red = "background-color: rgba(255, 0, 0, 128);"
        success = True

        for widget in [self.max_iterations_line_edit]:
            try:
                int(widget.text())
                widget.setStyleSheet("")
            except ValueError:
                widget.setStyleSheet(red)
                success = False

        for widget in [self.relative_error_line_edit,
                       self.epsilon_line_edit]:
            try:
                float(widget.text())
                widget.setStyleSheet("")
            except ValueError:
                widget.setStyleSheet(red)
                success = False

        return success

    def apply_settings(self):
        """
        Validates and applies the user settings for the fitter.
        """
        if not self._validate_inputs():
            return

        fitting_type = self.fitting_type_combo_box.currentText()
        max_iterations = int(self.max_iterations_line_edit.text())
        relative_error = float(self.relative_error_line_edit.text())
        epsilon = float(self.epsilon_line_edit.text())
        displayed_digits = self.displayed_digits_spin_box.value()

        self.model_editor.fitting_options = {
            'fitter': fitting_type,
            'displayed_digits': displayed_digits,
            'max_iterations': max_iterations,
            'relative_error': relative_error,
            'epsilon': epsilon,
        }

        self.close()

    def cancel(self):
        """
        Closes the dialog without apply user settings to the fitter.
        """
        self.close()


class FitModelThread(QThread):
    """
    QThread for running the model fitting operations in a separate thread from
    the GUI.

    Parameters
    ----------
    spectrum : :class:`~specutils.Spectrum1D`
        The spectrum data class to which the model will be fit.
    model : :class:`~astropy.modeling.models.Fittable1DModel`
        The model to be fit to the data.
    fitter : :class:`~astropy.modeling.fitting.Fitter`
        The fitter used in fitting the model to the data.
    window : :class:`~specutils.spectra.spectral_region.SpectralRegion`
        The spectral region class used to excise the particular portion of
        the data used in the model fitting.
    output_formatter : str
        The format of the data to be passed to the method updating
        displayed units in the GUI.
    """
    status = Signal(str, int)
    result = Signal(object)

    def __init__(self, spectrum, model, fitter, fitter_kwargs=None, window=None,
                 parent=None):
        super(FitModelThread, self).__init__(parent)

        self.spectrum = spectrum
        self.model = model
        self.fitter = fitter
        self.fitter_kwargs = fitter_kwargs or {}
        self.window = window

    def run(self):
        """
        Implicitly called when the thread is started. Performs the operation.
        """
        self.status.emit("Fitting model...", 0)

        fit_mod = fit_lines(self.spectrum, self.model, fitter=self.fitter,
                            window=self.window, **self.fitter_kwargs)

        if not self.fitter.fit_info.get('message', ""):
            self.status.emit("Fit completed successfully!", 5000)
        else:
            self.status.emit("Fit completed, but with warnings.", 5000)

        self.result.emit(fit_mod)


class DataItemProxyModel(QSortFilterProxyModel):
    """
    Proxy model to filter out model data items for display in the model editor
    list. Items in the data selection list should only be data items, as model
    data items cannot have new model data items associated with them.
    """
    def filterAcceptsRow(self, source_row, source_parent):
        """
        Filter out model data items in the model rows.
        """
        idx = self.sourceModel().index(source_row, 0, source_parent)
        item = self.sourceModel().itemFromIndex(idx)

        return not isinstance(item, ModelDataItem)
