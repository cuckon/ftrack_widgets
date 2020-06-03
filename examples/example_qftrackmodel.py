import os
import json
from functools import lru_cache

import ftrack_api

from Qt import QtWidgets, QtGui
from ftrack_widgets.model import QueryModel, EntityModel


@lru_cache()
def _get_variables():
    variables_path = os.path.join(os.path.dirname(__file__), 'ftrack_variables.json')
    with open(variables_path) as f:
        variables = json.load(f)
    return variables


def init_session():
    variables = _get_variables()

    server_url = variables['FTRACK_SERVER']
    user = variables['FTRACK_USER']
    key = variables['FTRACK_API_KEY']
    return ftrack_api.Session(server_url, key, user)


def test_model():
    session = init_session()
    proj = session.query('Project where name is lyao').one()
    model = EntityModel(proj, 2, ['name', 'id', 'type'])
    widget = QtWidgets.QTreeView()
    widget.setModel(model)
    widget.clicked.connect(model.itemActived)

    return widget


app = QtWidgets.QApplication([])
w = test_model()
w.show()

os._exit(app.exec_())
