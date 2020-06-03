from backports.functools_lru_cache import lru_cache

from Qt import QtWidgets, QtGui, QtCore
import qtawesome


from ftrack_api import mixin


@lru_cache()
def task_status_icon(status):
    if not status:
        return None
    state_name = status['state']['name']
    color = status['color']
    icon_name = {
        'Not Started': 'mdi.circle-outline',
        'In Progress': 'mdi.checkbox-blank-circle',
        'Blocked': 'fa.clock-o',
        'Done': 'fa.check-circle',
    }.get(state_name)

    return qtawesome.icon(icon_name, color=color)


def entity_type_icon(entity):
    icon_name = {
        'Shot': 'fa.video-camera',
        'AssetBuild': 'mdi.tree',
        'Folder': 'fa.folder',
    }.get(entity.entity_type)
    return icon_name and qtawesome.icon(icon_name, color='gray')


class ParentPrefix(object):
    def data(self, index, role):
        super_data = super(ParentPrefix, self).data
        if index.column() is not 0:
            return super_data(index, role)
        if role == QtCore.Qt.DisplayRole:
            entity = self.entity(index)
            if not entity:
                return super_data(index, role)
        else:
            return super_data(index, role)

        if role == QtCore.Qt.DisplayRole:
            if index.parent() == self.invisibleRootItem().index():
                if entity['parent']:
                    return '{0[parent][name]}/{0[name]}'.format(entity)
            return super_data(index, role)


class SimpleIcon(object):
    def data(self, index, role):
        super_data = super(SimpleIcon, self).data
        if index.column() is not 0:
            return super_data(index, role)
        if role in [
            QtCore.Qt.ToolTipRole,
            QtCore.Qt.FontRole,
            QtCore.Qt.DecorationRole,
        ]:
            entity = self.entity(index)
            if not entity:
                return super_data(index, role)
        else:
            return super_data(index, role)

        if role == QtCore.Qt.ToolTipRole:
            return (entity.get('status') or {}).get('name')

        if role == QtCore.Qt.DecorationRole:
            if entity.entity_type == 'Task':
                return task_status_icon(entity['status'])
            return entity_type_icon(entity)
