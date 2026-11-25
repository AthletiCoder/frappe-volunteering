"""Published holidays, organisation charter and employee-specific payroll setup."""
import calendar
import json
import math
from datetime import date

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate, nowdate, now_datetime
from volunteering.volunteering.hr_policy import is_policy_manager, require_policy_manager, reason_text, policy_on

FIXED_NAMES=['Republic Day','Independence Day','Gandhi Jayanti','Shivaji Jayanti','Gudi Padwa','Maharashtra Day','Ganesh Chaturthi','Holi','Ram Navami','Janmashtami','Dussehra','Diwali']
OPTIONAL_NAMES=['Eid-ul-Fitr','Bakrid','Good Friday','Christmas','Buddha Purnima','Guru Nanak Jayanti']
DEFAULT_CHARTER={
 'effective_from':'2026-12-01',
 'availability':'Keep your phone available on working days and respond promptly to work calls and messages.',
 'exit_terms':'Notice period and exit terms follow the individual signed offer letter.',
 'contacts':[
  {'area':'Payroll and expenses','name':'Madhu Pr','title':'Accounts','details':'Salary disbursement, payroll queries and expense reimbursement.'},
  {'area':'Records and systems','name':'Hemanth Pr','title':'CFO','details':'Leave balances, attendance records, system access and IT support.'},
  {'area':'Workload and scheduling','name':'Your reporting manager','title':'First contact','details':'Role clarity, responsibilities, scheduling and workplace matters.'}],
 'positions':[
  {'id':'directors','name':'Board of Directors','title':'Statutory governance','manager_id':'','functional_line':''},
  {'id':'advisors','name':'Board of Advisors','title':'Advisory counsel; no direct reporting line','manager_id':'','functional_line':''},
  {'id':'executive','name':'Executive Board','title':'Priya Gopesh Pr, Nikunj Lila Pr, Trivikram Charan Pr, Vadiraj Tirtha Das, Saurabh Pr','manager_id':'directors','functional_line':''},
  {'id':'operations','name':'Saurabh Pr','title':'Operations Head','manager_id':'programmes','functional_line':''},
  {'id':'programmes','name':'HG Nikunj Lila Pr','title':'Program Implementation','manager_id':'executive','functional_line':''},
  {'id':'admin','name':'Vadiraj Tirtha Das','title':'Administration and Media Wing Lead','manager_id':'executive','functional_line':''},
  {'id':'cfo','name':'Hemanth Pr','title':'CFO (Honorary)','manager_id':'admin','functional_line':''},
  {'id':'accounts','name':'Ankit Pr','title':'Accounts In-charge','manager_id':'cfo','functional_line':''},
  {'id':'associate','name':'Madhu Pr','title':'Accounts Associate','manager_id':'accounts','functional_line':''},
  {'id':'amar','name':'HG Amar Jagannath Pr','title':'Pune Activities Head and Media Manager','manager_id':'operations','functional_line':'Administration and Media Wing'},
  {'id':'delhi','name':'HG Harinam Rupa Pr','title':'Delhi Activities Head','manager_id':'operations','functional_line':''},
  {'id':'rajesh','name':'Rajesh Pr','title':'Volunteer Relationship Coordinator','manager_id':'operations','functional_line':''},
  {'id':'shyam','name':'Shyamsundari Mataji','title':'Volunteer Relationship Coordinator','manager_id':'operations','functional_line':''}],
 'locations':[
  {'city':'Pune','centres':'Balewadi, IIIT Pune, IISER Pune','activities_head':'HG Amar Jagannath Pr','office':'Prachetas, 1st floor'},
  {'city':'Mumbai','centres':'IIT Bombay','activities_head':'To be appointed','office':''},
  {'city':'Delhi','centres':'No centre yet','activities_head':'HG Harinam Rupa Pr','office':''},
  {'city':'Hyderabad','centres':'No centre yet','activities_head':'To be appointed','office':''}]}


def is_payroll_manager():
 return is_policy_manager() or 'Accounts Manager' in frappe.get_roles()


def _require_payroll():
 if not is_payroll_manager():frappe.throw(_('Only HR or Accounts Managers can manage payroll profiles.'),frappe.PermissionError)


def charter():
 row=frappe.db.get_value('HR Charter Revision',{},['name','settings'],order_by='creation desc',as_dict=True)
 return {'revision':row.name if row else '', 'settings':frappe.parse_json(row.settings) if row else DEFAULT_CHARTER}


