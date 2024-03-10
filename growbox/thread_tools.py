import sys

from PyQt6.QtCore import QRunnable, pyqtSlot, QObject, pyqtSignal, QThreadPool


class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    print_to_log = pyqtSignal(object)
    callback_write = pyqtSignal(object)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            # traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value))#, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done


class SerialWorkersManager:
    def __init__(self, print_to_log, callback_write):
        self.workers = []
        self.is_started = False
        self.threadpool = QThreadPool()
        self.print_to_log = print_to_log
        self.callback_write = callback_write
        self.current_worker = None

    def run_next_worker(self, any_data, result_func):
        try:
            if result_func:
                result_func(any_data)
        except Exception as err:
            print(err)

        if self.workers:
            worker = self.workers.pop(0)
            self.threadpool.start(worker)
            self.current_worker = worker
        else:
            self.current_worker = None
            self.is_started = False

    def add_and_start_worker(self, result_func, task_func, *args, **kwargs):
        worker = Worker(task_func, *args, **kwargs)
        worker.signals.result.connect(lambda any_data: self.run_next_worker(any_data, result_func))
        worker.signals.print_to_log.connect(self.print_to_log)
        worker.signals.callback_write.connect(self.callback_write)
        if self.is_started:
            self.workers.append(worker)
        else:
            self.threadpool.start(worker)
            self.current_worker = worker
            self.is_started = True

        return worker
