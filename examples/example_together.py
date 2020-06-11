## #@#
import sys
sys.path.insert(0, r'D:\code-test\ftrack_widgets')

import os
import json

import nqt

from Qt import QtWidgets, QtGui

from ftrack_widgets import model


def _get_variables():
    variables_path = os.path.join(os.path.dirname(__file__), 'ftrack_variables.json')
    with open(variables_path) as f:
        variables = json.load(f)
    return variables


def init_session():
    import nftrack
    return nftrack.load_session()


class DemoDialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(DemoDialog, self).__init__(parent)
        self.session = init_session()

        self.setWindowTitle('Ftrack Widgets Demo')

        self.searcher = self._make_general_searcher()
        self.result_selector = self._make_result_selector()

        lay_1 = QtWidgets.QVBoxLayout()
        lay_1.addWidget(self.searcher)
        lay_1.addWidget(self.result_selector)

        self.treeview = self._make_tree()

        self.component_view = self._make_component_view()

        hlay = QtWidgets.QHBoxLayout()
        hlay.addLayout(lay_1)
        hlay.addWidget(self.treeview)
        hlay.addWidget(self.component_view)

        self.setLayout(hlay)
        self._connect()

    def _update_components(self, selector_index):
        entity = self.treeview.model().entity(selector_index)
        if entity.entity_type == 'Task':
            self.component_view.model().query(
                'AssetVersion where task_id is %s' % entity['id']
            )

    def _make_component_view(self):
        table = QtWidgets.QTableView()
        component_model = model.QueryModel(
            self.session, fields=['name', 'comment']
        )
        table.setModel(component_model)

        return table

    def _make_tree(self):
        selector = QtWidgets.QTreeView()
        proj_model = model.EntityModel(fields=['name', 'description'])
        selector.setModel(proj_model)
        selector.clicked.connect(self._update_components)

        return selector

    def _make_result_selector(self):
        selector = QtWidgets.QListView()
        proj_model = model.QueryModel(self.session, fields=['name'])
        selector.setModel(proj_model)

        return selector

    def _make_general_searcher(self):
        searcher = QtWidgets.QLineEdit()
        searcher.setPlaceholderText('Project where status is active')
        return searcher

    def on_search(self):
        self.result_selector.model().query(self.searcher.text())

    def on_change_selection(self, index):
        entity = self.result_selector.model().entity(index)
        if entity:
            self.treeview.model().setCurrentEntity(entity)

    def _connect(self):
        self.searcher.returnPressed.connect(self.on_search)
        self.result_selector.clicked.connect(self.on_change_selection)
        self.result_selector.clicked.connect(self.result_selector.model().itemActived)
        self.treeview.clicked.connect(self.treeview.model().itemActived)


app = QtWidgets.QApplication([])
dialog = DemoDialog()
dialog.show()
os._exit(app.exec_())
