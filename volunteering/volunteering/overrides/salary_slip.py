"""Dated calendar-day payroll and explicitly enrolled employee deductions."""
import calendar
import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip, verify_lwp_days_corrected
from volunteering.volunteering.hr_policy import policy_on


class SevamritaSalarySlip(SalarySlip):
    def get_working_days_details(self,lwp=None,for_preview=0,lwp_days_corrected=None):
        policy=policy_on(self.end_date)
        if not policy.get('calendar_day_payroll') or self.salary_slip_based_on_timesheet:
            return super().get_working_days_details(lwp,for_preview,lwp_days_corrected)
        start,end=getdate(self.start_date),getdate(self.end_date)
        if (start.year,start.month)!=(end.year,end.month):frappe.throw(_('Calendar-day salary must cover dates in a single month.'))
        total=calendar.monthrange(start.year,start.month)[1]
        if for_preview:self.total_working_days=total;self.payment_days=(end-start).days+1;return
        holidays=self.get_holidays_for_employee(start,end)
        settings=frappe.get_single('Payroll Settings')
        fraction=0.5
        if policy['attendance_based_payroll']:
            actual_lwp,absent=self.calculate_lwp_ppl_and_absent_days_based_on_attendance(holidays,fraction,False)
            half=self.get_half_absent_days(False,holidays)*fraction
            # Missing work becomes unpaid only after the dated logging window;
            # submission validation prevents finalising a still-open window.
            absent+=half
        else:
            actual_lwp=self.calculate_lwp_or_ppl_based_on_leave_application(holidays,[add_days(start,i) for i in range((end-start).days+1)],fraction)
            absent=0
        self.leave_without_pay=flt(actual_lwp if lwp is None else lwp)
        self.total_working_days=total;self.absent_days=absent
        paid=self.get_payment_days(True)
        self.payment_days=max(0,paid-self.leave_without_pay-absent)
        if lwp_days_corrected and verify_lwp_days_corrected(self.employee,start,end,lwp_days_corrected):self.payment_days=min(paid,self.payment_days+lwp_days_corrected)

    def apply_regional_deductions(self):
        super().apply_regional_deductions()
        # Recalculation must not retain deductions from an earlier profile.
        owned_deductions = {'SF Employee PF', 'SF Professional Tax'}
        self.set('deductions', [row for row in self.get('deductions') or [] if row.salary_component not in owned_deductions])
        self.set('employer_contributions', [row for row in self.get('employer_contributions') or [] if row.salary_component != 'SF Employer PF'])
        self.sf_employer_pf = 0
        self.sf_payroll_policy = None
        policy=policy_on(self.end_date)
        if not policy.get('charter_enabled'):return
        from volunteering.volunteering.hr_resources import payroll_profile_on,deduction_values
        profile=payroll_profile_on(self.employee,self.end_date)
        if not profile:return
        if not profile.get('pf_enrolled') and not profile.get('pt_applicable'):
            self.sf_employer_pf=0;return
        basic_component=profile.get('basic_component') or 'Basic'
        basic=next((flt(row.amount) for row in self.earnings if row.salary_component==basic_component),None)
        if profile.get('pf_enrolled') and basic is None:frappe.throw(_('Choose the Basic salary component in this employee payroll profile before calculating PF.'))
        values=deduction_values(basic or 0,flt(self.gross_pay),frappe.db.get_value('Employee',self.employee,'gender'),getdate(self.end_date).month,profile,policy)
        names={'employee_pf':'SF Employee PF','professional_tax':'SF Professional Tax'}
        for key,name in names.items():
            amount=values[key]
            if amount:
                for row in self.deductions:
                    other=(row.salary_component or '').lower()
                    if row.salary_component!=name and (('provident' in other or other in {'pf','epf'}) if key=='employee_pf' else 'professional tax' in other):
                        frappe.throw(_('This salary already has {0}. Resolve the existing deduction before enabling an additional automatic deduction.').format(row.salary_component))
                if not frappe.db.exists('Salary Component',name):
                    frappe.get_doc({'doctype':'Salary Component','salary_component':name,'salary_component_abbr':'SFEPF' if key=='employee_pf' else 'SFPT',
                        'type':'Deduction','depends_on_payment_days':0}).insert(ignore_permissions=True)
            existing=next((row for row in self.deductions if row.salary_component==name),None)
            if existing:existing.amount=amount;existing.default_amount=amount;existing.amount_based_on_formula=0;existing.depends_on_payment_days=0
            elif amount:self.append('deductions',{'salary_component':name,'amount':amount,'default_amount':amount,'depends_on_payment_days':0})
        contribution=next((row for row in self.get('employer_contributions') or [] if row.salary_component=='SF Employer PF'),None)
        if values['employer_pf']:
            if not frappe.db.exists('Salary Component','SF Employer PF'):
                frappe.get_doc({'doctype':'Salary Component','salary_component':'SF Employer PF','salary_component_abbr':'SFERPF','type':'Employer Contribution','depends_on_payment_days':0}).insert(ignore_permissions=True)
            if contribution:contribution.amount=values['employer_pf'];contribution.default_amount=values['employer_pf']
            else:self.append('employer_contributions',{'salary_component':'SF Employer PF','amount':values['employer_pf'],'default_amount':values['employer_pf'],'depends_on_payment_days':0})
        elif contribution:contribution.amount=0;contribution.default_amount=0
        self.sf_employer_pf=values['employer_pf'];self.sf_payroll_policy=policy.get('_revision')
