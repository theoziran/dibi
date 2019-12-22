from typing import List, Tuple, Callable, Dict, Union

from PyQt5.QtWidgets import QTableWidget,\
    QTableWidgetItem,\
    QHBoxLayout,\
    QVBoxLayout,\
    QWidget,\
    QLineEdit,\
    QLabel,\
    QTextEdit, \
    QListView,\
    QMainWindow,\
    QItemDelegate,\
    QSizePolicy,\
    QStackedWidget,\
    QPushButton
from PyQt5.QtCore import pyqtSlot, Qt, QAbstractListModel, QVariant, QEvent, QMargins, QPropertyAnimation, pyqtSignal, QThread, QModelIndex
from PyQt5.QtGui import QGuiApplication, QTextCursor, QPainter

from dibi.configuration import ConnectionInfo
from dibi.waitingspinnerwidget import QtWaitingSpinner


class CellEditorContainer(QWidget):
    objectName = 'cellEditorContainer'

    def __init__(self, parent):
        super().__init__(parent=parent)
        layout = QVBoxLayout()
        self.setStyleSheet('background: #ffffff')
        layout.setContentsMargins(QMargins(0, 0, 0, 0))
        layout.setSpacing(0)
        self.cb = None
        self.cellEditor = CellEditor()
        layout.addWidget(self.cellEditor)

        bottom_layout = QHBoxLayout()

        save = QPushButton("Save")
        save.setObjectName('save-change-btn')
        save.setCursor(Qt.PointingHandCursor)
        self.save = save

        cancel = QPushButton("Cancel")
        cancel.setObjectName('cancel-change-btn')
        cancel.setCursor(Qt.PointingHandCursor)
        self.cancel = cancel

        bottom_layout.addWidget(self.save)
        bottom_layout.addWidget(self.cancel)

        layout.addLayout(bottom_layout)
        self.setLayout(layout)

        self.save.clicked.connect(self.onSaveClick)
        self.cancel.clicked.connect(self.onCancelClick)

    def setText(self, text):
        self.cellEditor.setText(text)

    def onSaveClick(self):
        if self.cb is not None:
            self.cb(self.cellEditor.toPlainText())

    def onCancelClick(self):
        if self.cb is not None:
            self.cb(None)

    def setCallback(self, cb):
        self.cb = cb
        self.cellEditor.setCallback(cb)


class CellEditor(QTextEdit):
    cb = None
    installed = False

    def setCallback(self, cb: Callable) -> None:
        if not self.installed:
            self.installEventFilter(self)
            self.installed = True
        self.cb = cb

    def eventFilter(self, source, event):
        if self.cb is None or event.type() != QEvent.KeyPress:
            return QMainWindow.eventFilter(self, source, event)

        key = event.key()
        modifiers = QGuiApplication.queryKeyboardModifiers()

        if key == Qt.Key_Escape:
            self.cb(None)
            self.cb = None
            return True

        if key == Qt.Key_Return and modifiers == Qt.ControlModifier:
            self.cb(self.toPlainText())
            self.cb = None
            return True
        return QMainWindow.eventFilter(self, source, event)


class ListViewModel(QAbstractListModel):
    def __init__(self, data: List[str], parent: QWidget):
        super().__init__(parent=parent)
        self._data = data

    def rowCount(self, ok):
        return len(self._data)

    def flags(self, _: QModelIndex):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def get(self, index: QModelIndex) -> str:
        return self._data[index.row()]

    def data(self, index: QModelIndex, role: int) -> str:
        if role == Qt.DisplayRole:
            return self._data[index.row()]
        elif role == Qt.EditRole:
            return self._data[index.row()]
        return QVariant()


class ItemDelegate(QItemDelegate):
    pass


class VertLabel(QWidget):
    clicked = pyqtSignal()

    def __init__(self, text):
        super().__init__()
        self.text = text

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(Qt.white)
        painter.translate(10, 10)
        painter.rotate(90)
        painter.drawText(0, 0, self.text)
        painter.end()

    def setText(self, text):
        self.text = text
        self.repaint()

    def mouseReleaseEvent(self, event):
        self.clicked.emit()


