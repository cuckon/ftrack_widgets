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
        'Asset': 'AssetVersion where asset_id is %s',
    }.get(entity.entity_type, 'Context where parent_id is %s')
    return query_pattern % entity['id']


def append_entities(entities, item, fields, page_size, filter_func):
    if not entities:
        return
    session = entities[0].session

    for entity in entities:
        if not filter_func(entity):
            continue

        items = [
            QtGui.QStandardItem(repr_entity(entity, field))
            for field in fields
        ]

        query = session.query(
            query_children_exp(entity),
            page_size,
        )

        ItemData(query, items[0], fields, filter_func)

        items[0].entity = entity
        item.appendRow(items)


class ItemData(object):
    ROLE_DATA = QtCore.Qt.UserRole + 100
    ROLE_ENTITY = ROLE_DATA + 1

    def __init__(self, query, item, fields, filter_func):
        item.setData(self, self.ROLE_DATA)

        self.item = item
        self.fetched = False
        self.fields = fields
        self.query = query
        self.filter_func = filter_func

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
            results, self.item, self.fields, self.query._page_size,
            self.filter_func
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
        self._filter = lambda x: True

        if entities:
            self.appendEntities(entities)

    def setCustomFilter(self, func):
        self._filter = func

    def indexOfEntity(self, entity):
        item = self.invisibleRootItem()
        if not item.hasChildren() or 'link' not in entity:
            return QtCore.QModelIndex()

        ancestor_ids = [i['id'] for i in entity['link']]

        # Find the right ancestor item
        for row in range(item.rowCount()):
            child_item = item.child(row, 0)
            child_entity = self.entity(child_item.index())
            if child_entity['id'] in ancestor_ids:
                base_item = child_item
                base_entity = child_entity
                break
        else:
            return QtCore.QModelIndex()

        # Find the item
        start_parent_index = ancestor_ids.index(base_entity['id'])
        reach_dead_end = False
        for link in entity['link'][start_parent_index + 1:]:
            child_item = None
            current_child_index = 0
            while not child_item:
                if current_child_index >= base_item.rowCount():
                    if not self.canFetchMore(base_item.index()):
                        reach_dead_end = True
                        break

                    self.fetchMore(base_item.index())
                current_child_item = base_item.child(current_child_index, 0)
                if self.entity(current_child_item.index())['id'] == link['id']:
                    child_item = current_child_item
                    break
                current_child_index += 1

            if reach_dead_end:
                return base_item.index()
            base_item = child_item
        return base_item.index()

    def setEntities(self, entities):
        self.clear()
        self.appendEntities(entities)

    def appendEntities(self, entities):
        append_entities(
            entities, self.invisibleRootItem(), self._fields, self._page_size,
            self._filter
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
        return self.index(
            index.row(), 0, index.parent() or QtCore.QModelIndex()
        )

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
        self._root_data = ItemData(
            query, self.invisibleRootItem(), self._fields, self._filter
        )
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

    def indexOfEntity(self, entity):
        return self.mapFromSource(self.sourceModel().indexOfEntity(entity))
