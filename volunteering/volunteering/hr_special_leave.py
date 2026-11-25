"""Medical evidence, optional holidays and separate parental entitlements."""
import base64
from datetime import timedelta
from pathlib import PurePath

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, cstr, getdate, nowdate
from volunteering.volunteering.hr_policy import policy_on, is_policy_manager, reason_text

MATERNITY = 'Maternity Leave'
PATERNITY = 'Paternity Leave'
OPTIONAL = 'Optional Holiday'
SPECIAL = {MATERNITY, PATERNITY, OPTIONAL}


def ensure_types():
    for name in SPECIAL:
        if not frappe.db.exists('Leave Type',name):
            frappe.get_doc({'doctype':'Leave Type','leave_type_name':name,'include_holiday':int(name==MATERNITY),
                'allow_negative':0,'is_earned_leave':0,'is_carry_forward':0}).insert(ignore_permissions=True)


def optional_units(employee, day, exclude=None):
    day=getdate(day)
    filters={'employee':employee,'leave_type':OPTIONAL,'status':['in',['Open','Approved']],'docstatus':['<',2],
        'from_date':['between',[day.replace(month=1,day=1),day.replace(month=12,day=31)]]}
    if exclude:filters['name']=['!=',exclude]
    return sum(row.total_leave_days for row in frappe.get_all('Leave Application',filters=filters,fields=['total_leave_days']))


def prepare_special(employee, type, start, end, raw):
    policy=policy_on(start)
    if not policy['charter_enabled']:frappe.throw(_('This leave type is available from the revised policy effective date.'))
    ensure_types()
    from volunteering.volunteering.hr_leave_balances import current_allocation
    if type==OPTIONAL:
        if raw.get('half_day'):frappe.throw(_('Select the full designated optional holiday.'))
        if start!=end:frappe.throw(_('Select one designated optional holiday per request.'))
        from volunteering.volunteering.employee_calendars import holiday_on
        company=frappe.db.get_value('Employee',employee,'company')
        if not frappe.db.exists('HR Holiday',{'company':company,'holiday_date':start,'kind':'Optional','enabled':1}):frappe.throw(_('Choose a published optional holiday.'))
        if holiday_on(employee,start):frappe.throw(_('This date is already a weekly off or fixed holiday.'))
        quota=policy['optional_holidays']
        if optional_units(employee,start,raw.get("name"))>=quota:frappe.throw(_('The optional-holiday allowance for this year is already used or reserved.'))
        period_start,period_end=start.replace(month=1,day=1),start.replace(month=12,day=31)
        amount=quota
    else:
        gender=frappe.db.get_value('Employee',employee,'gender')
        expected_gender='Female' if type==MATERNITY else 'Male'
        if gender!=expected_gender:frappe.throw(_('This parental leave type requires the appropriate employee eligibility record. Ask HR to check your employee details.'))
        if not raw.get('childbirth_date'):frappe.throw(_('Enter the expected or actual childbirth date.'))
        event=getdate(raw['childbirth_date'])
        if raw.get('half_day'):frappe.throw(_('Parental leave must be requested in full days.'))
        if type==MATERNITY:
            case=raw.get('parental_case') or 'Birth'
            if case not in {'Birth','Two or more surviving children','Adoption or commissioning'}:frappe.throw(_('Choose the parental leave case.'))
            amount=(12 if case!='Birth' else policy['maternity_weeks'])*7
            period_start=getdate(add_days(event,-56 if case=='Birth' else -42 if case=='Two or more surviving children' else 0))
            period_end=getdate(add_days(event,amount-1))
            if (end-start).days+1>amount:frappe.throw(_('This request exceeds the parental entitlement.'))
        else:
            amount=policy['paternity_days'];period_start=event;period_end=getdate(add_months(event,policy['paternity_window_months']))
        if start<period_start or end>period_end:frappe.throw(_('Choose dates within the parental leave window: {0} to {1}.').format(period_start,period_end))
    allocation=current_allocation(employee,type,start)
    if not allocation:
        frappe.get_doc({'doctype':'Leave Allocation','employee':employee,'leave_type':type,'from_date':period_start,
            'to_date':period_end,'new_leaves_allocated':amount,'carry_forward':0}).insert(ignore_permissions=True).submit()
    elif getdate(allocation.to_date)<end:frappe.throw(_('An existing entitlement covers a different childbirth period. HR must resolve it first.'))


