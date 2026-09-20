"""Single-flight background reads with GUI-thread delivery."""

import threading

from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal, pyqtSlot

from app.services.server_client import get_server_session


class BackgroundRead(QObject):
    busyChanged = pyqtSignal()
    finished = pyqtSignal(object, object, object)

    def __init__(self, parent, apply, report):
        super().__init__(parent)
        self._apply = apply
        self._report = report
        self._running = False
        self._pending = None
        self.finished.connect(self._finish)

    @pyqtProperty(bool, notify=busyChanged)
    def busy(self):
        return self._running

    def submit(self, fetch):
        if self._running:
            self._pending = fetch
            return
        session = get_server_session()
        self._running = True
        self.busyChanged.emit()

        def worker():
            try:
                result, error = fetch(session), None
            except Exception as exc:
                result, error = None, str(exc)
            self.finished.emit(session, result, error)

        threading.Thread(target=worker, daemon=True, name="workspace-read").start()

    @pyqtSlot(object, object, object)
    def _finish(self, session, result, error):
        self._running = False
        self.busyChanged.emit()
        pending, self._pending = self._pending, None
        if session == get_server_session():
            if error is not None:
                self._report(error)
            else:
                self._apply(result)
        if pending is not None:
            self.submit(pending)