@frappe.whitelist(methods=['POST'])
def get_people_centre(year=None):
 from volunteering.volunteering.time_leave_portal import access
 data=access();own=(data['employee'] or {}).get('name');year=int(year or getdate(nowdate()).year)
 if not 2024<=year<=2100:frappe.throw(_('Choose a year between 2024 and 2100.'))
 company=frappe.db.get_value('Employee',own,'company') if own else 'Sevamrita Foundation'
 holidays=frappe.get_all('HR Holiday',filters={'company':company,'holiday_date':['between',[date(year,1,1),date(year,12,31)]],**({} if data['can_override'] else {'enabled':1})},
  fields=['name','modified','holiday_date','holiday_name','kind','enabled'],order_by='holiday_date asc')
 from volunteering.volunteering.hr_special_leave import optional_units
 profile=frappe.db.get_value('HR Payroll Profile',{'employee':own},['monthly_basic','monthly_gross','pf_enrolled','pt_applicable','pt_exempt','effective_from'],as_dict=True) if own else None
 people=frappe.get_all('Employee',filters={'status':'Active'},fields=['name','employee_name','gender'],order_by='employee_name',limit_page_length=0) if is_payroll_manager() else data['people']
 manager=frappe.db.get_value('Employee',own,'reports_to') if own else None
 current=policy_on();upcoming=policy_on('2026-12-01')
 return {**charter(),'year':year,'today':nowdate(),'employee':data['employee'],'can_manage':data['can_override'],'can_payroll':is_payroll_manager(),
  'people':people,'employment_types':frappe.get_all('Employment Type',pluck='name') if data['can_override'] else [],'holidays':holidays,'fixed_names':FIXED_NAMES,'optional_names':OPTIONAL_NAMES,
  'fixed_count':sum(bool(row.enabled and row.kind=='Fixed') for row in holidays),
  'optional_used':optional_units(own,date(year,1,1)) if own else 0,'optional_limit':policy_on(date(year,12,31))['optional_holidays'],
  'current_policy':{k:current[k] for k in ['work_log_days','half_day_hours','full_day_hours','comp_valid_months','medical_certificate_days','maternity_weeks','paternity_days','paternity_window_months','charter_enabled']},
  'revised_policy':{k:upcoming[k] for k in ['work_log_days','half_day_hours','full_day_hours','comp_valid_months']},
  'guide_policy':{k:v for k,v in (current if current['charter_enabled'] else upcoming).items() if not k.startswith('_')},
  'reporting_manager':frappe.db.get_value('Employee',manager,'employee_name') if manager else '',
  'payroll_accounts':{name:frappe.db.get_value('Salary Component Account',{'parent':name,'company':company},'account') for name in ['SF Employee PF','SF Professional Tax']} if is_payroll_manager() else {},
  'liability_accounts':frappe.get_all('Account',filters={'company':company,'root_type':'Liability','account_type':['not in',['Payable','Receivable']],'is_group':0,'disabled':0},fields=['name','account_name'],order_by='account_name') if is_payroll_manager() else [],
  'payroll_profile':profile,'salary_slips':frappe.get_all('Salary Slip',filters={'employee':own or '__none__','docstatus':1},fields=['name','start_date','end_date','gross_pay','total_deduction','net_pay','sf_employer_pf'],order_by='end_date desc',limit=24)}


