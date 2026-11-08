"""Permission-scoped collaboration extensions shared by web and native clients."""
import hashlib
import json
import re

import frappe
from frappe.utils import cint, getdate, get_datetime

MENTION = re.compile(r"@\[([^\]\n]{1,160})\]\(([^)\s]{1,140})\)")


def display_body(body):
    return MENTION.sub(lambda match: '@' + match[1], body or '')


def mentions(body, root):
    from volunteering.volunteering import collaboration as c
    allowed = {row.user for row in root.members if c.has_chat_access(row.user)}
    users = []
    for match in MENTION.finditer(body or ''):
        if match[2] not in allowed or match[1] != c._name(match[2]):
            frappe.throw('Mention people from this conversation using the member picker.')
        if match[2] not in users:
            users.append(match[2])
    if len(users) > 50:
        frappe.throw('Mention at most 50 people in one message.')
    return users


def clean_subtasks(rows, root):
    from volunteering.volunteering import collaboration as c
    if not isinstance(rows, list) or len(rows) > 100:
        frappe.throw('Use at most 100 subtasks.')
    cleaned, ids = [], set()
    for value in rows:
        row = c._data(value, {'id', 'title', 'assignee', 'deadline', 'status'})
        key = c._text(row.get('id'), 80, True)
        if key in ids:
            frappe.throw('Subtask identifiers must be distinct.')
        ids.add(key)
        status = row.get('status') or 'Open'
        if status not in {'Open', 'In progress', 'Completed'}:
            frappe.throw('Choose a valid subtask status.')
        assignee = c._allowed_assignee(row['assignee'], root) if row.get('assignee') else None
        cleaned.append({'id': key, 'title': c._text(row.get('title'), 160, True), 'assignee': assignee,
                        'deadline': str(getdate(row['deadline'])) if row.get('deadline') else None, 'status': status})
    return cleaned


def update_subtask(name, subtask, status, expected_modified):
    from volunteering.volunteering import collaboration as c
    doc, root, level = c._item(name)
    if doc.item_kind != 'Task' or doc.status not in c.OPEN:
        frappe.throw('Subtasks can be changed only on an open task.')
    c._version(doc, expected_modified)
    data = c._json(doc.item_data, {})
    row = next((x for x in data.get('subtasks', []) if x['id'] == subtask), None)
    if not row or not (c._can_edit_item(doc, level) or row.get('assignee') == frappe.session.user):
        c._deny()
    if status not in {'Open', 'In progress', 'Completed'}:
        frappe.throw('Choose a valid subtask status.')
    row['status'] = status
    doc.item_data = data
    c._save(doc)
    c._entry(doc.space, f"{row['title']}: {status}", item=doc.name)
    c._publish(doc.space, root)
    return c._item_payload(doc, level)


def _page(rows, before, fields=('creation', 'name')):
    """Stable cursor using timestamp and ID; the anchor must belong to the scoped result."""
    if not before:
        return rows
    anchor = next((row for row in rows if row.name == before), None)
    if not anchor:
        frappe.throw('This page is no longer available. Refresh the list.')
    return [row for row in rows if (get_datetime(row.creation), row.name) < (get_datetime(anchor.creation), anchor.name)]


def get_comments(name, before=None):
    from volunteering.volunteering import collaboration as c
    item, room, root, level = c._read_item(name)
    if item.item_kind != 'Tracker' or not c.can_read_space(room.name):
        c._deny()
    rows = frappe.get_all(c.PREFIX+'Entry', filters={'item': name, 'entry_kind': 'Comment', 'is_deleted': 0},
                         fields=['name', 'creation'], order_by='creation desc, name desc', limit_page_length=0)
    rows = _page(rows, before)
    return {'comments': [c._entry_payload(frappe.get_doc(c.PREFIX+'Entry', row.name), level) for row in rows[:30]],
            'next_cursor': rows[29].name if len(rows) > 30 else None,
            'can_comment': level in {'Owner', 'Manager', 'Member'}}


