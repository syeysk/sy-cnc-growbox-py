from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QDialogButtonBox, QSlider, QSpinBox, QListWidget, QListWidgetItem, QHBoxLayout, QLabel,
)


class SetValueIntegerDialog(QDialog):
    def event_set_value_from_input(self, checked):
        self.value = self.input.value()
        self.slider.setValue(self.value)

    def event_set_value_from_slider(self, checked=None):
        self.value = self.slider.value()
        self.input.setValue(self.value)

    def __init__(self, parent=None, text='', value=0, maximum=255):
        super().__init__(parent)
        self.setWindowTitle(text)
        self.value = value

        buttons = QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel
        button_box = QDialogButtonBox(buttons)
        button_box.clicked.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, maximum)
        self.slider.sliderMoved.connect(self.event_set_value_from_slider)
        self.slider.sliderReleased.connect(self.event_set_value_from_slider)
        self.slider.valueChanged.connect(self.event_set_value_from_slider)
        layout.addWidget(self.slider)

        self.input = QSpinBox()
        self.input.setRange(0, maximum)
        self.input.valueChanged.connect(self.event_set_value_from_input)
        self.input.setValue(value)

        layout.addWidget(self.input)
        layout.addWidget(button_box)
        self.setLayout(layout)


class SetValueListDialog(QDialog):
    def event_set_value_from_input(self, _):
        current_item = self.input.currentItem()
        self.value = current_item.data(Qt.ItemDataRole.UserRole)

    def __init__(self, parent=None, text='', value=None, values=None):
        super().__init__(parent)
        self.setWindowTitle(text)
        self.value = value
        values = {} if not values else values

        buttons = QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel
        button_box = QDialogButtonBox(buttons)
        button_box.clicked.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()

        self.input = QListWidget()
        for item_value, item_name in values.items():
            widget_item = QListWidgetItem(item_name, self.input)
            widget_item.setData(Qt.ItemDataRole.UserRole, item_value)
            if self.value == item_value:
                widget_item.setSelected(True)

        self.input.itemClicked.connect(self.event_set_value_from_input)
        layout.addWidget(self.input)
        layout.addWidget(button_box)
        self.setLayout(layout)


class SetValueTimeDialog(QDialog):
    def event_set_value(self, _):
        self.hours = self.field_hours.value()
        self.minutes = self.field_minutes.value()
        self.value = self.hours * 60 + self.minutes

    def __init__(self, parent=None, text='', value=0):
        super().__init__(parent)
        self.setWindowTitle(text)
        self.value = value
        self.hours = value // 60
        self.minutes = value % 60

        self.field_hours = QSpinBox()
        self.field_hours.setRange(0, 23)
        self.field_minutes = QSpinBox()
        self.field_minutes.setRange(0, 59)

        self.field_hours.setValue(self.hours)
        self.field_minutes.setValue(self.minutes)

        buttons = QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel
        button_box = QDialogButtonBox(buttons)
        button_box.clicked.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()

        layout_time = QHBoxLayout()
        layout_time.addWidget(QLabel('Часы:'))
        layout_time.addWidget(self.field_hours)
        layout_time.addWidget(QLabel('Минуты:'))
        layout_time.addWidget(self.field_minutes)

        self.field_hours.valueChanged.connect(self.event_set_value)
        self.field_minutes.valueChanged.connect(self.event_set_value)
        layout.addLayout(layout_time)
        layout.addWidget(button_box)
        self.setLayout(layout)