@frappe.whitelist(methods=['POST'])
def save_holiday(details, reason, expected_modified=None):
 require_policy_manager();reason=reason_text(reason);raw=frappe.parse_json(details)
 if not isinstance(raw,dict):frappe.throw(_('Enter holiday details.'))
 if not raw.get('holiday_date') or not cstr(raw.get('holiday_name')).strip():frappe.throw(_('Holiday name and date are required.'))
 day=getdate(raw['holiday_date']);kind=raw.get('kind')
 if kind not in {'Fixed','Optional'}:frappe.throw(_('Choose a fixed or optional holiday.'))
 if day<getdate(nowdate()):frappe.throw(_('Use today or a future holiday date; historical calendars retain their records.'))
 company='Sevamrita Foundation'
 frappe.db.get_value('Company',company,'name',for_update=True)
 if raw.get('name'):
  doc=frappe.get_doc('HR Holiday',raw['name'],for_update=True)
  if str(doc.modified)!=cstr(expected_modified):frappe.throw(_('This holiday changed. Reload the calendar.'))
 else:doc=frappe.new_doc('HR Holiday')
 for affected in {day, getdate(doc.holiday_date) if doc.holiday_date else day}:
  if frappe.db.exists('Leave Application',{'company':company,'status':['in',['Open','Approved']],'docstatus':['<',2],'from_date':['<=',affected],'to_date':['>=',affected]}):frappe.throw(_('Resolve leave requests on this date before changing the calendar.'))
  if frappe.db.exists('Salary Slip',{'company':company,'docstatus':1,'start_date':['<=',affected],'end_date':['>=',affected]}):frappe.throw(_('Payroll is already submitted for this date. Keep the historical holiday calendar unchanged.'))
 enabled=int(bool(raw.get('enabled',True)))
 if enabled and kind=='Fixed':
  count=frappe.db.count('HR Holiday',{'company':company,'kind':'Fixed','enabled':1,'holiday_date':['between',[day.replace(month=1,day=1),day.replace(month=12,day=31)]],'name':['!=',doc.name or '']})
  if count>=12:frappe.throw(_('This year already has twelve fixed holidays. Disable or correct an existing entry.'))
 doc.update({'company':company,'holiday_date':day,'holiday_name':cstr(raw['holiday_name']).strip()[:140],'kind':kind,'enabled':enabled,'change_reason':reason,
  'unique_key':f'{company}:{day}'})
 doc.flags.hr_resource_service=True;doc.save(ignore_permissions=True)
 doc.add_comment('Info',frappe.utils.escape_html(reason))
 from volunteering.volunteering.employee_calendars import clear_calendar_cache
 clear_calendar_cache()
 frappe.enqueue('volunteering.volunteering.employee_calendars.sync_all_calendars',enqueue_after_commit=True)
 return get_people_centre(day.year)


@frappe.whitelist(methods=['POST'])
def save_charter(settings, expected_revision, reason):
 require_policy_manager();reason=reason_text(reason)
 frappe.db.get_value('Company','Sevamrita Foundation','name',for_update=True)
 current=charter()
 if cstr(expected_revision)!=current['revision']:frappe.throw(_('The handbook changed. Reload before publishing.'))
 raw=frappe.parse_json(settings)
 if not isinstance(raw,dict) or set(raw)-set(DEFAULT_CHARTER):frappe.throw(_('Unsupported handbook fields.'))
 value={**DEFAULT_CHARTER,**raw}
 if len(frappe.as_json(value))>60000:frappe.throw(_('Keep the handbook under 60 KB.'))
 if not all(isinstance(value[k],list) for k in ['positions','contacts','locations']):frappe.throw(_('Enter valid handbook sections.'))
 ids={r.get('id') for r in value['positions']}
 if len(ids)!=len(value['positions']) or None in ids:frappe.throw(_('Organisation positions need distinct IDs.'))
 for row in value['positions']:
  parent=row.get('manager_id')
  if parent and parent not in ids:frappe.throw(_('Choose an existing reporting position.'))
  seen={row['id']}
  while parent:
   if parent in seen:frappe.throw(_('Reporting positions cannot form a cycle.'))
   seen.add(parent);parent=next(r.get('manager_id') for r in value['positions'] if r['id']==parent)
 doc=frappe.get_doc({'doctype':'HR Charter Revision','settings':json.dumps(value),'reason':reason,'published_by':frappe.session.user,'published_on':now_datetime()})
 doc.flags.hr_resource_service=True;doc.insert(ignore_permissions=True)
 return charter()


def payroll_profile_on(employee, day):
 row=frappe.db.get_value('HR Payroll Profile Revision',{'employee':employee,'effective_from':['<=',day]},['settings'],as_dict=True,order_by='effective_from desc, creation desc')
 return frappe.parse_json(row.settings) if row else None


@frappe.whitelist(methods=['POST'])
def get_payroll_profile(employee):
 _require_payroll()
 doc=frappe.db.get_value('HR Payroll Profile',{'employee':employee},['name','modified'],as_dict=True)
 data=frappe.get_doc('HR Payroll Profile',doc.name).as_dict() if doc else {'employee':employee,'effective_from':nowdate(),'monthly_basic':0,'monthly_gross':0,'pf_enrolled':0,'pt_applicable':0,'pt_exempt':0,'payroll_state':'Maharashtra','basic_component':'Basic'}
 return {'profile':data,'history':frappe.get_all('HR Payroll Profile Revision',filters={'employee':employee},fields=['name','effective_from','settings','reason','author','published_on'],order_by='creation desc',limit=30)}