def post_comment(name, body, request_key):
    from volunteering.volunteering import collaboration as c
    item, root, level = c._item(name)
    c._space(item.space, write=True, lock=True)
    if item.item_kind != 'Tracker':
        c._deny()
    text = c._text(body, 12000, True)
    tagged = mentions(text, root)
    key = hashlib.sha256(f'comment:{frappe.session.user}:{name}:{c._text(request_key, 100, True)}'.encode()).hexdigest()
    prior = frappe.db.get_value(c.PREFIX+'Entry', {'request_key': key}, ['name','body','is_deleted'], as_dict=True)
    if prior:
        if prior.body != text or prior.is_deleted:
            frappe.throw('This comment request was used with different details.')
        return {'name': prior.name}
    entry = c._insert('Entry', {'space': item.space, 'item': name, 'body': text, 'entry_kind': 'Comment',
                               'request_key': key, 'mentions': tagged})
    c._save(item)
    c._publish(item.space, root)
    return {'name': entry.name}


def get_mentions(before=None, unread_only=False):
    from volunteering.volunteering import collaboration as c
    user = c._require()
    spaces = frappe.get_all(c.PREFIX+'Space', filters={'root_space':['in',c._root_ids() or ['__none__']]},
                            fields=['name','title'], limit_page_length=0)
    titles = {row.name:row.title for row in spaces}
    rows = frappe.get_all(c.PREFIX+'Entry', filters={'space':['in',list(titles) or ['__none__']],
                         'is_deleted':0,'mentions':['like','%'+user.replace('%',r'\%').replace('_',r'\_')+'%']},
                         fields=['name','creation','space','mentions'], order_by='creation desc, name desc', limit_page_length=0)
    rows = [row for row in rows if user in c._json(row.mentions, [])]
    seen = {row.space:row.mentions_seen_through for row in frappe.get_all(c.PREFIX+'Read State',
            filters={'user':user},fields=['space','mentions_seen_through'],limit_page_length=0)}
    unread = lambda row: not seen.get(row.space) or get_datetime(row.creation)>get_datetime(seen[row.space])
    total = sum(bool(unread(row)) for row in rows)
    if cint(unread_only): rows = [row for row in rows if unread(row)]
    rows = _page(rows, before)
    return {'mentions':[dict(c._entry_payload(frappe.get_doc(c.PREFIX+'Entry',row.name),'Viewer'),
            space_title=titles[row.space],unread=bool(unread(row))) for row in rows[:30]],
            'next_cursor':rows[29].name if len(rows)>30 else None,'unread_count':total}


def mark_mention_seen(entry):
    from volunteering.volunteering import collaboration as c
    doc = frappe.get_doc(c.PREFIX+'Entry',entry)
    if frappe.session.user not in c._json(doc.get('mentions'),[]) or doc.is_deleted: c._deny()
    return c._mark_received(doc.space,entry,('mentions_seen_through',))


