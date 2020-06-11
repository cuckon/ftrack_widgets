from Qt import QtWidgets, QtGui, QtCore

from . import model, mixins


def make_vlay_widget(parent=None):
    widget = parent or QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    widget.setLayout(layout)
    return widget


def current_user(session):
    return session.query(
        'User where username is ' + session.api_user
    ).one()


def current_project(session):
    return


class TreeWidget(QtWidgets.QTreeView):
    # selected = QtCore.Signal(object)
    # doubleClicked = QtCore.Signal(object)
    #
    def __init__(self, session, fields=None, parent=None):
        super(TreeWidget, self).__init__(parent)
        self._session = session

        proj_model = model.QueryModel(self._session, fields=fields)
        mixins.mixin(proj_model, mixins.SimpleIcon)
        self.setModel(proj_model)
        self.setSelectionMode(self.ExtendedSelection)
        self.doubleClicked.connect(proj_model.itemActived)

    def query(self, expression):
        self.model().query(expression)

    def setCustomFilter(self, func):
        self.model().setCustomFilter(func)

    def selectedEntities(self):
        return [
            self.model().entity(i)
            for i in self.selectedIndexes()
            if i.column() == 0
        ]


class TasksWidget(QtWidgets.QWidget):
    def __init__(self, session):
        self._session = session

        filter_le = QtWidgets.QLineEdit()
        filter_le.setPlaceholderText('rig.*')

        self._task_view = QtWidgets.QListView()
        user = current_user(self._session)
        tasks = self._session.query(
            'Task where assignments.resource_id is "%s" and project_id is "%s"'
            % (user['id'], self._current_project()['id'])
        ).all()
        tasks = self._sort_tasks(tasks)
        self._task_model = model.ListModel(tasks)
        mixins.mixin(self._task_model, mixins.SimpleIcon)
        mixins.mixin(self._task_model, mixins.ParentPrefix)

        proxy = model.SortFilterProxy()
        proxy.setSourceModel(self._task_model)
        proxy.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        proxy.setFilterKeyColumn(-1)

        self._task_view.setModel(proxy)
        self._task_view.setSelectionMode(self._task_view.ExtendedSelection)

        make_vlay_widget(self)
        self.layout().addWidgets([filter_le, self._task_view])
        filter_le.textChanged.connect(proxy.setFilterRegExp)


    def _sort_tasks(self, tasks):
        """Sort tasks based on the time of last timelog"""
        user_id = self._current_user()['id']
        logs = self._session.query(
            'Timelog where user_id is "%s" and context.project_id is "%s" order'
            ' by start descending limit 200' %
            (user_id, self._current_project()['id'])
        ).all()
        task_occurance = [l['context_id'] for l in logs]

        timer = self._session.query(
            'Timer where user_id is ' + user_id
        ).first()
        if timer:
            task_occurance.insert(0, timer['context_id'])

        def index(t):
            if t['id'] in task_occurance:
                return task_occurance.index(t['id'])
            return 9999
        return sorted(tasks, key=index)