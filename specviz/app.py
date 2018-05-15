import sys

from qtpy.QtWidgets import QApplication

from cosmoscope.core.server import launch as server_launch

from .client import launch as client_launch
from .widgets.main_window import MainWindow


def start(server_ip=None, client_ip=None):
    # Start the server connections
    server_launch(server_ip=server_ip,
                  client_ip=client_ip)

    # Start the client connection
    client_launch(server_ip=server_ip,
                  client_ip=client_ip)

    # Start the application
    app = QApplication(sys.argv)

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    start()