@frappe.whitelist(methods=['POST'])
def save_payroll_profile(details, reason, expected_modified=None):
 _require_payroll();reason=reason_text(reason);raw=frappe.parse_json(details)
 from volunteering.volunteering.hr_leave_balances import lock_employee, require_unprocessed_salary
 employee=raw.get('employee');lock_employee(employee)
 if not frappe.db.exists('Employee',{'name':employee,'status':'Active'}):frappe.throw(_('Choose an active employee.'))
 day=getdate(raw.get('effective_from') or nowdate())
 require_unprocessed_salary(employee,day,date(2100,12,31))
 # Backlog payroll may be configured before it is processed, with a reason.
 values={key:raw.get(key) for key in ['employee','basic_component','payroll_state','pt_exemption_reason']}
 values['effective_from']=str(day)
 if values['payroll_state'] not in {'Maharashtra','Other'}:frappe.throw(_('Choose the employee payroll state.'))
 for key in ['monthly_basic','monthly_gross']:
  try:number=float(raw.get(key) or 0)
  except (TypeError,ValueError):frappe.throw(_('Enter valid payroll amounts.'))
  if not math.isfinite(number) or number<0 or number>10000000:frappe.throw(_('Payroll amounts must be between zero and 1 crore.'))
  values[key]=number
 if values['monthly_basic']>values['monthly_gross']:frappe.throw(_('Basic salary cannot exceed gross salary.'))
 for key in ['pf_enrolled','pt_applicable','pt_exempt']:values[key]=int(bool(raw.get(key)))
 if values['pt_applicable'] and values['payroll_state']!='Maharashtra':frappe.throw(_('Configure the applicable state rules before enabling automatic professional tax outside Maharashtra.'))
 if values['pt_exempt'] and len(cstr(values['pt_exemption_reason']).strip())<10:frappe.throw(_('Explain the professional-tax exemption.'))
 name=frappe.db.get_value('HR Payroll Profile',{'employee':employee},'name')
 doc=frappe.get_doc('HR Payroll Profile',name) if name else frappe.new_doc('HR Payroll Profile')
 if name and str(doc.modified)!=cstr(expected_modified):frappe.throw(_('The payroll profile changed. Reload it.'))
 doc.update({**values,'change_reason':reason});doc.flags.hr_resource_service=True;doc.save(ignore_permissions=True)
 revision=frappe.get_doc({'doctype':'HR Payroll Profile Revision','employee':employee,'effective_from':day,'settings':json.dumps(values),'reason':reason,'author':frappe.session.user,'published_on':now_datetime()})
 revision.flags.hr_resource_service=True;revision.insert(ignore_permissions=True)
 return get_payroll_profile(employee)


def deduction_values(basic, gross, gender, month, profile, policy):
 pf=min(max(0,basic),policy['pf_wage_ceiling']) if policy['pf_wage_ceiling'] else max(0,basic)
 employee_pf=round(pf*policy['pf_employee_rate']/100) if profile.get('pf_enrolled') else 0
 employer_pf=round(pf*policy['pf_employer_rate']/100) if profile.get('pf_enrolled') else 0
 pt=0
 if profile.get('pt_applicable') and not profile.get('pt_exempt'):
  if profile.get('payroll_state')!='Maharashtra':frappe.throw(_('Automatic professional tax is configured for Maharashtra only.'))
  if gender=='Female':upper=gross>policy['pt_female_exempt']
  elif gender=='Male':
   upper=gross>policy['pt_male_upper']
   if policy['pt_male_lower']<gross<=policy['pt_male_upper']:pt=policy['pt_middle_rate']
  else:frappe.throw(_('Verify the employee gender or record the appropriate professional-tax exemption.'))
  if upper:pt=policy['pt_february_rate'] if int(month)==2 else policy['pt_regular_rate']
 return {'employee_pf':employee_pf,'employer_pf':employer_pf,'professional_tax':pt,'total_deduction':employee_pf+pt,'net_before_other_deductions':round(gross-employee_pf-pt,2)}