def validate_details(doc, exception=''):
    policy=policy_on(doc.from_date,revision=doc.get('sf_policy_revision'))
    if doc.get('leave_category')=='Medical':
        if not policy['charter_enabled']:frappe.throw(_('The medical policy is not effective on these dates.'))
        informed=doc.get('sf_manager_notified_on')
        if not informed:frappe.throw(_('Record the date you informed your manager.'))
        informed=getdate(informed)
        if informed>getdate(nowdate()):frappe.throw(_('The notification date cannot be in the future.'))
        if informed>getdate(add_days(doc.from_date,policy['medical_notice_days'])) and not exception:
            frappe.throw(_('Sudden illness must be reported to the manager the same day. HR can record an exception.'))
        if doc.status=='Approved' and (getdate(doc.to_date)-getdate(doc.from_date)).days+1>policy['medical_certificate_days']:
            if not doc.get('sf_medical_certificate') and not exception:frappe.throw(_('Attach a medical certificate before approval for more than two consecutive days.'))
    previous = doc.get_doc_before_save()
    verification_changed = any(
        cstr(doc.get(key)) != cstr(previous.get(key) if previous else None)
        for key in ('sf_eligibility_verified_by', 'sf_eligibility_reason')
    )
    if verification_changed and not doc.flags.get('eligibility_service'):
        frappe.throw(_('Eligibility verification can only be recorded through the HR verification action.'),frappe.PermissionError)
    if doc.get('sf_medical_certificate'):
        if not frappe.db.exists('File',{'file_url':doc.sf_medical_certificate,'is_private':1,'attached_to_doctype':'Leave Application','attached_to_name':doc.name}):
            frappe.throw(_('Attach a private certificate through this request before using it as evidence.'),frappe.PermissionError)
    if doc.leave_type not in SPECIAL:return
    if not policy['charter_enabled']:frappe.throw(_('This leave type is not effective on these dates.'))
    if doc.leave_type==OPTIONAL:
        company=frappe.db.get_value('Employee',doc.employee,'company')
        if getdate(doc.from_date)!=getdate(doc.to_date) or doc.half_day or not frappe.db.exists('HR Holiday',{'company':company,'holiday_date':doc.from_date,'kind':'Optional','enabled':1}):
            frappe.throw(_('Choose one published optional holiday as a full day.'))
        if optional_units(doc.employee,doc.from_date,doc.name)+doc.total_leave_days>policy['optional_holidays']:
            frappe.throw(_('The optional-holiday allowance is already used or reserved.'))
    elif doc.status=='Approved' and not doc.get('sf_eligibility_verified_by'):
        frappe.throw(_('HR must verify parental eligibility before the reporting manager approves leave.'))


@frappe.whitelist(methods=['POST'])
def upload_certificate(filename, content):
    from volunteering.volunteering.time_leave_portal import access
    access()
    name=PurePath(cstr(filename).replace('\\','/')).name
    if len(name)>140 or PurePath(name).suffix.lower() not in {'.pdf','.png','.jpg','.jpeg'}:frappe.throw(_('Choose a PDF, PNG or JPEG certificate.'))
    if len(cstr(content))>7*1024*1024:frappe.throw(_('Certificate must be at most 5 MB.'))
    try:data=base64.b64decode(content,validate=True)
    except Exception:frappe.throw(_('Invalid certificate content.'))
    if not data or len(data)>5*1024*1024:frappe.throw(_('Choose a non-empty certificate up to 5 MB.'))
    valid=(data.startswith(b'%PDF') if name.lower().endswith('.pdf') else data.startswith(b'\x89PNG\r\n\x1a\n') if name.lower().endswith('.png') else data.startswith(b'\xff\xd8\xff'))
    if not valid:frappe.throw(_('Certificate content does not match the selected file type.'))
    if name.lower().endswith('.pdf'):
        from io import BytesIO
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
        try:PdfReader(BytesIO(data))
        except (PdfReadError, ValueError):frappe.throw(_('This PDF could not be read. Upload a valid certificate.'))
    from frappe.utils.file_manager import save_file
    file=save_file(name,data,None,None,is_private=1)
    return {'file_url':file.file_url,'filename':file.file_name}


def bind_certificate(doc, url):
    if not url:return
    files=frappe.get_all('File',filters={'file_url':url,'is_private':1,'owner':frappe.session.user},fields=['name','owner','attached_to_doctype','attached_to_name'])
    file=next((row for row in files if not row.attached_to_name or row.attached_to_name==doc.name),None)
    if not file:
        frappe.throw(_('Choose a private certificate uploaded by your account for this request.'),frappe.PermissionError)
    frappe.db.set_value('File',file.name,{'attached_to_doctype':'Leave Application','attached_to_name':doc.name,'attached_to_field':'sf_medical_certificate'})
    doc.db_set('sf_medical_certificate',url)


@frappe.whitelist(methods=['POST'])
def attach_certificate(name, file_url, expected_modified):
    from volunteering.volunteering.time_leave_portal import access, _normal_row
    from volunteering.volunteering.hr_leave_balances import lock_employee
    data=access();employee=frappe.db.get_value('Leave Application',name,'employee');lock_employee(employee)
    doc=frappe.get_doc('Leave Application',name,for_update=True)
    if doc.employee!=(data['employee'] or {}).get('name') and not data['can_override']:frappe.throw(_('Only the employee or HR may attach evidence.'),frappe.PermissionError)
    if doc.status!='Open' or str(doc.modified)!=str(expected_modified):frappe.throw(_('Reopen the current open request before adding evidence.'))
    bind_certificate(doc,file_url);doc.add_comment('Info','Private supporting evidence attached by '+frappe.session.user)
    return _normal_row(doc)


@frappe.whitelist(methods=['POST'])
def verify_parental_eligibility(name, expected_modified, reason):
    from volunteering.volunteering.hr_policy import require_policy_manager
    from volunteering.volunteering.time_leave_portal import _normal_row
    require_policy_manager();reason=reason_text(reason)
    doc=frappe.get_doc('Leave Application',name,for_update=True)
    if doc.leave_type not in {MATERNITY,PATERNITY} or doc.status!='Open' or str(doc.modified)!=str(expected_modified):frappe.throw(_('Reopen an undecided parental request before verification.'))
    if frappe.db.get_value('Employee',doc.employee,'user_id')==frappe.session.user:frappe.throw(_('Another HR manager must verify your eligibility.'),frappe.PermissionError)
    doc.flags.eligibility_service=True;doc.flags.ignore_permissions=True
    doc.sf_eligibility_verified_by=frappe.session.user;doc.sf_eligibility_reason=reason
    doc.save(ignore_permissions=True);doc.add_comment('Info','Parental eligibility verified by '+frappe.session.user+': '+frappe.utils.escape_html(reason))
    return _normal_row(doc)