def search_conversation(query, space=None, kind='All', before=None):
    from volunteering.volunteering import collaboration as c
    c._require()
    text=c._text(query,100,True)
    if len(text)<2: frappe.throw('Enter at least two characters to search.')
    if kind not in {'All','Messages','Tasks','Trackers','Files'}: frappe.throw('Choose a search category.')
    if space:
        c._space(space);rooms=[space]
    else:
        rooms=frappe.get_all(c.PREFIX+'Space',filters={'root_space':['in',c._root_ids() or ['__none__']]},pluck='name',limit_page_length=0)
    # Parameterized literal LIKE, without interpreting user text as SQL wildcard syntax.
    term='%'+text.replace('\\','\\\\').replace('%',r'\%').replace('_',r'\_')+'%'
    rows=frappe.db.sql('''select name, creation, space, body, item, entry_kind from `tabCollaboration Entry`
        where space in %(rooms)s and is_deleted=0 and entry_kind!='System' and body like %(term)s
        order by creation desc,name desc''',{'rooms':tuple(rooms or ['__none__']),'term':term},as_dict=True) if kind in {'All','Messages'} else []
    output=[{'id':'entry:'+x.name,'name':x.name,'creation':x.creation,'space':x.space,'kind':'Message','title':display_body(x.body), 'item':x.item} for x in rows]
    if kind in {'All','Tasks','Trackers'}:
        types={'Tasks':['Task'],'Trackers':['Tracker'],'All':['Task','Tracker']}[kind]
        found=frappe.db.sql('''select name,creation,space,title,item_kind from `tabCollaboration Item`
            where space in %(rooms)s and item_kind in %(types)s and (title like %(term)s or description like %(term)s)''',
            {'rooms':tuple(rooms or ['__none__']),'types':tuple(types),'term':term},as_dict=True)
        output += [{'id':'item:'+x.name,'name':x.name,'item':x.name,'creation':x.creation,'space':x.space,'kind':x.item_kind,'title':x.title} for x in found]
    if kind in {'All','Files'}:
        found=frappe.db.sql('''select f.name,f.file_name,f.file_url,f.creation,e.space,e.item from `tabFile` f
            join `tabCollaboration Entry` e on f.attached_to_doctype='Collaboration Entry' and f.attached_to_name=e.name
            where e.space in %(rooms)s and e.is_deleted=0 and f.is_private=1 and f.file_name like %(term)s''',
            {'rooms':tuple(rooms or ['__none__']),'term':term},as_dict=True)
        output += [{'id':'file:'+x.name,'name':x.name,'item':x.item,'creation':x.creation,'space':x.space,'kind':'File','title':x.file_name,'file_url':x.file_url} for x in found]
    output.sort(key=lambda x:(get_datetime(x['creation']),x['id']),reverse=True)
    if before:
        anchor=next((x for x in output if x['id']==before),None)
        if not anchor: frappe.throw('Search results changed. Search again.')
        output=[x for x in output if (get_datetime(x['creation']),x['id'])<(get_datetime(anchor['creation']),anchor['id'])]
    return {'results':[dict(x,creation=str(x['creation']),space_title=frappe.db.get_value(c.PREFIX+'Space',x['space'],'title')) for x in output[:30]],
            'next_cursor':output[29]['id'] if len(output)>30 else None}


OPERATIONS={'send_message','save_item','update_task','record_progress','add_tracker_files','post_comment','update_subtask'}


def apply_operation(method, payload, request_key):
    """Serialised and fingerprinted replay; successful retries never repeat a mutation."""
    from volunteering.volunteering import collaboration as c
    user=c._require()
    if method not in OPERATIONS: frappe.throw('This action cannot be queued.')
    data=frappe.parse_json(payload) if isinstance(payload,str) else payload
    if not isinstance(data,dict): frappe.throw('Queued action data must be an object.')
    room=data.get('space') or (data.get('payload') or {}).get('space')
    item=data.get('name')
    if item and method!='save_item': room=frappe.db.get_value(c.PREFIX+'Item',item,'space')
    if not room: c._deny()
    if item and method in {'update_task', 'record_progress', 'update_subtask'}:
        # Item-only Update shares must keep working without granting chat membership.
        # The item row lock serialises retries; the normal action still validates its scope.
        c._read_item(item, write=True)
    else:
        c._space(room,write=True,lock=True)
    key=hashlib.sha256(f'{user}:{c._text(request_key,100,True)}'.encode()).hexdigest()
    digest=hashlib.sha256(json.dumps({'method':method,'data':data},sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
    prior=frappe.db.get_value('Collaboration Operation',key,['user','fingerprint','result'],as_dict=True)
    if prior:
        if prior.user!=user or prior.fingerprint!=digest: frappe.throw('This queued request has different details.')
        return c._json(prior.result,{})
    # Match the HTTP representation, including datetimes returned by progress actions.
    result=frappe.parse_json(frappe.as_json(getattr(c,method)(**data)))
    doc=frappe.get_doc({'doctype':'Collaboration Operation','name':key,'user':user,'fingerprint':digest,'result':result})
    doc.flags.name_set=True;doc.flags.collaboration_write=True;doc.insert(ignore_permissions=True)
    return result
