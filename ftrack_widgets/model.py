import six
from Qt import QtWidgets, QtGui, QtCore
from Qt.QtCore import QModelIndex, Qt

from .thread import QueryThread

DEFAULT_PAGE_SIZE = 20


def repr_entity(entity, attr):
    if attr == 'name' and entity.entity_type == 'AssetVersion':
        return '%s.v%03d' % (entity['asset']['name'], entity['version'])

    value = entity.get(attr)
    if value is None:
        return ''

    if isinstance(value, six.string_types):
        return value

    if 'name' in value:
        return value['name']


    return str(value)


def query_children_exp(entity):
    query_pattern = {
        'Task': 'AssetVersion where task_id is %s',
        'AssetVersion': 'Component where version_id is %s',
    }.get(entity.entity_type, 'Context where parent_id is %s')
    return query_pattern % entity['id']


def append_entities(entities, item, fields, page_size):
    if not entities:
        return
    session = entities[0].session

    for entity in entities:
        items = [
            QtGui.QStandardItem(repr_entity(entity, field))
            for field in fields
        ]

        query = session.query(
            query_children_exp(entity),
            page_size,
        )

        ItemData(query, items[0], fields)

        items[0].entity = entity
        item.appendRow(items)


class ItemData(object):
    ROLE_DATA = QtCore.Qt.UserRole + 100
    ROLE_ENTITY = ROLE_DATA + 1

    def __init__(self, query, item, fields):
        item.setData(self, self.ROLE_DATA)

        self.item = item
        self.fetched = False
        self.fields = fields
        self.query = query

        self._session = query._session
        self._query_thread = QueryThread()
        self._query_thread.responsed.connect(self._append_results)

    def _append_results(self, results):
        nrows = self.item.rowCount()

        # Eliminate the last "..."
        if nrows:
            if not self.item.child(nrows - 1).data(self.ROLE_DATA):
                self.item.setRowCount(nrows - 1)

        append_entities(
            results, self.item, self.fields, self.query._page_size
        )

        if self.query._can_fetch_more():
            self.item.appendRow(QtGui.QStandardItem('...'))


    def fetch(self):
        self.fetched = True

        if not self.query._can_fetch_more():
            return

        self._query_thread.do(self.query)


class ListModel(QtGui.QStandardItemModel):
    error = QtCore.Signal(str)

    def __init__(self, entities=None, page_size=DEFAULT_PAGE_SIZE, fields=None,
                 parent=None):
        super(ListModel, self).__init__(parent)
        self._page_size = page_size
        self._fields = fields or ['name', 'description']
        self._root_data = None

        if entities:
            self.appendEntities(entities)

    # def indexOfEntity(self, entity):
    #     for parent in entity['link']:
    #

    def setEntities(self, entities):
        self.clear()
        self.appendEntities(entities)

    def appendEntities(self, entities):
        append_entities(
            entities, self.invisibleRootItem(), self._fields, self._page_size
        )

    def flags(self, index):
        return super(ListModel, self).flags(index) & ~QtCore.Qt.ItemIsEditable

    def columnCount(self, parent):
        return len(self._fields)

    def headerData(self, section, orientation, role):
        '''Return label for *section* according to *orientation* and *role*.'''
        if orientation == QtCore.Qt.Horizontal:
            if section < len(self._fields):
                column = self._fields[section]
                if role == Qt.DisplayRole:
                    return column.title()

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

        return 'Component' not in entity.entity_type

    def entity(self, index):
        """Returns the entity at given *index*."""
        index = self._dataIndex(index)
        return getattr(self.itemFromIndex(index), 'entity', None)

    def _loadMore(self, index):
        data = self.data(index, ItemData.ROLE_DATA)
        data and data.fetch()

    def _dataIndex(self, index):
        return self.index(index.row(), 0, index.parent())

    def itemActived(self, index):
        """Load more unloaded entities."""
        index = self._dataIndex(index)
        data = self.data(index, ItemData.ROLE_DATA)
        if data:
            return

        index_parent = index.parent()
        if index_parent.isValid():
            self._loadMore(index_parent)
        else:
            self._root_data.fetch()


class QueryModel(ListModel):
    def __init__(self, session, page_size=DEFAULT_PAGE_SIZE, fields=None,
                 parent=None):
        super(QueryModel, self).__init__(None, page_size, fields, parent)
        self._session = session
        self.expression = None

    def query(self, expression):
        self.clear()
        # TODO: projection
        self.expression = expression
        try:
            query = self._session.query(expression, self._page_size)
        except:
            self.error.emit('Invalid query expression.')
            return
        self._root_data = ItemData(query, self.invisibleRootItem(), self._fields)
        self._root_data.fetch()


class EntityModel(QueryModel):
    def __init__(self, entity=None, page_size=DEFAULT_PAGE_SIZE, fields=None, parent=None):
        super(EntityModel, self).__init__(
            entity and entity.session,
            page_size,
            fields,
            parent
        )
        if entity:
            self.setCurrentEntity(entity)

    def setCurrentEntity(self, entity):
        """Set the entity the for model to work on."""
        self._session = entity.session
        self.query(query_children_exp(entity))


class SortFilterProxy(QtCore.QSortFilterProxyModel):
    def __getattr__(self, item):
        return getattr(self.sourceModel(), item)

    def itemActived(self, index):
        self.sourceModel().itemActived(self.mapToSource(index))

    def entity(self, index):
        return self.sourceModel().entity(self.mapToSource(index))
