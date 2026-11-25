"""Policy, leave ledger and employee/manager/HR workflow regression tests."""
import uuid
from datetime import date, timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, nowdate

from volunteering.volunteering import hr_policy as policy, hr_leave_balances as balances, time_leave_portal as portal
from volunteering.volunteering.accounting_test_utils import get_or_create_department, get_or_create_employee, get_or_create_user


class IntegrationTestTimeLeave(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user('Administrator')
        with patch('frappe.core.doctype.user.user.User.password_strength_test'):
            cls.staff = get_or_create_user('hr.policy.staff@example.com', ['Employee'])
            cls.manager = get_or_create_user('hr.policy.manager@example.com', ['Employee', 'Leave Approver'])
            cls.hr = get_or_create_user('hr.policy.manager.hr@example.com', ['HR Manager'])
            cls.hr_user = get_or_create_user('hr.policy.clerk@example.com', ['HR User'])
        dep = get_or_create_department('HR Policy Regression')
        cls.manager_emp = get_or_create_employee(cls.manager, dep, 'Policy Manager')
        cls.emp = get_or_create_employee(cls.staff, dep, 'Policy Employee')
        frappe.db.set_value('Employee', cls.emp, {'reports_to': cls.manager_emp, 'leave_approver': cls.manager})

    def setUp(self):
        super().setUp()
        frappe.set_user('Administrator')
        self.today = getdate(nowdate())
        self.rules = {**policy.DEFAULTS, '_revision': frappe.db.get_value('HR Policy Revision', {}, 'name'), '_effective_from': '2026-01-01'}
        self.policy_patch = patch.object(policy, 'policy_on', side_effect=lambda day=None, revision=None: self.rules)
        self.policy_patch.start()
        # Modules import policy_on directly; keep all dated call sites consistent.
        self.patches = [patch.object(module, 'policy_on', side_effect=lambda day=None, revision=None: self.rules)
                        for module in (balances, portal)]
        for item in self.patches: item.start()
        self.addCleanup(self.policy_patch.stop)
        for item in self.patches: self.addCleanup(item.stop)
        for dt in ('Leave Application', 'Leave Allocation', 'Leave Adjustment', 'Leave Ledger Entry', 'HR Leave Posting', 'Compensatory Leave Use', 'Staff Time Request', 'Daily Work Log', 'Attendance'):
            names = frappe.get_all(dt, filters={'employee': self.emp}, pluck='name')
            if dt == 'Daily Work Log' and names: frappe.db.delete('Daily Work Log Item', {'parent': ['in', names]})
            frappe.db.delete(dt, {'employee': self.emp})
        frappe.db.set_value('Employee', self.emp, {'date_of_joining': date(self.today.year, 1, 1), 'employment_type': None})
        frappe.db.set_single_value('HR Settings', 'restrict_backdated_leave_application', 0)
        balances.sync_leave_masters()
        frappe.local.sf_employee_calendars = {}

    def tearDown(self):
        frappe.set_user('Administrator')
        super().tearDown()

    def request(self, type='WFH', **updates):
        raw = {'type': type, 'from_date': str(self.today + timedelta(days=2)), 'reason': 'Detailed regression request for manager review.'}
        raw.update(updates)
        frappe.set_user(self.staff)
        return portal.submit_time_request(raw, uuid.uuid4().hex)

    def approve(self, row, user=None, **updates):
        frappe.set_user(user or self.manager)
        return portal.decide_time_request(row['doctype'], row['name'], 'approve', row['modified'], **updates)

    def test_defaults_and_calendar_year(self):
        self.assertEqual(policy.leave_year(self.today), (date(self.today.year, 1, 1), date(self.today.year, 12, 31)))
        self.assertEqual(self.rules['monthly_leave'], 2.5)
        self.assertEqual(self.rules['carry_forward_days'], 15)
        self.assertEqual(self.rules['weekly_off_day'], 6)
        self.assertEqual(policy.deadline_for_log('2026-11-20'), date(2026, 11, 23))

    def test_policy_and_balance_overrides_are_hr_manager_only(self):
        for user in (self.staff, self.manager, self.hr_user, 'Guest'):
            frappe.set_user(user)
            with self.subTest(user=user), self.assertRaises(frappe.PermissionError): policy.get_hr_policy_workspace()
            with self.assertRaises(frappe.PermissionError): balances.adjust_leave_balance(self.emp, 1, 'Authorised correction reason', uuid.uuid4().hex)
        frappe.set_user(self.hr)
        self.assertTrue(policy.get_hr_policy_workspace()['history'])
        with self.assertRaises(frappe.ValidationError): balances.adjust_leave_balance(self.emp, 1, 'short', uuid.uuid4().hex)

    def test_invalid_policy_values_are_rejected(self):
        for raw in ({'monthly_leave': float('nan')}, {'monthly_leave': 2.6}, {'weekly_off_day': 5, 'swap_off_day': 5}, {'unexpected': 1}, {'work_log_days': 1.5}):
            with self.subTest(raw=raw), self.assertRaises(frappe.ValidationError): policy.clean_policy(raw)

    def test_monthly_accrual_is_exactly_once_and_stops_at_current_month(self):
        balances.ensure_current_balance(self.emp)
        self.assertEqual(balances.paid_balance(self.emp), self.today.month * 2.5)
        balances.ensure_current_balance(self.emp)
        self.assertEqual(frappe.db.count('HR Leave Posting', {'employee': self.emp}), self.today.month)
        self.assertEqual(frappe.db.count('Leave Adjustment', {'employee': self.emp, 'docstatus': 1}), self.today.month)

    def test_joining_mid_month_gets_prorated_credit(self):
        import calendar
        joining = self.today.replace(day=min(10, self.today.day))
        frappe.db.set_value('Employee', self.emp, 'date_of_joining', joining)
        balances.ensure_current_balance(self.emp)
        length = calendar.monthrange(joining.year, joining.month)[1]
        self.assertAlmostEqual(balances.paid_balance(self.emp), round(2.5 * (length-joining.day+1)/length * 4)/4, places=3)

    def test_unpaid_employee_can_log_but_gets_no_automatic_leave_or_attendance(self):
        from volunteering.volunteering.employment_type import ensure_employment_type
        from volunteering.volunteering.attendance_service import process_employee_attendance
        from volunteering.volunteering.work_log_portal import work_logging_access
        frappe.db.set_value('Employee', self.emp, 'employment_type', ensure_employment_type())
        balances.ensure_current_balance(self.emp)
        self.assertFalse(frappe.db.exists('Leave Allocation', {'employee': self.emp}))
        self.assertEqual(process_employee_attendance(self.emp, self.today), 'skipped')
        frappe.set_user(self.staff)
        self.assertTrue(work_logging_access()['can_create'])
        with self.assertRaises(frappe.ValidationError): self.request()

    def test_request_retry_and_payload_conflict(self):
        frappe.set_user(self.staff)
        raw = {'type': 'WFH', 'from_date': str(self.today + timedelta(days=2)), 'reason': 'Prepare remote team materials.'}
        key = uuid.uuid4().hex
        first = portal.submit_time_request(raw, key)
        self.assertEqual(first['name'], portal.submit_time_request(raw, key)['name'])
        with self.assertRaises(frappe.ValidationError): portal.submit_time_request({**raw, 'reason': 'Different request with same reference'}, key)
        with self.assertRaises(frappe.ValidationError): portal.submit_time_request(raw, uuid.uuid4().hex)

    def test_manager_approval_and_self_approval_guard(self):
        row = self.request()
        with self.assertRaises(frappe.PermissionError): self.approve(row, self.staff)
        result = self.approve(row)
        self.assertEqual(result['status'], 'Approved')
        self.assertEqual(self.approve(row)['name'], row['name'])

    def test_ordinary_manager_cannot_change_policy_or_backfill_another_employee(self):
        frappe.set_user(self.manager)
        with self.assertRaises(frappe.PermissionError): portal.submit_time_request({'employee': self.emp, 'type': 'WFH', 'from_date': str(self.today), 'reason': 'Creating on behalf of employee'}, uuid.uuid4().hex)
        frappe.set_user(self.hr)
        with self.assertRaises(frappe.ValidationError): portal.submit_time_request({'employee': self.emp, 'type': 'WFH', 'from_date': str(self.today), 'reason': 'Creating on behalf of employee'}, uuid.uuid4().hex)

    def test_swap_deadline_and_approval_after_deadline(self):
        sunday = self.today + timedelta(days=(6-self.today.weekday()) % 7)
        monday = sunday - timedelta(days=6)
        with patch.object(portal, 'nowdate', return_value=str(monday)):
            row = self.request('Weekly Off Swap', from_date=str(sunday), to_date=str(sunday-timedelta(days=1)))
        with patch.object(portal, 'nowdate', return_value=str(sunday-timedelta(days=1))):
            self.assertEqual(self.approve(row)['status'], 'Approved')
        from volunteering.volunteering.employee_calendars import holiday_on, clear_calendar_cache
        clear_calendar_cache()
        self.assertIsNone(holiday_on(self.emp, sunday))
        self.assertIsNotNone(holiday_on(self.emp, sunday-timedelta(days=1)))

    def test_swap_late_request_needs_explicit_hr_reason(self):
        sunday = self.today + timedelta(days=(6-self.today.weekday()) % 7)
        with patch.object(portal, 'nowdate', return_value=str(sunday-timedelta(days=1))):
            with self.assertRaises(frappe.ValidationError): self.request('Weekly Off Swap', from_date=str(sunday), to_date=str(sunday-timedelta(days=1)))

    def test_compensatory_credit_six_hours_and_expiry(self):
        sunday = self.today - timedelta(days=(self.today.weekday()+1)%7 or 7)
        with patch('volunteering.volunteering.attendance_service.get_submitted_work_log_hours', return_value=6):
            row = self.request('Compensatory Credit', from_date=str(sunday))
            self.assertEqual(row['days'], 1)
            result = self.approve(row)
        self.assertEqual(result['status'], 'Approved')
        self.assertEqual(frappe.db.count('HR Leave Posting', {'employee': self.emp, 'source': 'Compensatory credit'}), 1)
        credit = frappe.get_doc('Staff Time Request', row['name'])
        with patch.object(portal, 'nowdate', return_value=str(getdate(credit.valid_until)+timedelta(days=1))):
            portal.expire_compensatory_credits(self.emp)
            portal.expire_compensatory_credits(self.emp)
        self.assertEqual(frappe.db.get_value('Staff Time Request', row['name'], 'expired_days'), 1)

    def test_short_compensatory_work_requires_hr_decision(self):
        sunday = self.today - timedelta(days=(self.today.weekday()+1)%7 or 7)
        with patch('volunteering.volunteering.attendance_service.get_submitted_work_log_hours', return_value=3):
            row = self.request('Compensatory Credit', from_date=str(sunday))
            self.assertTrue(row['requires_hr'])
            with self.assertRaises(frappe.PermissionError): self.approve(row)
            with self.assertRaises(frappe.ValidationError): self.approve(row, self.hr, credit_days=0.5)
            self.assertEqual(self.approve(row, self.hr, credit_days=0.5, override='Approved shorter Sunday work after checking evidence')['days'], 0.5)

    def test_leave_notice_and_retry(self):
        start = self.today + timedelta(days=7)
        while start.weekday() == 6: start += timedelta(days=1)
        raw = {'type': balances.PAID, 'from_date': str(start), 'to_date': str(start), 'reason': 'Personal appointment with advance notice'}
        frappe.set_user(self.staff)
        key = uuid.uuid4().hex
        row = portal.submit_time_request(raw, key)
        self.assertEqual(row['name'], portal.submit_time_request(raw, key)['name'])
        with self.assertRaises(frappe.ValidationError): portal.submit_time_request({**raw, 'reason': 'Changed original leave application'}, key)
        with patch('volunteering.volunteering.leave_policy.nowdate', return_value=str(start+timedelta(days=2))):
            result = self.approve(row)
        self.assertEqual(result['status'], 'Approved')
        self.assertEqual(frappe.db.count('Leave Ledger Entry', {'transaction_name': row['name'], 'leaves': -1}), 1)

    def test_long_leave_requires_fourteen_days_notice(self):
        from volunteering.volunteering.leave_policy import validate_normal_leave
        with self.assertRaises(frappe.ValidationError): validate_normal_leave(None, self.today+timedelta(days=10), self.today, 4, self.rules)
        validate_normal_leave(None, self.today+timedelta(days=14), self.today, 4, self.rules)

    def test_hr_balance_adjustment_is_reasoned_and_idempotent(self):
        balances.ensure_current_balance(self.emp)
        before = balances.paid_balance(self.emp)
        frappe.set_user(self.hr)
        key = uuid.uuid4().hex
        balances.adjust_leave_balance(self.emp, 1.5, 'Verified exceptional leave balance correction', key)
        balances.adjust_leave_balance(self.emp, 1.5, 'Verified exceptional leave balance correction', key)
        self.assertEqual(balances.paid_balance(self.emp), before+1.5)

    def test_year_end_carry_forward_capped_at_fifteen_and_zero_is_supported(self):
        balances.ensure_current_balance(self.emp)
        balances.post_leave(self.emp, balances.PAID, 20, self.today, 'Test verified additional balance', 'HR adjustment', self.hr, 'carry-fixture:'+self.emp)
        next_year = date(self.today.year+1, 1, 1)
        allocation = balances.ensure_allocation(self.emp, balances.PAID, next_year)
        self.assertEqual(allocation.carry_forward, 0)
        with patch.object(balances,"nowdate",return_value=str(next_year)):
            balances._carry_forward(self.emp,balances.PAID,allocation,next_year)
        self.assertEqual(frappe.db.get_value("HR Leave Posting",{"employee":self.emp,"source":"Carry forward"},"days"),15)

    def test_policy_zero_carry_forward_is_not_unlimited(self):
        balances.ensure_current_balance(self.emp)
        self.rules['carry_forward_days'] = 0
        allocation = balances.ensure_allocation(self.emp, balances.PAID, date(self.today.year+1, 1, 1))
        self.assertEqual(allocation.unused_leaves, 0)

    def test_existing_legacy_balance_is_not_credited_twice(self):
        allocation = frappe.get_doc({'doctype':'Leave Allocation','employee':self.emp,'leave_type':balances.PAID,
            'from_date':date(self.today.year,4,1),'to_date':date(self.today.year+1,3,31),'new_leaves_allocated':10})
        allocation.insert(ignore_permissions=True); allocation.submit()
        balances.ensure_current_balance(self.emp)
        self.assertEqual(balances.paid_balance(self.emp),10)
        self.assertEqual(frappe.db.count('HR Leave Posting',{'employee':self.emp}),0)

    def test_calendar_adoption_closes_allocation_and_adjustment_without_double_count(self):
        allocation = frappe.get_doc({'doctype':'Leave Allocation','employee':self.emp,'leave_type':balances.PAID,
            'from_date':date(self.today.year,4,1),'to_date':date(self.today.year+1,3,31),'new_leaves_allocated':10})
        allocation.insert(ignore_permissions=True); allocation.submit()
        balances.post_leave(self.emp, balances.PAID, 2, self.today-timedelta(days=2), 'Verified prior adjustment', 'HR adjustment',self.hr,'legacy-extra:'+self.emp)
        frappe.set_user(self.hr)
        preview=balances.preview_leave_adoption(self.emp)
        self.assertEqual(preview['balance'],12)
        result=balances.adopt_leave_year(self.emp,12,'Verified legacy closing balance and new calendar year',allocation.name,uuid.uuid4().hex)
        self.assertEqual(result['balance'],12)
        self.assertEqual(getdate(result['allocation'].to_date),date(self.today.year,12,31))
        self.assertTrue(result['allocation'].sf_managed_policy)
        balances.ensure_current_balance(self.emp)
        self.assertEqual(balances.paid_balance(self.emp),12)

    def test_compensatory_leave_reserves_credit_and_cancellation_releases_it(self):
        sunday=self.today-timedelta(days=(self.today.weekday()+1)%7 or 7)
        with patch('volunteering.volunteering.attendance_service.get_submitted_work_log_hours',return_value=6):
            credit=self.request('Compensatory Credit',from_date=str(sunday)); self.approve(credit)
        day=self.today+timedelta(days=2)
        while day.weekday()==6:day+=timedelta(days=1)
        row=self.request(balances.COMP,from_date=str(day),to_date=str(day))
        self.assertEqual(portal._used(credit['name']),1)
        frappe.set_user(self.staff)
        portal.decide_time_request(row['doctype'],row['name'],'cancel',row['modified'],reason='No longer need this compensatory leave')
        self.assertEqual(portal._used(credit['name']),0)
        with self.assertRaises(frappe.ValidationError): self.request(balances.COMP,from_date=str(getdate(credit['valid_until'])+timedelta(days=2)))

    def test_work_log_late_hr_exception_and_processed_payroll_protection(self):
        from volunteering.volunteering.work_log_portal import save_work_log
        raw={'employee':self.emp,'date':str(self.today-timedelta(days=10)),'items':[{'task_title':'Late verified work','description':'Checked the work details with project lead.','time_spent_hours':6}]}
        frappe.set_user(self.staff)
        with self.assertRaises(frappe.ValidationError):save_work_log(raw)
        frappe.set_user(self.hr)
        raw['hr_exception_reason']='Verified late work log against supervisor records'
        row=save_work_log(raw,submit=1)['log']
        self.assertEqual(row['status'],'Submitted')
        self.assertEqual(frappe.db.get_value('Daily Work Log',row['name'],'hr_exception_by'),self.hr)
        raw['date']=str(self.today-timedelta(days=9))
        with patch.object(balances,'salary_processed',return_value=True):
            with self.assertRaises(frappe.ValidationError):save_work_log(raw)

    def test_half_day_work_has_unpaid_other_half(self):
        from volunteering.volunteering.attendance_service import process_employee_attendance
        day=self.today-timedelta(days=4)
        while day.weekday()==6:day-=timedelta(days=1)
        with patch('volunteering.volunteering.attendance_service.get_submitted_work_log_hours',return_value=3):
            process_employee_attendance(self.emp,day)
        row=frappe.db.get_value('Attendance',{'employee':self.emp,'attendance_date':day},['status','half_day_status'],as_dict=True)
        self.assertEqual(row.status,'Half Day');self.assertEqual(row.half_day_status,'Absent')

    def test_balance_retry_cannot_reuse_key_for_different_amount(self):
        frappe.set_user(self.hr); key=uuid.uuid4().hex
        balances.adjust_leave_balance(self.emp,1,'Verified special balance adjustment',key)
        with self.assertRaises(frappe.ValidationError):balances.adjust_leave_balance(self.emp,2,'Verified special balance adjustment',key)

    def test_published_policy_is_immutable_and_historical_rules_are_preserved(self):
        self.policy_patch.stop()
        frappe.local.sf_hr_policies=None
        try:
            current=policy.policy_on()
            past=policy.policy_on(self.today-timedelta(days=2))
            frappe.set_user(self.hr)
            before=frappe.db.count('HR Policy Revision')
            result=policy.publish_hr_policy({**policy.DEFAULTS,'monthly_leave':3},str(self.today+timedelta(days=5)),
                'Approved future monthly entitlement revision',current.get('_revision'))
            self.assertEqual(frappe.db.count('HR Policy Revision'),before+1)
            self.assertEqual(policy.policy_on()['monthly_leave'],current['monthly_leave'])
            self.assertEqual(policy.policy_on(self.today+timedelta(days=5))['monthly_leave'],3)
            self.assertEqual(policy.policy_on(self.today-timedelta(days=2))['monthly_leave'],past['monthly_leave'])
            doc=frappe.get_doc('HR Policy Revision',result['history'][0].name)
            doc.reason='Change the published historical evidence'
            with self.assertRaises(frappe.ValidationError):doc.save(ignore_permissions=True)
            with self.assertRaises(frappe.ValidationError):policy.publish_hr_policy(policy.DEFAULTS,str(self.today-timedelta(days=1)),'Backdated policy revision rejected',current.get('_revision'))
        finally:
            self.policy_patch.start();frappe.local.sf_hr_policies=None

    def test_pending_leave_prevents_automatic_unpaid_absence(self):
        from volunteering.volunteering.attendance_service import process_employee_attendance
        day=self.today-timedelta(days=4)
        while day.weekday()==6:day-=timedelta(days=1)
        frappe.set_user(self.hr)
        portal.submit_time_request({'employee':self.emp,'type':balances.PAID,'from_date':str(day),'reason':'Verified old leave awaiting manager approval',
            'hr_exception_reason':'Verified delayed leave request against supervisor record'},uuid.uuid4().hex)
        with patch('volunteering.volunteering.attendance_service.get_submitted_work_log_hours',return_value=0):
            self.assertEqual(process_employee_attendance(self.emp,day),'skipped')
        self.assertFalse(frappe.db.exists('Attendance',{'employee':self.emp,'attendance_date':day}))

    def test_hr_exception_does_not_allow_forged_identity(self):
        from volunteering.volunteering.hr_policy import override_reason
        doc=frappe.new_doc('Daily Work Log');doc.hr_exception_by=self.hr;doc.hr_exception_on=nowdate()
        frappe.set_user(self.staff)
        with self.assertRaises(frappe.PermissionError):override_reason(doc)
        doc.hr_exception_reason='Pretend to authorise a late work entry'
        with self.assertRaises(frappe.PermissionError):override_reason(doc)

    def test_salary_counts_absent_and_half_days_using_attendance(self):
        from volunteering.volunteering.attendance_service import ensure_attendance
        balances.sync_leave_masters()
        self.assertEqual(frappe.db.get_single_value('Payroll Settings','payroll_based_on'),'Attendance')
        day=self.today-timedelta(days=10)
        while day.weekday() in (5,6):day-=timedelta(days=1)
        ensure_attendance(self.emp,day,'Absent',working_hours=0)
        ensure_attendance(self.emp,day+timedelta(days=1),'Half Day',working_hours=3,half_day_status='Absent')
        slip=frappe.get_doc({'doctype':'Salary Slip','employee':self.emp,'start_date':day,'end_date':day+timedelta(days=1),
            'actual_start_date':day,'actual_end_date':day+timedelta(days=1)})
        with patch.object(type(slip),'get_holidays_for_employee',return_value=[]):slip.get_working_days_details()
        self.assertEqual(slip.absent_days,1.5)
        self.assertEqual(slip.payment_days,0.5)

    def test_salary_submission_waits_for_open_leave_and_logging_window(self):
        from volunteering.volunteering.employee_calendars import validate_salary_policy
        row=self.request()
        doc=frappe.get_doc({'doctype':'Salary Slip','employee':self.emp,'start_date':row['from_date'],'end_date':row['to_date']})
        with self.assertRaises(frappe.ValidationError):validate_salary_policy(doc)
        doc.start_date=self.today;doc.end_date=self.today
        with self.assertRaises(frappe.ValidationError):validate_salary_policy(doc)

    def test_direct_manager_cannot_approve_director_routed_extended_leave(self):
        doc=frappe.get_doc({'doctype':'Leave Application','employee':self.emp,'employee_name':'Policy Employee','from_date':str(self.today+timedelta(days=20)),
            'to_date':str(self.today+timedelta(days=35)),'total_leave_days':12,'leave_approver':'another.director@example.com','status':'Open','leave_type':balances.PAID})
        frappe.set_user(self.manager)
        self.assertFalse(portal._can_decide_doc(doc))

    def test_next_year_request_does_not_expire_or_change_this_year_balance(self):
        balances.ensure_current_balance(self.emp)
        before=balances.paid_balance(self.emp)
        allocation=balances.ensure_allocation(self.emp,balances.PAID,date(self.today.year+1,1,1))
        self.assertEqual(allocation.carry_forward,0)
        self.assertEqual(balances.paid_balance(self.emp),before)
        self.assertFalse(frappe.db.exists('HR Leave Posting',{'employee':self.emp,'source':'Carry forward'}))

    def test_late_previous_year_leave_adjusts_carry_with_a_new_audit_entry(self):
        balances.ensure_current_balance(self.emp)
        before=balances.paid_balance(self.emp)
        balances.post_leave(self.emp,balances.PAID,10-before,self.today,'Verified closing test balance','HR adjustment',self.hr,'year-close:'+self.emp)
        day=self.today+timedelta(days=7)
        while day.weekday()==6:day+=timedelta(days=1)
        row=self.request(balances.PAID,from_date=str(day),to_date=str(day))
        next_year=date(self.today.year+1,1,1)
        allocation=balances.ensure_allocation(self.emp,balances.PAID,next_year)
        with patch.object(balances,'nowdate',return_value=str(next_year)):
            balances._carry_forward(self.emp,balances.PAID,allocation,next_year)
            self.assertEqual(balances.paid_balance(self.emp,next_year),10)
            self.approve(row)
            self.assertEqual(balances.paid_balance(self.emp,next_year),9)
        self.assertEqual(frappe.db.count('HR Leave Posting',{'employee':self.emp,'source':'Carry correction'}),1)

    def test_expired_compensatory_credit_does_not_reduce_another_year(self):
        end=date(self.today.year,12,31)
        sunday=end-timedelta(days=(end.weekday()+1)%7)
        with patch.object(portal,'nowdate',return_value=str(sunday)), patch('volunteering.volunteering.attendance_service.get_submitted_work_log_hours',return_value=6):
            row=self.request('Compensatory Credit',from_date=str(sunday))
            self.approve(row,self.hr,valid_until=str(end),override='Verified expiry at this leave year end')
        with patch.object(portal,'nowdate',return_value=str(end+timedelta(days=2))):portal.expire_compensatory_credits(self.emp)
        posting=frappe.db.get_value('HR Leave Posting',{'employee':self.emp,'source':'Compensatory expiry'},['days','posting_date'],as_dict=True)
        self.assertEqual(posting.days,-1)
        self.assertEqual(getdate(posting.posting_date),end)
        self.assertFalse(balances.current_allocation(self.emp,balances.COMP,end+timedelta(days=1)))

    def test_hr_can_change_payroll_mode_through_a_reasoned_policy_revision(self):
        self.policy_patch.stop();frappe.local.sf_hr_policies=None
        try:
            frappe.set_user(self.hr)
            with patch.object(balances,'policy_on',side_effect=policy.policy_on):
                current=policy.policy_on()
                policy.publish_hr_policy({**policy.DEFAULTS,'attendance_based_payroll':0},str(self.today),
                    'Approved payroll calculation policy override',current.get('_revision'))
                self.assertEqual(frappe.db.get_single_value('Payroll Settings','payroll_based_on'),'Leave')
        finally:self.policy_patch.start();frappe.local.sf_hr_policies=None

    def test_saved_leave_policy_reference_cannot_be_replaced(self):
        row=self.request(balances.PAID,from_date=str(self.today+timedelta(days=7)))
        doc=frappe.get_doc('Leave Application',row['name']);doc.sf_policy_revision='forged-policy-reference'
        from volunteering.volunteering.overrides.leave_application import prepare_leave_policy
        with self.assertRaises(frappe.PermissionError):prepare_leave_policy(doc)

    def test_legacy_accrual_schedule_stays_unchanged_until_explicit_adoption(self):
        doc=frappe.get_doc({'doctype':'Leave Allocation','employee':self.emp,'leave_type':balances.PAID,
            'from_date':date(self.today.year,4,1),'to_date':date(self.today.year+1,3,31),'new_leaves_allocated':10,
            'earned_leave_schedule':[{'allocation_date':self.today+timedelta(days=7),'number_of_leaves':2.5}]})
        doc.insert(ignore_permissions=True);doc.submit()
        self.rules['monthly_leave']=3
        balances.sync_leave_masters();balances.ensure_current_balance(self.emp)
        self.assertEqual(frappe.db.get_value('Earned Leave Schedule',{'parent':doc.name},'number_of_leaves'),2.5)
        self.assertEqual(balances.paid_balance(self.emp),10)
