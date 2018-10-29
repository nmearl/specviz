import os

import astropy.units as u
from astropy.table import Table
from astropy.nddata import StdDevUncertainty
from specutils import Spectrum1D
from specutils.io.registers import data_loader

__all__ = ['ascii_identify', 'ascii_loader']


def ascii_identify(*args, **kwargs):
    """Check if it's an ASCII file."""
    name = os.path.basename(args[0])

    if name.lower().split('.')[-1] in ['txt', 'ascii']:
       return True

    return False


@data_loader(label="ASCII", identifier=ascii_identify)
def ascii_loader(file_name, **kwargs):
    """
    Load spectrum from ASCII file

    Parameters
    ----------
    file_name: str
        The path to the ASCII file

    Returns
    -------
    data: Spectrum1D
        The data.
    """
    table = Table.read(file_name, format='ascii')

    flux = None
    dispersion = None
    uncertainty = None

    # If there are more than two columns, assume that the first is wavelength,
    # and the second is flux
    if len(table.columns) > 1:
        disp_unit = u.Unit("Angstrom")
        dispersion = table.columns[0] * disp_unit

        unit = u.Unit("Jy")
        flux = table.columns[1] * unit

        # If there are more than two columns, assume the third is uncertainty
        if len(table.columns) >= 2:
            uncertainty = StdDevUncertainty(table.columns[2] * unit)
    # If there is only one column, assume it's just flux.
    elif len(table.columns) == 1:
        unit = u.Unit("Jy")
        flux = table.columns[0] * unit

    return Spectrum1D(flux=flux,
                      spectral_axis=dispersion,
                      meta=table.meta,
                      uncertainty=uncertainty)