@frappe.whitelist(methods=['POST'])
def preview_payroll(employee, month=None, unpaid_days=0):
 _require_payroll()
 from volunteering.volunteering.work_log_portal import _month
 first,last=_month(month or getdate(nowdate()).strftime('%Y-%m'))
 profile=payroll_profile_on(employee,last)
 if not profile:frappe.throw(_('Save an effective payroll profile first.'))
 if not policy_on(last).get('charter_enabled'):frappe.throw(_('The revised payroll preview is available from the charter effective date. Earlier payroll keeps its earlier rules.'))
 days=calendar.monthrange(first.year,first.month)[1]
 try:unpaid=float(unpaid_days)
 except (TypeError,ValueError):frappe.throw(_('Enter valid unpaid days.'))
 if not math.isfinite(unpaid) or not 0<=unpaid<=days:frappe.throw(_('Unpaid days must fit within the selected month.'))
 fraction=(days-unpaid)/days
 return {'month':first.strftime('%Y-%m'),'calendar_days':days,'unpaid_days':unpaid,'salary_reduction':round(profile['monthly_gross']*(1-fraction),2),
  **deduction_values(profile['monthly_basic']*fraction,profile['monthly_gross']*fraction,frappe.db.get_value('Employee',employee,'gender'),first.month,profile,policy_on(last)),
  'gross_after_absence':round(profile['monthly_gross']*fraction,2),'preview_only':True}


@frappe.whitelist(methods=['POST'])
def get_employee_reporting(employee):
 require_policy_manager()
 return frappe.db.get_value('Employee',employee,['name','employee_name','modified','reports_to','designation','employment_type'],as_dict=True)


@frappe.whitelist(methods=['POST'])
def save_employee_reporting(employee, reports_to, designation, expected_modified, reason, employment_type=None):
 require_policy_manager();reason=reason_text(reason)
 from volunteering.volunteering.hr_leave_balances import lock_employee
 lock_employee(employee)
 doc=frappe.get_doc('Employee',employee,for_update=True)
 if str(doc.modified)!=cstr(expected_modified):frappe.throw(_('This employee changed. Reload before updating reporting.'))
 if doc.company!='Sevamrita Foundation':frappe.throw(_('Choose a Sevamrita employee.'))
 parent=reports_to;seen={employee}
 while parent:
  if parent in seen:frappe.throw(_('An employee reporting relationship cannot form a cycle.'))
  seen.add(parent)
  person=frappe.db.get_value('Employee',parent,['reports_to','company','status'],as_dict=True)
  if not person or person.company!=doc.company or person.status!='Active':frappe.throw(_('Choose an active reporting manager in this company.'))
  parent=person.reports_to
 title=cstr(designation).strip()
 if not title or len(title)>140:frappe.throw(_('Enter a designation up to 140 characters.'))
 if not frappe.db.exists('Designation',title):frappe.get_doc({'doctype':'Designation','designation_name':title}).insert(ignore_permissions=True)
 if employment_type is not None:
  if not frappe.db.exists('Employment Type',employment_type):frappe.throw(_('Choose an existing employment type.'))
  doc.employment_type=employment_type
 doc.reports_to=reports_to or None;doc.designation=title;doc.save(ignore_permissions=True)
 doc.add_comment('Info','Reporting/designation updated by '+frappe.session.user+': '+frappe.utils.escape_html(reason))
 return get_employee_reporting(employee)


@frappe.whitelist(methods=['POST'])
def configure_payroll_ledgers(pf_account, pt_account, reason):
 _require_payroll();reason=reason_text(reason)
 company='Sevamrita Foundation'
 for name,account,abbr in [('SF Employee PF',pf_account,'SFEPF'),('SF Professional Tax',pt_account,'SFPT')]:
  if not account:frappe.throw(_('Select both payroll liability ledgers.'))
  row=frappe.db.get_value('Account',account,['company','root_type','account_type','is_group','disabled'],as_dict=True)
  if not row or row.company!=company or row.root_type!='Liability' or row.account_type in {'Payable','Receivable'} or row.is_group or row.disabled:frappe.throw(_('Choose active liability ledgers that do not require an employee, customer or supplier party.'))
  doc=frappe.get_doc('Salary Component',name) if frappe.db.exists('Salary Component',name) else frappe.get_doc({'doctype':'Salary Component','salary_component':name,'salary_component_abbr':abbr,'type':'Deduction','depends_on_payment_days':0})
  existing=next((row for row in doc.accounts if row.company==company),None)
  if existing:existing.account=account
  else:doc.append('accounts',{'company':company,'account':account})
  doc.save(ignore_permissions=True);doc.add_comment('Info','Payroll ledger configured by '+frappe.session.user+': '+frappe.utils.escape_html(reason))
 return {'configured':True}
