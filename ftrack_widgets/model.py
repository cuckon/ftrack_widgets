from Qt import QtWidgets, QtGui, QtCore
from Qt.QtCore import QModelIndex, Qt

from .thread import QFtrackQuery

DEFAULT_PAGE_SIZE = 20


def repr_entity(val):
    if val is None:
        return ''

    if isinstance(val, basestring):
        return val

    if 'name' in val:
        return val['name']

    return str(val)


class ItemData(QtCore.QObject):
    ROLE_DATA = QtCore.Qt.UserRole + 100
    ROLE_ENTITY_ID = ROLE_DATA + 1
    fetchStarted = QtCore.Signal()
    loaded = QtCore.Signal()

    def __init__(self, query, item, fields):
        super(ItemData, self).__init__()

        item.setData(self, self.ROLE_DATA)

        self.item = item
        self.fetched = False
        self.fields = fields
        self.query = query

        self._session = query._session
        self._query_thread = QFtrackQuery()
        self._query_thread.responsed.connect(self._append_results)

        self._ = []


    def _append_results(self, results):
        nrows = self.item.rowCount()

        # Eliminate the last "..."
        if nrows:
            if not self.item.child(nrows - 1).data(self.ROLE_DATA):
                self.item.setRowCount(nrows - 1)

        for entity in results:
            items = [
                QtGui.QStandardItem(repr_entity(entity.get(field)))
                for field in self.fields
            ]
            query = self.query._session.query(
                'Context where parent_id is ' + entity['id'],
                self.query._page_size,
            )

            # _ is necessary to protect it from being auto released by Qt
            self._.append(ItemData(query, items[0], self.fields))

            items[0].setData(entity['id'], self.ROLE_ENTITY_ID)
            self.item.appendRow(items)

        if self.query._can_fetch_more():
            self.item.appendRow(QtGui.QStandardItem('...'))

        self.loaded.emit()

    def fetch(self):
        self.fetched = True
        self.fetchStarted.emit()

        if not self.query._can_fetch_more():
            self.loaded.emit()
            return

        self._query_thread.do(self.query)


class QFtrackModel(QtGui.QStandardItemModel):
    def __init__(self, session, page_size=DEFAULT_PAGE_SIZE, fields=None,
                 parent=None):
        super(QFtrackModel, self).__init__(parent)
        self._session = session
        self._page_size = page_size
        self._fields = fields or ['name', 'description']
        self._root_data = None

    def query(self, expression):
        # TODO: projection
        query = self._session.query(expression, self._page_size)
        self._root_data = ItemData(query, self.invisibleRootItem(), self._fields)
        self._root_data.fetch()

    def columnCount(self, parent):
        return len(self._fields)

    def headerData(self, section, orientation, role):
        '''Return label for *section* according to *orientation* and *role*.'''
        if orientation == QtCore.Qt.Horizontal:
            if section < len(self._fields):
                column = self._fields[section]
                if role == Qt.DisplayRole:
                    return column

        return None

    def canFetchMore(self, parent):
        item = self.itemFromIndex(parent)
        if not item:
            return False
        data = item.data(ItemData.ROLE_DATA)
        if not data:
            return False

        return not data.fetched

    def fetchMore(self, parent):
        self._loadMore(parent)

    def hasChildren(self, index):
        if not index.isValid():
            return True

        entity = self.entity(index)
        if not entity:
            return False

        return entity.entity_type != 'Task'

    def entity(self, index):
        """Returns the entity at given *index*."""
        entity_id = self.data(index, ItemData.ROLE_ENTITY_ID)
        return entity_id and self._session.get('Context', entity_id)

    def _loadMore(self, index):
        data = self.data(index, ItemData.ROLE_DATA)
        data and data.fetch()

    def itemActived(self, index):
        """Load more unloaded entities."""
        data = self.data(index, ItemData.ROLE_DATA)
        if data:
            return

        index_parent = index.parent()
        if index_parent.isValid():
            self._loadMore(index_parent)
        else:
            self._root_data.fetch()



class QEntityModel(QFtrackModel):
    def __init__(self, entity=None, page_size=DEFAULT_PAGE_SIZE, fields=None, parent=None):
        super(QEntityModel, self).__init__(
            entity and entity.session,
            page_size,
            fields,
            parent
        )
        self._entity = entity
        if entity:
            self.setCurrentEntity(entity)

    def setCurrentEntity(self, entity):
        """Set the entity the for model to work on."""
        self._session = entity.session
        self.query('Context where parent_id is ' + entity['id'])
        self._entity = entity



class QFtrackSortProxy(QtCore.QSortFilterProxyModel):
    def loadMore(self, index):
        """Load more unloaded entities."""
        return self.sourceModel().itemActived(index)

    def setEntity(self, entity):
        """Set the entity the for model to work on."""
        return self.sourceModel().setCurrentEntity(entity)

    def entity(self, index):
        """Returns the entity at given *index*."""
        return self.sourceModel().entity(index)