class ConnectionButton(QPushButton):
    def __init__(self, label: str, index: int, on_click_cb: Callable):
        super().__init__(label)
        # self.index = index
        # self.on_click_cb = on_click_cb
        self.clicked.connect(lambda x: on_click_cb(index))
        self.setObjectName('connection-btn')
        self.setCursor(Qt.PointingHandCursor)
        if index == 0:
            self.setStyleSheet('border-left: 2px solid #272343')


class UI(QWidget):
    def __init__(self, thread, connections: List[ConnectionInfo]):
        super().__init__()
        self.connection = ''
        self.t = thread
        self.t.db_list_updated.connect(self.on_dbs_list)
        self.t.query_result.connect(self.on_query_result)
        self.t.use_db.connect(self.on_use_db)
        self.t.error.connect(self.on_error)
        self.t.info.connect(self.on_info)
        self.t.execute.connect(self.on_query)
        self.t.table_list_updated.connect(self.on_tables_list)
        self.t.running_query.connect(self.on_query_op)
        t = QThread()
        self.t.moveToThread(t)
        t.started.connect(self.t.longRunning)
        t.start()
        self._t = t

        self.setObjectName('mainbox')
        self.db_list_open = False
        self.table_list_open = False

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Maximum)

        self.db_label_input = QLabel('')
        self.textbox = QLineEdit(parent=self)
        self.textbox.returnPressed.connect(self.run_query)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(QMargins(0, 0, 0, 0))
        self.layout.setSpacing(0)

        self.top = QWidget(parent=self)
        self.top.setObjectName('top')
        self.top_layout = QVBoxLayout()
        self.top_layout.setSpacing(0)
        self.top.setLayout(self.top_layout)
        text_and_button = QHBoxLayout()
        text_and_button.setSpacing(0)

        self.spinner = QtWaitingSpinner(self, False)
        self.spinner.setInnerRadius(-1)
        self.spinner.setObjectName('spinner')
        self.spinner.setColor('#353b48')
        self.spinner.setBgColor('#eeeeee')
        self.spinner.setNumberOfLines(16)
        self.spinner.setRevolutionsPerSecond(1.2)
        self.spinner.setLineWidth(2.5)
        self.spinner.setLineLength(12)
        self.spinner.setRoundness(10)
        self.spinner.setPadding(5)

        run = QPushButton("Run")
        run.setObjectName('run-btn')
        run.setCursor(Qt.PointingHandCursor)
        run.clicked.connect(self.run_query)

        commit = QPushButton("Commit")
        commit.setObjectName('commit-btn')
        commit.setCursor(Qt.PointingHandCursor)
        commit.clicked.connect(self.on_commit_click)

        rollback = QPushButton("Rollback")
        rollback.setObjectName('rollback-btn')
        rollback.setCursor(Qt.PointingHandCursor)
        rollback.clicked.connect(self.on_rollback_click)
        self.bottom = QWidget(parent=self)
        self.bottom.setObjectName('bottom')

        self.bottom_layout = QHBoxLayout()
        self.bottom_layout.setSpacing(0)
        self.bottom_layout.setContentsMargins(QMargins(0, 0, 0, 0))
        self.bottom.setLayout(self.bottom_layout)

        self.table = Table(parent=self)
        self.table.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)

        self.table_list = ListViewModel([], parent=self)
        self.table_list.setProperty(b'maximumWidth', 0)

        self.sidebar = QStackedWidget(parent=self)
        self.sidebar.setObjectName('sidebar')
        self.sidebar.setProperty(b'maximumWidth', 0)

        self.list = QListView(parent=self.sidebar)
        self.list.setObjectName('db_list')
        self.list.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.MinimumExpanding)
        self.dbs_label = VertLabel("D A T A B A S E S")
        self.dbs_label.setObjectName('database_label')
        self.dbs_label.setCursor(Qt.PointingHandCursor)

        self.sidebar.addWidget(self.list)
        self.sidebar.addWidget(self.dbs_label)
        self.sidebar.setMaximumWidth(200)

        self.dbs_label.clicked.connect(self.on_list_click)
        self.list.doubleClicked.connect(self.on_list_dbl_click)

        self.tablelist = QListView(parent=self)
        self.tablelist.setObjectName('table_list')
        self.tablelist.setModel(self.table_list)
        self.tablelist.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.MinimumExpanding)
        self.tablelist.setMaximumWidth(200)
        self.tablelist.doubleClicked.connect(self.on_tablename_dbl_click)
        self.tablelist.clicked.connect(self.on_tablename_click)

        self.bottom_layout.addWidget(self.sidebar)
        self.bottom_layout.addWidget(self.tablelist)

        self.cellEditorContainer = CellEditorContainer(parent=self)

        self.table_and_editor = QStackedWidget(parent=self)
        self.table_and_editor.addWidget(self.table)
        self.table_and_editor.addWidget(self.cellEditorContainer)

        self.bottom_layout.addWidget(self.table_and_editor)

        connection_buttons = QHBoxLayout()
        for idx, connection in enumerate(connections):
            btn = ConnectionButton(connection.label, idx, self.change_connection)
            connection_buttons.addWidget(btn)

        new_connection_btn = QPushButton('➕ New connection')
        new_connection_btn.setObjectName('connection-btn')
        new_connection_btn.setCursor(Qt.PointingHandCursor)
        new_connection_btn.clicked.connect(self.on_new_connection)
        connection_buttons.addWidget(new_connection_btn)
        connection_buttons.insertStretch(-1)

        self.top_layout.addLayout(connection_buttons)
        self.top_layout.addWidget(self.log_text)
        text_and_button.addWidget(self.db_label_input)
        text_and_button.addWidget(self.textbox)
        text_and_button.addWidget(self.spinner)
        text_and_button.addWidget(run)
        text_and_button.addWidget(commit)
        text_and_button.addWidget(rollback)
        self.top_layout.addLayout(text_and_button)

        self.layout.addWidget(self.bottom)
        self.layout.addWidget(self.top)
        self.setLayout(self.layout)

        self.history_cursor = 0
        self.history = []

        self.db_list = ListViewModel([], parent=self)
        self.autocomplete_state = []

        self.installEventFilter(self)
        self.textbox.installEventFilter(self)

    def on_query_op(self, isRunning: bool) -> None:
        if not isRunning:
            self.spinner.stop()
            return

        self.spinner.start()

    def on_dbs_list(self, dbs: List[str], connection: str) -> None:
        self.db_list = ListViewModel(dbs, parent=self)
        self.connection = connection
        self.update_db_label('')
        self.list.setModel(self.db_list)
        self.open_db_list()

    def on_new_connection(self):

        pass

    def on_tables_list(self, tables: List[str]) -> None:
        self.close_db_list()
        self.table_list = ListViewModel(tables, parent=self)
        self.tablelist.setModel(self.table_list)
        self.open_table_list()

    def on_error(self, error: str) -> None:
        self.append_to_status('<span style="color: red">'+error+'</span>')
        self.spinner.stop()

    def on_info(self, info: str) -> None:
        self.append_to_status('<span style="color: black">'+info+'</span>')

    def on_query(self, query: str, params) -> None:
        p = ''
        if params:
            p = ' <table style="border-color: red; border-style: solid" border="1px solid red"><tr><td>'
            p += '</td><td>'.join([str(param) for param in params])
            p += '</td></tr></table>'
        self.append_to_status(query + p)

    def on_query_result(self, results) -> None:
        self.close_cell_editor()
        self.table.set_data(results)

    def update_db_label(self, db: str):
        text = self.connection
        if db:
            text = f'{text}.{db}'
        self.dbs_label.setText(text)
        self.db_label_input.setText(text)

    def on_use_db(self, db: str) -> None:
        self.update_db_label(db)
        self.close_db_list()

    def append_to_status(self, text: str) -> None:
        # lines = self.log_text.toHtml()
        self.log_text.insertHtml(text + '<br>')
        self.log_text.moveCursor(QTextCursor.End)

    def prev_command(self, inc: int = -1) -> None:
        self.history_cursor += inc
        hl = len(self.history)
        if hl > 0:
            self.textbox.setText(self.history[self.history_cursor % hl])

    def change_connection(self, connection_id: int) -> None:
        self.t.job.emit('change_connection', str(connection_id), '', {})

    def eventFilter(self, source, event: QEvent):
        if event.type() == QEvent.KeyPress:
            key = event.key()

            if source == self.textbox:
                if key == Qt.Key_Tab or key == Qt.Key_Backtab:
                    self.autocomplete(event.key() == Qt.Key_Tab)
                    return True

                elif key == Qt.Key_Up:
                    self.prev_command()
                    return True

                elif key == Qt.Key_Down:
                    self.prev_command(+1)
                    return True

                elif key == Qt.Key_Shift:
                    return False

            elif key >= Qt.Key_0 and key <= Qt.Key_9:
                if QGuiApplication.queryKeyboardModifiers() == Qt.ControlModifier:
                    number = key - Qt.Key_0
                    self.change_connection(number)
                    return True

            self.autocomplete_state = []

        return QMainWindow.eventFilter(self, source, event)

    SQL = [
        'USE',
        'SELECT',
        'FROM',
        'IN',
        'WHERE',
        'GROUP',
        'BY',
        'INSERT',
        'UPDATE',
        'TABLE',
        'VALUES',
    ]

    def autocomplete(self, forward):
        if self.autocomplete_state:
            [words, after_cursor, word, matches, matches, idx] = self.autocomplete_state

            len_matches = len(matches)
            if forward:
                idx += 1
            if not forward:
                idx += len_matches - 1

            idx = idx % len_matches

            self.autocomplete_state = [list(words), after_cursor, word, matches, matches, idx]

            words.append(matches[idx])
            match = matches[idx]
            before_cursor = ' '.join(words)
            self.textbox.setText(before_cursor + after_cursor)
            self.textbox.setCursorPosition(len(before_cursor))
            return

        pos = self.textbox.cursorPosition()
        text = self.textbox.text()
        before_cursor, after_cursor = text[:pos], text[pos:]
        words = before_cursor.split(' ')
        word = words.pop().lower()
        wl = len(word)
        candidates = [s + ' ' for s in self.SQL] + [db for db in self.db_list._data]
        if '.' in word:
            db_name = word.split('.')[0]
            self.t.job.emit('table_list', db_name, '', {})
            tables = self.table_list._data
            candidates += [db_name + '.' + table + ' ' for table in tables]
        else:
            candidates += [table + ' ' for table in self.table_list._data]

        matches = [w for w in candidates if w[:wl % len(w)].lower() == word]
        if len(matches) == 0:
            return

        match = matches[0]
        if len(matches) != 1:
            match = matches[0]
            self.autocomplete_state = [list(words), after_cursor, word, matches, matches, 0]

        words.append(match)
        before_cursor = ' '.join(words)
        self.textbox.setText(before_cursor + after_cursor)
        self.textbox.setCursorPosition(len(before_cursor))

    @pyqtSlot()
    def on_commit_click(self):
        self.append_to_status('<strong style="color: green">COMMIT</strong>')
        self.t.job.emit('commit', '', '', {})

    @pyqtSlot()
    def on_rollback_click(self):
        self.append_to_status('<strong style="color: red">ROLLBACK</strong>')
        self.t.job.emit('rollback', '', '', {})

    @pyqtSlot()
    def on_list_click(self) -> None:
        self.open_db_list()

    @pyqtSlot()
    def on_list_dbl_click(self) -> None:
        self.close_db_list()
        selection = self.list.selectedIndexes()[0]
        db = self.db_list.get(selection)
        self.t.job.emit('table_list', db, '', {})

    @pyqtSlot()
    def on_tablename_click(self) -> None:
        modifiers = QGuiApplication.queryKeyboardModifiers()
        if modifiers != Qt.AltModifier:
            return
        selection = self.tablelist.selectedIndexes()[0]
        selected_table = self.table_list.get(selection)
        self.t.job.emit('table_contents', selected_table, '', {})

    def open_db_list(self) -> None:
        if self.db_list_open:
            return
        self.sidebar.setCurrentIndex(0)
        self.db_list_open = True
        self.anim = QPropertyAnimation(self.sidebar, b'maximumWidth')
        self.anim.setDuration(150)
        self.anim.setEndValue(200)
        self.anim.start()
        self.close_table_list()

    def close_db_list(self) -> None:
        if not self.db_list_open:
            return
        self.sidebar.setCurrentIndex(1)
        self.db_list_open = False
        self.anim = QPropertyAnimation(self.sidebar, b'maximumWidth')
        self.anim.setDuration(150)
        self.anim.setEndValue(30)
        self.anim.start()

    def open_table_list(self) -> None:
        if self.table_list_open:
            return
        self.table_list_open = True
        self.tableanim = QPropertyAnimation(self.tablelist, b'maximumWidth')
        self.tableanim.setDuration(150)
        self.tableanim.setEndValue(200)
        self.tableanim.start()

    def close_table_list(self) -> None:
        if not self.table_list_open:
            return
        self.table_list_open = False
        self.tableanim = QPropertyAnimation(self.tablelist, b'maximumWidth')
        self.tableanim.setDuration(150)
        self.tableanim.setEndValue(0)
        self.tableanim.start()

    def show_cell_editor(self, text: str, cb: Callable) -> None:
        self.table_and_editor.setCurrentIndex(1)
        self.cellEditorContainer.setText(str(text))

        def onEditDone(text):
            if text is not None:
                cb(text)
            self.close_cell_editor()

        self.cellEditorContainer.setCallback(onEditDone)

    def close_cell_editor(self) -> None:
        self.table_and_editor.setCurrentIndex(0)

    def on_tablename_dbl_click(self) -> None:
        selection = self.tablelist.selectedIndexes()[0]
        selected_table = self.table_list.get(selection)
        self.t.job.emit('table_data', selected_table, '', {})
        self.close_db_list()

    def run_query(self) -> None:
        text = self.textbox.text()
        self.history.append(text)
        self.history_cursor = 0
        self.t.job.emit('query', text, '', {})
        self.textbox.setText('')

    def on_reference_click(self, column_name: str, value: str) -> None:
        self.t.job.emit('get_reference', column_name, value, {})

    def update_record(self, record: Dict['str', 'str'], column_name: str, data: Union[str, int]) -> None:
        self.t.job.emit('update', column_name, str(data), dict(record))


