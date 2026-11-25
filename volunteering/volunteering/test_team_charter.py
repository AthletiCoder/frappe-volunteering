"""December charter, medical/parental leave, holidays and payroll safeguards."""
import uuid
from datetime import date,timedelta
from unittest.mock import patch
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate,nowdate
from volunteering.volunteering import hr_policy as policy,hr_resources as resources,hr_special_leave as special,time_leave_portal as portal,hr_leave_balances as balances
from volunteering.volunteering.accounting_test_utils import get_or_create_user,get_or_create_employee,get_or_create_department

class IntegrationTestTeamCharter(IntegrationTestCase):
 @classmethod
 def setUpClass(cls):
  super().setUpClass();frappe.set_user('Administrator')
  with patch('frappe.core.doctype.user.user.User.password_strength_test'):
   cls.staff=get_or_create_user('charter.staff@example.com',['Employee'])
   cls.manager=get_or_create_user('charter.manager@example.com',['Employee','Leave Approver'])
   cls.hr=get_or_create_user('charter.hr@example.com',['HR Manager'])
  dep=get_or_create_department('Charter regression')
  cls.manager_emp=get_or_create_employee(cls.manager,dep,'Charter Manager')
  cls.emp=get_or_create_employee(cls.staff,dep,'Charter Employee')
  frappe.db.set_value('Employee',cls.emp,{'reports_to':cls.manager_emp,'leave_approver':cls.manager})
 def setUp(self):
  super().setUp();frappe.set_user('Administrator');self.today=getdate(nowdate())
  self.rules={**policy.DEFAULTS,'charter_enabled':1,'work_log_days':4,'comp_valid_months':2,'half_day_hours':3,'director_approval_days':0,'calendar_day_payroll':1,
   '_revision':frappe.db.get_value('HR Policy Revision',{},'name'),'_effective_from':'2026-12-01'}
  self.patches=[patch.object(m,'policy_on',side_effect=lambda day=None,revision=None:self.rules) for m in (policy,resources,special,portal,balances)]
  for p in self.patches:p.start();self.addCleanup(p.stop)
  frappe.local.sf_employee_calendars={}
  for dt in ['Leave Application','Leave Allocation','Leave Adjustment','Leave Ledger Entry','HR Leave Posting','Staff Time Request','Compensatory Leave Use','HR Payroll Profile','HR Payroll Profile Revision','Attendance']:
   frappe.db.delete(dt,{'employee':self.emp})
  frappe.db.set_value('Employee',self.emp,{'gender':'Male','date_of_joining':date(self.today.year,1,1),'employment_type':None})
  frappe.db.set_single_value('HR Settings','restrict_backdated_leave_application',0)
  special.ensure_types();balances.sync_leave_masters()
 def tearDown(self):frappe.set_user('Administrator');super().tearDown()
 def request(self,type='Privilege Leave',**more):
  frappe.set_user(self.staff)
  raw={'type':type,'from_date':str(self.today+timedelta(days=18)),'reason':'Detailed team charter regression request'};raw.update(more)
  return portal.submit_time_request(raw,uuid.uuid4().hex)
 def test_december_revision_is_dated_and_seeded_only_once(self):
  for p in self.patches:p.stop()
  frappe.local.sf_hr_policies=None
  try:
   policy.ensure_policy_defaults();before=frappe.db.count('HR Policy Revision');policy.ensure_policy_defaults()
   self.assertEqual(before,frappe.db.count('HR Policy Revision'))
   self.assertEqual(policy.policy_on('2026-11-30')['work_log_days'],2)
   revised=policy.policy_on('2026-12-01');self.assertEqual(revised['work_log_days'],4);self.assertEqual(revised['comp_valid_months'],2)
   self.assertEqual(revised['director_approval_days'],0);self.assertEqual(revised['half_day_hours'],3)
  finally:
   for p in self.patches:p.start()
   frappe.local.sf_hr_policies=None
 def test_future_policy_publication_rejects_a_stale_editor(self):
  frappe.set_user(self.hr)
  workspace=policy.get_hr_policy_workspace()
  policy.publish_hr_policy({k:self.rules[k] for k in policy.DEFAULTS},str(self.today+timedelta(days=50)),
   'Confirmed a future policy revision for stale editor regression',workspace['revision'],workspace['publication_revision'])
  with self.assertRaises(frappe.ValidationError):policy.publish_hr_policy({k:self.rules[k] for k in policy.DEFAULTS},str(self.today+timedelta(days=51)),
   'Stale future policy publication must be rejected',workspace['revision'],workspace['publication_revision'])
 def test_under_three_hours_absent_and_three_hours_half_day(self):
  from volunteering.volunteering import attendance_service as service
  day=self.today-timedelta(days=6)
  with patch.object(service,'get_holiday_info',return_value=None),patch.object(service,'get_submitted_work_log_hours',return_value=2.99),patch.object(service,'ensure_attendance',return_value=('ATT','created')) as write:
   service.process_employee_attendance(self.emp,day);self.assertEqual(write.call_args.kwargs['status'],'Absent')
  with patch.object(service,'get_holiday_info',return_value=None),patch.object(service,'get_submitted_work_log_hours',return_value=3),patch.object(service,'ensure_attendance',return_value=('ATT','created')) as write:
   service.process_employee_attendance(self.emp,day);self.assertEqual(write.call_args.kwargs['status'],'Half Day')
 def test_medical_notice_waives_advance_and_three_day_limit(self):
  start=self.today-timedelta(days=1)
  row=self.request(category='Medical',from_date=str(start),to_date=str(start+timedelta(days=4)),manager_notified_on=str(start))
  self.assertEqual(row['status'],'Open')
  frappe.set_user(self.manager)
  with self.assertRaises(frappe.ValidationError):portal.decide_time_request('Leave Application',row['name'],'approve',row['modified'])
 def test_medical_late_notice_needs_hr_exception(self):
  start=self.today-timedelta(days=2)
  with self.assertRaises(frappe.ValidationError):self.request(category='Medical',from_date=str(start),manager_notified_on=str(self.today))
 def test_certificate_upload_private_and_rejects_forged_file(self):
  import base64
  frappe.set_user(self.staff)
  with self.assertRaises(frappe.ValidationError):special.upload_certificate('proof.pdf',base64.b64encode(b'not a PDF').decode())
  with self.assertRaises(frappe.ValidationError):special.upload_certificate('corrupt.pdf',base64.b64encode(b'%PDF-1.7\nnot a valid document').decode())
  from io import BytesIO
  from pypdf import PdfWriter
  stream=BytesIO();writer=PdfWriter();writer.add_blank_page(width=100,height=100);writer.write(stream)
  certificate=special.upload_certificate('medical-proof.pdf',base64.b64encode(stream.getvalue()).decode())
  self.assertEqual(frappe.db.get_value('File',{'file_url':certificate['file_url']},'is_private'),1)
  row=self.request(category='Medical',from_date=str(self.today),to_date=str(self.today+timedelta(days=3)),manager_notified_on=str(self.today),certificate_url=certificate['file_url'])
  self.assertEqual(row['certificate_url'],certificate['file_url'])
  frappe.set_user(self.manager)
  result=portal.decide_time_request('Leave Application',row['name'],'approve',row['modified'])
  self.assertEqual(result['status'],'Approved')
 def test_paternity_uses_separate_balance_and_hr_verification(self):
  event=self.today-timedelta(days=2)
  row=self.request('Paternity Leave',from_date=str(self.today+timedelta(days=2)),childbirth_date=str(event))
  self.assertTrue(frappe.db.exists('Leave Allocation',{'employee':self.emp,'leave_type':'Paternity Leave','new_leaves_allocated':5}))
  frappe.set_user(self.manager)
  with self.assertRaises(frappe.ValidationError):portal.decide_time_request('Leave Application',row['name'],'approve',row['modified'])
  frappe.set_user(self.hr)
  row=special.verify_parental_eligibility(row['name'],row['modified'],'Verified childbirth date and employee entitlement records')
  frappe.set_user(self.manager)
  self.assertEqual(portal.decide_time_request('Leave Application',row['name'],'approve',row['modified'])['status'],'Approved')
 def test_paternity_outside_three_month_window_rejected(self):
  with self.assertRaises(frappe.ValidationError):self.request('Paternity Leave',childbirth_date=str(self.today-timedelta(days=150)))
 def test_revised_leave_routes_to_direct_manager_over_legacy_approver(self):
  frappe.db.set_value('Employee',self.emp,'leave_approver',self.hr)
  with patch('volunteering.volunteering.leave_policy.policy_on',return_value=self.rules):
   row=self.request(from_date=str(self.today+timedelta(days=20)))
  self.assertEqual(row['approver'],self.manager)
 def test_parental_type_matches_verified_employee_details(self):
  with self.assertRaises(frappe.ValidationError):self.request('Maternity Leave',childbirth_date=str(self.today))
 def test_parental_leave_does_not_inherit_medical_requirements(self):
  row=self.request('Paternity Leave',category='Medical',from_date=str(self.today+timedelta(days=2)),childbirth_date=str(self.today))
  self.assertEqual(frappe.db.get_value('Leave Application',row['name'],'leave_category'),'Normal')
 def test_hr_with_own_employee_restriction_can_verify_parental_leave(self):
  from frappe.core.doctype.user_permission.user_permission import get_user_permissions
  hr_employee=get_or_create_employee(self.hr,None,'Charter HR Employee')
  if not frappe.db.exists('User Permission',{'user':self.hr,'allow':'Employee','for_value':hr_employee}):
   frappe.get_doc({'doctype':'User Permission','user':self.hr,'allow':'Employee','for_value':hr_employee,'apply_to_all_doctypes':1}).insert(ignore_permissions=True)
  frappe.clear_cache(user=self.hr)
  row=self.request('Paternity Leave',from_date=str(self.today+timedelta(days=2)),childbirth_date=str(self.today))
  frappe.set_user(self.hr)
  original=get_user_permissions(self.hr)
  self.assertFalse(frappe.has_permission('Employee','read',self.emp))
  result=special.verify_parental_eligibility(row['name'],row['modified'],'Verified entitlement despite automatic own-employee restriction')
  self.assertEqual(result['eligibility_verified_by'],self.hr)
  self.assertFalse(frappe.has_permission('Employee','read',self.emp))
  self.assertEqual(get_user_permissions(self.hr),original)
  self.assertEqual(frappe.session.user,self.hr)
 def test_maternity_calendar_entitlement_and_cross_year(self):
  frappe.db.set_value('Employee',self.emp,'gender','Female')
  start=date(self.today.year,12,10);end=start+timedelta(days=181)
  row=self.request('Maternity Leave',from_date=str(start),to_date=str(end),childbirth_date=str(start),parental_case='Birth')
  self.assertEqual(row['days'],182)
  self.assertEqual(frappe.db.get_value('Leave Allocation',{'employee':self.emp,'leave_type':'Maternity Leave'},'new_leaves_allocated'),182)
 def test_employee_cannot_forge_parental_eligibility(self):
  doc=frappe.get_doc({'doctype':'Leave Application','employee':self.emp,'leave_type':'Maternity Leave','from_date':self.today,'to_date':self.today,'sf_eligibility_verified_by':self.hr})
  frappe.set_user(self.staff)
  with self.assertRaises(frappe.PermissionError):special.validate_details(doc)
 def test_optional_holiday_uses_own_two_day_allowance(self):
  day=date(self.today.year+3,2,10)
  while day.weekday()==6:day+=timedelta(days=1)
  frappe.set_user(self.hr)
  data=resources.save_holiday({'holiday_date':str(day),'holiday_name':'Optional test observance','kind':'Optional','enabled':True},'Confirmed optional holiday calendar date')
  self.assertTrue(data['holidays'])
  row=self.request('Optional Holiday',from_date=str(day))
  self.assertEqual(row['days'],1);self.assertEqual(special.optional_units(self.emp,day),1)
  self.assertEqual(frappe.db.get_value('Leave Allocation',{'employee':self.emp,'leave_type':'Optional Holiday'},'new_leaves_allocated'),2)
 def test_revised_calendar_does_not_inherit_extra_fixed_holidays(self):
  from volunteering.volunteering import employee_calendars as calendars
  # Do not overlap unrelated browser fixtures already approved on the site.
  day=date(self.today.year+3,1,10)
  while day.weekday()==6:day+=timedelta(days=1)
  inherited={day:frappe._dict(weekly_off=0,description='Old optional day treated as fixed')}
  with patch.object(calendars,'_base_holidays',return_value=inherited),patch.object(calendars,'policy_on',return_value={**self.rules,'charter_enabled':0}):
   calendars.clear_calendar_cache();self.assertIn(day,calendars.calendar_days(self.emp,day.year))
  with patch.object(calendars,'_base_holidays',return_value=inherited),patch.object(calendars,'policy_on',return_value=self.rules):
   calendars.clear_calendar_cache();self.assertNotIn(day,calendars.calendar_days(self.emp,day.year))
   frappe.set_user(self.hr)
   resources.save_holiday({'holiday_date':str(day),'holiday_name':'Confirmed company fixed holiday','kind':'Fixed'},'Published the confirmed company holiday calendar date')
   self.assertEqual(calendars.calendar_days(self.emp,day.year)[day]['description'],'Confirmed company fixed holiday')
 def test_only_hr_can_edit_holidays_and_payroll_profiles(self):
  frappe.set_user(self.staff)
  with self.assertRaises(frappe.PermissionError):resources.save_holiday({'holiday_date':str(self.today),'holiday_name':'X','kind':'Fixed'},'Unauthorised calendar change')
  with self.assertRaises(frappe.PermissionError):resources.get_payroll_profile(self.emp)
 def test_new_holiday_cannot_recalculate_an_existing_leave(self):
  day=self.today+timedelta(days=23)
  while day.weekday()==6:day+=timedelta(days=1)
  self.request(from_date=str(day))
  frappe.set_user(self.hr)
  with self.assertRaises(frappe.ValidationError):resources.save_holiday({'holiday_date':str(day),'holiday_name':'Unsafe new fixed holiday','kind':'Fixed'},'Attempted calendar change with a pending leave request')
 def test_empty_verification_fields_are_not_an_hr_verification(self):
  doc=frappe.get_doc({'doctype':'Leave Application','employee':self.emp,'leave_type':'Privilege Leave','from_date':self.today,'to_date':self.today,'sf_eligibility_reason':''})
  special.validate_details(doc)
 def test_employee_cannot_attach_another_users_private_certificate(self):
  import base64
  from io import BytesIO
  from pypdf import PdfWriter
  stream=BytesIO();writer=PdfWriter();writer.add_blank_page(width=101,height=101);writer.write(stream)
  frappe.set_user(self.hr)
  certificate=special.upload_certificate('hr-private-proof.pdf',base64.b64encode(stream.getvalue()).decode())
  with self.assertRaises(frappe.PermissionError):self.request(category='Medical',from_date=str(self.today),manager_notified_on=str(self.today),certificate_url=certificate['file_url'])
 def test_pf_and_professional_tax_slabs_and_february(self):
  profile={'pf_enrolled':1,'pt_applicable':1,'payroll_state':'Maharashtra'}
  result=resources.deduction_values(20000,30000,'Male',2,profile,self.rules)
  self.assertEqual(result['employee_pf'],2400);self.assertEqual(result['employer_pf'],2400);self.assertEqual(result['professional_tax'],300)
  self.assertEqual(resources.deduction_values(30000,40000,'Male',1,profile,self.rules)['employee_pf'],3000)
  self.assertEqual(resources.deduction_values(10000,25000,'Female',1,profile,self.rules)['professional_tax'],0)
  self.assertEqual(resources.deduction_values(5000,9000,'Male',1,profile,self.rules)['professional_tax'],175)
 def test_payroll_profile_preview_uses_calendar_days_and_keeps_history(self):
  frappe.set_user(self.hr)
  raw={'employee':self.emp,'effective_from':str(self.today.replace(day=1)),'monthly_basic':20000,'monthly_gross':31000,'pf_enrolled':1,'pt_applicable':1,'payroll_state':'Maharashtra','basic_component':''}
  result=resources.save_payroll_profile(raw,'Verified payroll enrolment and monthly salary values')
  self.assertEqual(len(result['history']),1)
  preview=resources.preview_payroll(self.emp,f'{self.today.year}-12',1)
  self.assertEqual(preview['calendar_days'],31);self.assertEqual(preview['salary_reduction'],1000)
  self.assertEqual(preview['employer_pf'],round(20000*30/31*.12))
 def test_handbook_revision_is_permissioned_and_reporting_cycles_rejected(self):
  frappe.set_user(self.hr)
  raw=dict(resources.DEFAULT_CHARTER);raw['positions']=[{'id':'a','name':'A','manager_id':'b'},{'id':'b','name':'B','manager_id':'a'}]
  with self.assertRaises(frappe.ValidationError):resources.save_charter(raw,resources.charter()['revision'],'Changed reporting structure after review')
 def test_payroll_profile_cannot_change_submitted_salary_period(self):
  frappe.set_user(self.hr)
  with patch.object(balances,'salary_processed',return_value=True):
   with self.assertRaises(frappe.ValidationError):resources.save_payroll_profile({'employee':self.emp,'effective_from':str(self.today)},'Attempted change to locked payroll period')
 def test_payroll_ledgers_require_unrestricted_liability_accounts(self):
  from volunteering.volunteering.accounting_test_utils import get_or_create_bank_account,get_or_create_payable_account
  bank=get_or_create_bank_account();payable=get_or_create_payable_account()
  frappe.set_user(self.hr)
  for account in [bank,payable]:
   with self.assertRaises(frappe.ValidationError):resources.configure_payroll_ledgers(account,account,'Verified payroll ledger validation test')
  company=frappe.db.get_value('Employee',self.emp,'company')
  parent=frappe.db.get_value('Account',{'company':company,'root_type':'Liability','is_group':1},'name')
  account=frappe.get_doc({'doctype':'Account','account_name':'Charter payroll deductions '+uuid.uuid4().hex[:8],'parent_account':parent,'company':company,'is_group':0}).insert(ignore_permissions=True).name
  self.assertTrue(resources.configure_payroll_ledgers(account,account,'Verified employee PF and PT payable mappings')['configured'])
  self.assertEqual(frappe.db.get_value('Salary Component Account',{'parent':'SF Employee PF','company':company},'account'),account)
 def test_actual_salary_uses_calendar_divisor_and_employer_pf_is_separate(self):
  from volunteering.volunteering.overrides.salary_slip import SevamritaSalarySlip
  start=date(self.today.year,12,1);end=date(self.today.year,12,31)
  slip=frappe.get_doc({'doctype':'Salary Slip','employee':self.emp,'start_date':start,'end_date':end,'actual_start_date':start,'actual_end_date':end})
  with patch('volunteering.volunteering.overrides.salary_slip.policy_on',return_value=self.rules),patch.object(type(slip),'get_holidays_for_employee',return_value=[]),patch.object(type(slip),'calculate_lwp_ppl_and_absent_days_based_on_attendance',return_value=(0,1)),patch.object(type(slip),'get_half_absent_days',return_value=1):
   slip.get_working_days_details()
  self.assertEqual(slip.total_working_days,31);self.assertEqual(slip.payment_days,29.5)
  profile={'pf_enrolled':1,'pt_applicable':1,'payroll_state':'Maharashtra','basic_component':'Basic'}
  slip.set('earnings',[{'salary_component':'Basic','amount':20000}]);slip.gross_pay=30000
  with patch('volunteering.volunteering.overrides.salary_slip.policy_on',return_value=self.rules),patch.object(resources,'payroll_profile_on',return_value=profile):slip.apply_regional_deductions()
  self.assertEqual(sum(row.amount for row in slip.deductions),2600)
  self.assertEqual(slip.sf_employer_pf,2400)
  self.assertEqual(sum(row.amount for row in slip.employer_contributions),2400)
  # Recalculating cannot duplicate contributions or retain unenrolled ones.
  with patch('volunteering.volunteering.overrides.salary_slip.policy_on',return_value=self.rules),patch.object(resources,'payroll_profile_on',return_value=profile):slip.apply_regional_deductions()
  self.assertEqual(len(slip.deductions),2);self.assertEqual(len(slip.employer_contributions),1)
  with patch('volunteering.volunteering.overrides.salary_slip.policy_on',return_value=self.rules),patch.object(resources,'payroll_profile_on',return_value={'pf_enrolled':0,'pt_applicable':0}):slip.apply_regional_deductions()
  self.assertEqual(len(slip.deductions),0);self.assertEqual(len(slip.employer_contributions),0);self.assertEqual(slip.sf_employer_pf,0)
 def test_optional_quota_reservation_cannot_exceed_two(self):
  day=date(self.today.year+3,3,10);rows=[]
  for i in range(3):
   while day.weekday()==6:day+=timedelta(days=1)
   frappe.set_user(self.hr);resources.save_holiday({'holiday_date':str(day),'holiday_name':f'Optional quota test {i}','kind':'Optional','enabled':True},'Confirmed optional holiday date for quota check')
   if i<2:rows.append(self.request('Optional Holiday',from_date=str(day)))
   else:
    with self.assertRaises(frappe.ValidationError):self.request('Optional Holiday',from_date=str(day))
   day+=timedelta(days=1)
  frappe.set_user(self.manager)
  self.assertEqual(portal.decide_time_request('Leave Application',rows[0]['name'],'approve',rows[0]['modified'])['status'],'Approved')
 def test_reporting_changes_are_audited_and_cycles_blocked(self):
  frappe.set_user(self.hr);employee=resources.get_employee_reporting(self.emp)
  result=resources.save_employee_reporting(self.emp,self.manager_emp,'Volunteer Relationship Coordinator',employee.modified,'Reviewed role and reporting relationship')
  self.assertEqual(result.designation,'Volunteer Relationship Coordinator')
  manager=resources.get_employee_reporting(self.manager_emp)
  with self.assertRaises(frappe.ValidationError):resources.save_employee_reporting(self.manager_emp,self.emp,'Operations Head',manager.modified,'Attempted reporting cycle must be rejected')
 def test_old_dates_do_not_gain_new_entitlements(self):
  for p in self.patches:p.stop()
  frappe.local.sf_hr_policies=None
  try:
   with self.assertRaises(frappe.ValidationError):self.request('Paternity Leave',from_date='2026-11-30',childbirth_date='2026-11-29')
  finally:
   for p in self.patches:p.start()
 def test_payroll_preview_covers_leap_february(self):
  frappe.set_user(self.hr)
  resources.save_payroll_profile({'employee':self.emp,'effective_from':str(self.today),'monthly_basic':20000,'monthly_gross':29000,'payroll_state':'Maharashtra','pt_applicable':1,'pf_enrolled':1},'Verified profile for leap-year salary calculation')
  result=resources.preview_payroll(self.emp,'2028-02',1)
  self.assertEqual(result['calendar_days'],29);self.assertEqual(result['salary_reduction'],1000)
  self.assertEqual(result['professional_tax'],300)