class TableItem(QTableWidgetItem):
    def __init__(self, column_name: str, idx: int, record: Dict['str', 'str']):
        self.column_name = column_name
        self.record = record
        text = self.text()
        super().__init__(text)

        self.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        # self.setFlags(Qt.ItemIsSelectable)

    def text(self) -> str:
        if self.record[self.column_name] is None:
            return 'NULL'
        return str(self.record[self.column_name])


class Table(QTableWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent=parent)
        self.parent = parent
        self.cellClicked.connect(self.on_click)
        self.cellDoubleClicked.connect(self.on_dbl_click)
        self.itemChanged.connect(self.on_change)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft and Qt.AlignVCenter)
        self.setShowGrid(False)

    def set_data(self, data: List[Tuple]) -> None:
        self.clear()
        row_count = len(data)

        if row_count == 0:
            self.setRowCount(0)
            self.setColumnCount(0)
            return

        self.setRowCount(row_count - 1)

        i = iter(data)
        header = next(i)

        self.setColumnCount(len(header))
        self.setHorizontalHeaderLabels(header)

        for row, item in enumerate(i):
            for col, val in enumerate(item):
                record = dict(zip(header, item))
                self.setItem(row, col, TableItem(header[col], col, record))
        self.resizeColumnsToContents()

    def on_change(self):
        for item in self.selectedItems():
            if item.data(0) != item.record[item.column_name]:
                self.parent.update_record(item.record, item.column_name, item.data(0))
                return

    def on_click(self):
        modifiers = QGuiApplication.queryKeyboardModifiers()
        if modifiers == Qt.AltModifier:
            selected = self.selectedItems()
            for item in selected:
                self.parent.on_reference_click(item.column_name, str(item.record[item.column_name]))
                return

    def on_dbl_click(self):
        selected = self.selectedItems()
        for item in selected:
            def on_update(newValue):
                self.parent.update_record(item.record, item.column_name, newValue)
                item.record[item.column_name] = newValue
                item.setText(item.text())
            self.parent.show_cell_editor(item.record[item.column_name], on_update)

            return
